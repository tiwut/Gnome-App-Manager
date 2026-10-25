import os
import threading
from gi.repository import Gtk, Adw, GLib, Pango
from typing import Callable, Optional, List

from ..models.app_info import AppItem
from ..models.location_info import LeftoverItem, LocationCategory
from ..backends.detector import AppDetector
from ..core.scanner import ResidualScanner
from ..core.cleaner import LeftoverCleaner
from ..core.utils import format_bytes, execute_process_with_callback


class UninstallDialog(Adw.Window):
    def __init__(self, parent_window: Gtk.Window, app: AppItem, on_complete_refresh: Optional[Callable[[], None]] = None):
        super().__init__()
        self.set_transient_for(parent_window)
        self.set_modal(True)
        self.set_default_size(750, 600)
        self.set_title(f"Uninstall {app.name}")

        self.app = app
        self.on_complete_refresh = on_complete_refresh
        self.selected_mode = "moderate"
        self.detected_leftovers: List[LeftoverItem] = []
        self.freed_bytes = 0
        self.purged_count = 0

        self.toolbar_view = Adw.ToolbarView()
        self.set_content(self.toolbar_view)

        self.header = Adw.HeaderBar()
        self.header.set_show_title(True)
        self.toolbar_view.add_top_bar(self.header)

        self.stack = Adw.ViewStack()
        self.toolbar_view.set_content(self.stack)

        self._build_step_profile()
        self._build_step_native()
        self._build_step_scan()
        self._build_step_review()
        self._build_step_summary()

        self.stack.set_visible_child_name("step_profile")

    def _build_step_profile(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        page.set_margin_top(20)
        page.set_margin_bottom(24)
        page.set_margin_start(24)
        page.set_margin_end(24)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(650)
        clamp.set_child(page)

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        icon_img = Gtk.Image.new_from_icon_name(self.app.icon_name or "application-x-executable")
        icon_img.set_pixel_size(48)
        icon_img.add_css_class("app-icon")
        title_box.append(icon_img)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        h_lbl = Gtk.Label(label=f"Uninstall {self.app.name}")
        h_lbl.set_halign(Gtk.Align.START)
        h_lbl.add_css_class("title-2")
        info_box.append(h_lbl)

        sub_lbl = Gtk.Label(label=f"Backend: {self.app.backend_display} • ID: {self.app.id}")
        sub_lbl.set_halign(Gtk.Align.START)
        sub_lbl.add_css_class("dim-label")
        info_box.append(sub_lbl)
        title_box.append(info_box)
        page.append(title_box)

        pref_group = Adw.PreferencesGroup()
        pref_group.set_title("Select Uninstallation Profile")
        pref_group.set_description("Choose how deeply Gnome App Manager should scan for residual files and data.")

        self.row_safe = Adw.ActionRow()
        self.row_safe.set_title("Safe")
        self.row_safe.set_subtitle("Runs native uninstaller and cleans direct user cache and temporary files.")
        self.radio_safe = Gtk.CheckButton()
        self.row_safe.add_prefix(self.radio_safe)
        self.row_safe.set_activatable_widget(self.radio_safe)
        pref_group.add(self.row_safe)

        self.row_mod = Adw.ActionRow()
        self.row_mod.set_title("Moderate (Recommended)")
        self.row_mod.set_subtitle("Safe mode + deep scan for user configuration, Flatpak sandbox data (~/.var/app), autostart entries, and desktop shortcuts.")
        self.radio_mod = Gtk.CheckButton.new()
        self.radio_mod.set_group(self.radio_safe)
        self.radio_mod.set_active(True)
        self.row_mod.add_prefix(self.radio_mod)
        self.row_mod.set_activatable_widget(self.radio_mod)
        pref_group.add(self.row_mod)

        self.row_deep = Adw.ActionRow()
        self.row_deep.set_title("Advanced / Deep")
        self.row_deep.set_subtitle("Moderate mode + thorough scan of system-wide directories (/etc, /var, /usr/share, /opt), systemd services, icons, and completions.")
        self.radio_deep = Gtk.CheckButton.new()
        self.radio_deep.set_group(self.radio_safe)
        self.row_deep.add_prefix(self.radio_deep)
        self.row_deep.set_activatable_widget(self.radio_deep)
        pref_group.add(self.row_deep)

        page.append(pref_group)

        options_group = Adw.PreferencesGroup()
        options_group.set_title("Additional Options")

        self.purge_data_row = Adw.SwitchRow()
        self.purge_data_row.set_title("Purge Application Data")
        self.purge_data_row.set_subtitle("Instruct package manager to remove user data folders where supported.")
        self.purge_data_row.set_active(True)
        options_group.add(self.purge_data_row)

        page.append(options_group)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(12)

        cancel_btn = Gtk.Button.new_with_label("Cancel")
        cancel_btn.connect("clicked", lambda b: self.close())
        btn_box.append(cancel_btn)

        start_btn = Gtk.Button.new_with_label("Proceed to Uninstall")
        start_btn.add_css_class("suggested-action")
        start_btn.add_css_class("destructive-action")
        start_btn.connect("clicked", self._start_native_uninstall)
        btn_box.append(start_btn)

        page.append(btn_box)

        self.stack.add_named(clamp, "step_profile")

    def _build_step_native(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        page.set_margin_top(20)
        page.set_margin_bottom(20)
        page.set_margin_start(24)
        page.set_margin_end(24)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(700)
        clamp.set_child(page)

        self.native_status_lbl = Gtk.Label(label="Executing native package manager uninstaller...")
        self.native_status_lbl.set_halign(Gtk.Align.START)
        self.native_status_lbl.add_css_class("title-3")
        page.append(self.native_status_lbl)

        self.native_progress = Gtk.ProgressBar()
        self.native_progress.set_pulse_step(0.1)
        page.append(self.native_progress)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_min_content_height(240)
        scrolled.add_css_class("terminal-box")

        self.text_buffer = Gtk.TextBuffer()
        text_view = Gtk.TextView(buffer=self.text_buffer)
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        scrolled.set_child(text_view)
        page.append(scrolled)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)

        self.skip_scan_btn = Gtk.Button.new_with_label("Finish Without Scanning")
        self.skip_scan_btn.set_sensitive(False)
        self.skip_scan_btn.connect("clicked", lambda b: self.close())
        btn_box.append(self.skip_scan_btn)

        self.next_scan_btn = Gtk.Button.new_with_label("Scan for Leftovers →")
        self.next_scan_btn.add_css_class("suggested-action")
        self.next_scan_btn.set_sensitive(False)
        self.next_scan_btn.connect("clicked", self._start_leftover_scan)
        btn_box.append(self.next_scan_btn)

        page.append(btn_box)

        self.stack.add_named(clamp, "step_native")

    def _build_step_scan(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        page.set_valign(Gtk.Align.CENTER)
        page.set_halign(Gtk.Align.CENTER)
        page.set_margin_top(48)
        page.set_margin_bottom(48)

        status_page = Adw.StatusPage()
        status_page.set_icon_name("system-search-symbolic")
        status_page.set_title("Scanning System for Leftovers")
        status_page.set_description("Searching user configs, caches, sandboxes, desktop shortcuts, and system entries...")
        page.append(status_page)

        self.scan_spinner = Gtk.Spinner()
        self.scan_spinner.set_size_request(48, 48)
        self.scan_spinner.set_halign(Gtk.Align.CENTER)
        page.append(self.scan_spinner)

        self.stack.add_named(page, "step_scan")

    def _build_step_review(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        page.set_margin_top(16)
        page.set_margin_bottom(20)
        page.set_margin_start(20)
        page.set_margin_end(20)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        icon = Gtk.Image.new_from_icon_name("edit-find-symbolic")
        icon.set_pixel_size(32)
        header_box.append(icon)

        title_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.review_title_lbl = Gtk.Label(label="Residual Leftovers Found")
        self.review_title_lbl.set_halign(Gtk.Align.START)
        self.review_title_lbl.add_css_class("title-3")
        title_vbox.append(self.review_title_lbl)

        self.review_sub_lbl = Gtk.Label(label="Select the residual files and folders you wish to permanently remove.")
        self.review_sub_lbl.set_halign(Gtk.Align.START)
        self.review_sub_lbl.add_css_class("dim-label")
        title_vbox.append(self.review_sub_lbl)
        header_box.append(title_vbox)

        page.append(header_box)

        tool_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        sel_all_btn = Gtk.Button.new_with_label("Select All")
        sel_all_btn.add_css_class("flat")
        sel_all_btn.connect("clicked", lambda b: self._toggle_all_leftovers(True))
        tool_bar.append(sel_all_btn)

        desel_all_btn = Gtk.Button.new_with_label("Deselect All")
        desel_all_btn.add_css_class("flat")
        desel_all_btn.connect("clicked", lambda b: self._toggle_all_leftovers(False))
        tool_bar.append(desel_all_btn)

        tool_bar.append(Gtk.Box(hexpand=True))

        self.selected_stat_lbl = Gtk.Label(label="0 items selected")
        self.selected_stat_lbl.add_css_class("size-pill")
        tool_bar.append(self.selected_stat_lbl)

        page.append(tool_bar)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.leftover_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scrolled.set_child(self.leftover_list_box)
        page.append(scrolled)

        footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        footer_box.set_halign(Gtk.Align.END)
        footer_box.set_margin_top(8)

        cancel_btn = Gtk.Button.new_with_label("Skip Cleanup")
        cancel_btn.connect("clicked", lambda b: self._finish_wizard())
        footer_box.append(cancel_btn)

        self.delete_btn = Gtk.Button.new_with_label("Delete Selected Leftovers")
        self.delete_btn.add_css_class("suggested-action")
        self.delete_btn.add_css_class("destructive-action")
        self.delete_btn.connect("clicked", self._execute_leftover_cleanup)
        footer_box.append(self.delete_btn)

        page.append(footer_box)

        self.stack.add_named(page, "step_review")

    def _build_step_summary(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        page.set_valign(Gtk.Align.CENTER)
        page.set_halign(Gtk.Align.CENTER)
        page.set_margin_top(36)
        page.set_margin_bottom(36)

        self.summary_status = Adw.StatusPage()
        self.summary_status.set_icon_name("emblem-ok-symbolic")
        self.summary_status.set_title("Uninstallation Complete!")
        self.summary_status.set_description("All selected files and residual components have been successfully removed.")
        page.append(self.summary_status)

        done_btn = Gtk.Button.new_with_label("Done")
        done_btn.add_css_class("suggested-action")
        done_btn.set_halign(Gtk.Align.CENTER)
        done_btn.connect("clicked", lambda b: self._finish_wizard())
        page.append(done_btn)

        self.stack.add_named(page, "step_summary")

    def _start_native_uninstall(self, btn):
        if self.radio_safe.get_active():
            self.selected_mode = "safe"
        elif self.radio_deep.get_active():
            self.selected_mode = "deep"
        else:
            self.selected_mode = "moderate"

        purge_data = self.purge_data_row.get_active()
        cmd = AppDetector.get_uninstall_command(self.app, purge_data=purge_data)

        self.stack.set_visible_child_name("step_native")
        self._append_log(f"Starting uninstallation for: {self.app.name} ({self.app.id})\n")
        self._append_log(f"Profile: {self.selected_mode.capitalize()} | Command: {' '.join(cmd)}\n")
        self._append_log("-" * 60 + "\n")

        self.pulse_timer_id = GLib.timeout_add(100, self._on_pulse)

        def on_output(line: str):
            self._append_log(line + "\n")

        def on_complete(exit_code: int):
            if hasattr(self, "pulse_timer_id") and self.pulse_timer_id:
                GLib.source_remove(self.pulse_timer_id)
                self.pulse_timer_id = None
            self.native_progress.set_fraction(1.0)

            if exit_code == 0:
                self.native_status_lbl.set_label("Native uninstallation completed successfully.")
                self._append_log("\n[SUCCESS] Package uninstalled cleanly.\n")
            else:
                self.native_status_lbl.set_label(f"Process finished with code {exit_code}.")
                self._append_log(f"\n[NOTE] Package manager exited with code {exit_code}.\n")

            self.skip_scan_btn.set_sensitive(True)
            self.next_scan_btn.set_sensitive(True)

        execute_process_with_callback(cmd, on_output, on_complete)

    def _on_pulse(self):
        self.native_progress.pulse()
        return True

    def _append_log(self, text: str):
        end_iter = self.text_buffer.get_end_iter()
        self.text_buffer.insert(end_iter, text)

    def _start_leftover_scan(self, btn):
        self.stack.set_visible_child_name("step_scan")
        self.scan_spinner.start()

        def scan_worker():
            leftovers = ResidualScanner.scan_leftovers(self.app, mode=self.selected_mode)
            GLib.idle_add(self._on_scan_completed, leftovers)

        threading.Thread(target=scan_worker, daemon=True).start()

    def _on_scan_completed(self, leftovers: List[LeftoverItem]):
        self.scan_spinner.stop()
        self.detected_leftovers = leftovers

        if not leftovers:
            self.summary_status.set_title("Completely Clean!")
            self.summary_status.set_description(f"{self.app.name} left no residual files or directories behind.")
            self.stack.set_visible_child_name("step_summary")
            return

        self._populate_review_list()
        self.stack.set_visible_child_name("step_review")

    def _populate_review_list(self):
        while self.leftover_list_box.get_first_child():
            self.leftover_list_box.remove(self.leftover_list_box.get_first_child())

        groups = {}
        for item in self.detected_leftovers:
            cat = item.category
            if cat not in groups:
                groups[cat] = []
            groups[cat].append(item)

        for cat, items in groups.items():
            pref_group = Adw.PreferencesGroup()
            pref_group.set_title(GLib.markup_escape_text(cat.value))

            for item in items:
                row = Adw.ActionRow()
                row.set_title(GLib.markup_escape_text(item.path))
                
                details = [item.reason]
                if item.requires_root:
                    details.append("Requires Administrator Privileges")
                row.set_subtitle(GLib.markup_escape_text(" • ".join(details)))

                check = Gtk.CheckButton()
                check.set_active(item.selected)
                check.connect("toggled", lambda b, it=item: self._on_item_toggled(it, b.get_active()))
                row.add_prefix(check)
                row.set_activatable_widget(check)

                icon = Gtk.Image.new_from_icon_name(cat.icon_name)
                row.add_prefix(icon)

                sz_lbl = Gtk.Label(label=item.formatted_size)
                sz_lbl.add_css_class("size-pill")
                row.add_suffix(sz_lbl)

                if item.requires_root:
                    root_badge = Gtk.Label(label="Root")
                    root_badge.add_css_class("badge-pill")
                    root_badge.add_css_class("badge-snap")
                    row.add_suffix(root_badge)

                pref_group.add(row)

            self.leftover_list_box.append(pref_group)

        self._update_selected_stats()

    def _on_item_toggled(self, item: LeftoverItem, active: bool):
        item.selected = active
        self._update_selected_stats()

    def _toggle_all_leftovers(self, select: bool):
        for item in self.detected_leftovers:
            item.selected = select
        self._populate_review_list()

    def _update_selected_stats(self):
        selected = [i for i in self.detected_leftovers if i.selected]
        total_size = sum(i.size_bytes for i in selected)
        self.selected_stat_lbl.set_label(f"{len(selected)} items selected ({format_bytes(total_size)})")
        self.delete_btn.set_sensitive(len(selected) > 0)

    def _execute_leftover_cleanup(self, btn):
        self.delete_btn.set_sensitive(False)

        def worker():
            def on_progress(status: str, pct: float):
                GLib.idle_add(lambda: self.review_sub_lbl.set_label(status))

            def on_finished(bytes_freed: int, count_removed: int, errors: List[str]):
                GLib.idle_add(self._on_cleanup_finished, bytes_freed, count_removed, errors)

            LeftoverCleaner.clean_leftovers(
                self.detected_leftovers,
                on_progress=on_progress,
                on_finished=on_finished
            )

        threading.Thread(target=worker, daemon=True).start()

    def _on_cleanup_finished(self, bytes_freed: int, count_removed: int, errors: List[str]):
        self.freed_bytes = bytes_freed
        self.purged_count = count_removed

        self.summary_status.set_title("Successfully Uninstalled & Cleaned!")
        msg = f"Reclaimed {format_bytes(bytes_freed)} of storage.\nRemoved {count_removed} residual files and system configurations."
        if errors:
            msg += f"\n\nNote: {len(errors)} items could not be removed."
        self.summary_status.set_description(msg)
        self.stack.set_visible_child_name("step_summary")

    def _finish_wizard(self):
        if self.on_complete_refresh:
            self.on_complete_refresh()
        self.close()
