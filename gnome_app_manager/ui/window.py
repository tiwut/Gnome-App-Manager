import os
import threading
from gi.repository import Gtk, Adw, GLib, Gio, Gdk, GObject
from typing import List, Optional

from ..models.app_info import AppItem
from ..backends.detector import AppDetector
from ..core.utils import format_bytes
from .app_row import AppRow
from .app_detail_view import AppDetailView
from .uninstall_dialog import UninstallDialog
from .batch_dialog import BatchUninstallDialog


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application):
        super().__init__(application=application)
        self.set_default_size(1100, 750)
        self.set_title("Gnome App Manager")

        self.all_apps: List[AppItem] = []
        self.filtered_apps: List[AppItem] = []
        self.active_category = "all"
        self.sort_by = "name"
        self.batch_mode = False
        self.include_nodisplay = False
        self.selected_app_items = set()

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        self.split_view = Adw.NavigationSplitView()
        self.split_view.set_min_sidebar_width(420)
        self.split_view.set_max_sidebar_width(520)
        self.toast_overlay.set_child(self.split_view)

        self.sidebar_page = Adw.NavigationPage.new(
            self._create_sidebar_content(),
            "Applications"
        )
        self.split_view.set_sidebar(self.sidebar_page)

        self.detail_view = AppDetailView(on_uninstall=self._launch_uninstaller)
        self.detail_page = Adw.NavigationPage.new(
            self._create_detail_content(),
            "App Inspector"
        )
        self.split_view.set_content(self.detail_page)

        self._setup_shortcuts()
        self.reload_apps()

    def _create_sidebar_content(self) -> Gtk.Widget:
        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.set_show_title(True)

        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Reload Installed Applications (Ctrl+R)")
        refresh_btn.connect("clicked", lambda b: self.reload_apps())
        header.pack_start(refresh_btn)

        self.batch_btn = Gtk.ToggleButton()
        self.batch_btn.set_icon_name("selection-mode-symbolic")
        self.batch_btn.set_tooltip_text("Toggle Multi-App Selection")
        self.batch_btn.connect("toggled", self._on_batch_mode_toggled)
        header.pack_start(self.batch_btn)

        self.search_toggle = Gtk.ToggleButton()
        self.search_toggle.set_icon_name("edit-find-symbolic")
        self.search_toggle.set_tooltip_text("Search Applications (Ctrl+F)")
        header.pack_end(self.search_toggle)

        menu = Gio.Menu()
        menu.append("Sort by Name", "win.sort_name")
        menu.append("Sort by Size", "win.sort_size")
        menu.append("Show Background System Helpers", "win.toggle_nodisplay")
        menu.append("About Gnome App Manager", "win.about")

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        toolbar_view.add_top_bar(header)

        self.search_bar = Gtk.SearchBar()
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.search_bar.set_child(self.search_entry)
        self.search_bar.set_key_capture_widget(self)
        self.search_bar.connect_entry(self.search_entry)
        self.search_toggle.bind_property(
            "active",
            self.search_bar,
            "search-mode-enabled",
            GObject.BindingFlags.BIDIRECTIONAL if hasattr(GLib, "BindingFlags") else 0
        )
        toolbar_view.add_top_bar(self.search_bar)

        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        filter_box.set_margin_start(12)
        filter_box.set_margin_end(12)
        filter_box.set_margin_top(8)
        filter_box.set_margin_bottom(8)
        filter_box.set_halign(Gtk.Align.CENTER)

        self.filter_buttons = {}
        for cat_id, cat_label in [
            ("all", "All"),
            ("flatpak", "Flatpak"),
            ("system", "System"),
            ("snap", "Snap"),
            ("appimage", "AppImage & Other")
        ]:
            btn = Gtk.ToggleButton(label=cat_label)
            btn.add_css_class("flat")
            btn.connect("toggled", lambda b, c=cat_id: self._on_category_changed(c, b.get_active()))
            filter_box.append(btn)
            self.filter_buttons[cat_id] = btn

        toolbar_view.add_top_bar(filter_box)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        toolbar_view.set_content(vbox)

        self.stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.stats_box.set_margin_start(16)
        self.stats_box.set_margin_end(16)
        self.stats_box.set_margin_top(4)

        self.stats_lbl = Gtk.Label(label="Scanning applications...")
        self.stats_lbl.set_halign(Gtk.Align.START)
        self.stats_lbl.add_css_class("dim-label")
        self.stats_box.append(self.stats_lbl)
        vbox.append(self.stats_box)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.add_css_class("boxed-list")
        self.list_box.set_margin_start(12)
        self.list_box.set_margin_end(12)
        self.list_box.set_margin_bottom(12)
        self.list_box.connect("row-selected", self._on_list_row_selected)
        scrolled.set_child(self.list_box)
        vbox.append(scrolled)

        self.no_results_page = Adw.StatusPage()
        self.no_results_page.set_icon_name("system-search-symbolic")
        self.no_results_page.set_title("No Applications Found")
        self.no_results_page.set_description("Try searching with different keywords or switch filters.")
        self.no_results_page.set_visible(False)
        vbox.append(self.no_results_page)

        self.action_bar = Gtk.ActionBar()
        self.action_bar.set_revealed(False)

        self.batch_count_lbl = Gtk.Label(label="0 apps selected")
        self.action_bar.pack_start(self.batch_count_lbl)

        batch_select_all = Gtk.Button.new_with_label("Select All")
        batch_select_all.add_css_class("flat")
        batch_select_all.connect("clicked", lambda b: self._set_all_selected(True))
        self.action_bar.pack_start(batch_select_all)

        batch_desel_all = Gtk.Button.new_with_label("Clear")
        batch_desel_all.add_css_class("flat")
        batch_desel_all.connect("clicked", lambda b: self._set_all_selected(False))
        self.action_bar.pack_start(batch_desel_all)

        self.batch_uninstall_btn = Gtk.Button.new_with_label("Uninstall Selected")
        self.batch_uninstall_btn.add_css_class("suggested-action")
        self.batch_uninstall_btn.add_css_class("destructive-action")
        self.batch_uninstall_btn.connect("clicked", self._on_batch_uninstall_clicked)
        self.action_bar.pack_end(self.batch_uninstall_btn)

        toolbar_view.add_bottom_bar(self.action_bar)
        self.filter_buttons["all"].set_active(True)

        return toolbar_view

    def _create_detail_content(self) -> Gtk.Widget:
        toolbar_view = Adw.ToolbarView()

        self.detail_header = Adw.HeaderBar()
        self.detail_header.set_show_title(True)

        self.detail_title = Adw.WindowTitle(title="App Inspector", subtitle="")
        self.detail_header.set_title_widget(self.detail_title)

        toolbar_view.add_top_bar(self.detail_header)
        toolbar_view.set_content(self.detail_view)

        return toolbar_view

    def _update_detail_title(self, app: Optional[AppItem]):
        if app:
            self.detail_title.set_title(app.name)
            self.detail_title.set_subtitle(f"{app.backend_display} • {app.id}")
            self.detail_page.set_title(app.name)
        else:
            self.detail_title.set_title("App Inspector")
            self.detail_title.set_subtitle("")
            self.detail_page.set_title("App Inspector")

    def _setup_shortcuts(self):
        act_sort_name = Gio.SimpleAction.new("sort_name", None)
        act_sort_name.connect("activate", lambda a, p: self._set_sort("name"))
        self.add_action(act_sort_name)

        act_sort_size = Gio.SimpleAction.new("sort_size", None)
        act_sort_size.connect("activate", lambda a, p: self._set_sort("size"))
        self.add_action(act_sort_size)

        act_nodisplay = Gio.SimpleAction.new("toggle_nodisplay", None)
        act_nodisplay.connect("activate", lambda a, p: self._toggle_nodisplay())
        self.add_action(act_nodisplay)

        act_about = Gio.SimpleAction.new("about", None)
        act_about.connect("activate", lambda a, p: self._show_about())
        self.add_action(act_about)

    def reload_apps(self):
        self.stats_lbl.set_label("Scanning installed applications across Flatpak, RPM, Snap...")

        def worker():
            apps = AppDetector.discover_all_apps(include_nodisplay=self.include_nodisplay)
            GLib.idle_add(self._on_apps_loaded, apps)

        threading.Thread(target=worker, daemon=True).start()

    def _on_apps_loaded(self, apps: List[AppItem]):
        self.all_apps = apps
        if self.detail_view.current_app and not any(a.id == self.detail_view.current_app.id for a in apps):
            self.detail_view.clear()
            self._update_detail_title(None)
        self._apply_filters()
        self.show_toast(f"Loaded {len(apps)} installed applications.")

    def _apply_filters(self):
        query = self.search_entry.get_text().strip().lower()

        filtered = []
        for a in self.all_apps:
            if self.active_category == "flatpak" and a.backend != "flatpak":
                continue
            elif self.active_category == "system" and a.backend not in ["rpm", "deb", "pacman", "system"]:
                continue
            elif self.active_category == "snap" and a.backend != "snap":
                continue
            elif self.active_category == "appimage" and a.backend not in ["appimage", "custom"]:
                continue

            if query and query not in a.get_search_terms():
                continue

            filtered.append(a)

        if self.sort_by == "size":
            filtered.sort(key=lambda a: -a.installed_size)
        else:
            filtered.sort(key=lambda a: a.name.lower())

        self.filtered_apps = filtered
        self._populate_list()
        self._update_stats_label()

    def _populate_list(self):
        if not hasattr(self, "list_box") or self.list_box is None:
            return

        while self.list_box.get_first_child():
            self.list_box.remove(self.list_box.get_first_child())

        if not self.filtered_apps:
            self.no_results_page.set_visible(True)
            self.list_box.set_visible(False)
            return

        self.no_results_page.set_visible(False)
        self.list_box.set_visible(True)

        for app in self.filtered_apps:
            row = AppRow(
                app=app,
                on_inspect=self._on_app_inspect,
                on_uninstall=self._launch_uninstaller,
                on_select_toggle=self._on_app_selected_toggle
            )
            row.set_batch_mode(self.batch_mode)
            if app.id in self.selected_app_items:
                row.set_selected(True)
            self.list_box.append(row)

    def _update_stats_label(self):
        total_count = len(self.all_apps)
        flatpak_count = sum(1 for a in self.all_apps if a.backend == "flatpak")
        sys_count = sum(1 for a in self.all_apps if a.backend in ["rpm", "deb", "pacman", "system"])
        total_size = sum(a.installed_size for a in self.all_apps)

        self.stats_lbl.set_label(
            f"{total_count} Apps Total ({format_bytes(total_size)}) • {flatpak_count} Flatpaks • {sys_count} System"
        )

    def _on_search_changed(self, entry):
        self._apply_filters()

    def _on_category_changed(self, cat_id: str, active: bool):
        if not active:
            return
        for cid, btn in self.filter_buttons.items():
            if cid != cat_id and btn.get_active():
                btn.set_active(False)
        self.active_category = cat_id
        self._apply_filters()

    def _set_sort(self, sort_type: str):
        self.sort_by = sort_type
        self._apply_filters()

    def _toggle_nodisplay(self):
        self.include_nodisplay = not self.include_nodisplay
        self.reload_apps()

    def _on_batch_mode_toggled(self, btn):
        self.batch_mode = btn.get_active()
        self.action_bar.set_revealed(self.batch_mode)

        child = self.list_box.get_first_child()
        while child:
            if isinstance(child, AppRow):
                child.set_batch_mode(self.batch_mode)
            child = child.get_next_sibling()

        self._update_batch_bar()

    def _on_app_selected_toggle(self, app: AppItem, selected: bool):
        if selected:
            self.selected_app_items.add(app.id)
        else:
            self.selected_app_items.discard(app.id)
        self._update_batch_bar()

    def _set_all_selected(self, select: bool):
        child = self.list_box.get_first_child()
        while child:
            if isinstance(child, AppRow):
                child.set_selected(select)
            child = child.get_next_sibling()
        if not select:
            self.selected_app_items.clear()
        self._update_batch_bar()

    def _update_batch_bar(self):
        count = len(self.selected_app_items)
        self.batch_count_lbl.set_label(f"{count} apps selected")
        self.batch_uninstall_btn.set_sensitive(count > 0)

    def _on_list_row_selected(self, list_box, row):
        if isinstance(row, AppRow):
            self.detail_view.load_app(row.app)
            self._update_detail_title(row.app)
            self.split_view.set_show_content(True)

    def _on_app_inspect(self, app: AppItem):
        self.detail_view.load_app(app)
        self._update_detail_title(app)
        self.split_view.set_show_content(True)

    def _launch_uninstaller(self, app: AppItem):
        wizard = UninstallDialog(self, app, on_complete_refresh=self.reload_apps)
        wizard.present()

    def _on_batch_uninstall_clicked(self, btn):
        selected_apps = [a for a in self.all_apps if a.id in self.selected_app_items]
        if not selected_apps:
            return
        batch_dlg = BatchUninstallDialog(self, selected_apps, on_complete_refresh=self.reload_apps)
        batch_dlg.present()

    def show_toast(self, text: str):
        toast = Adw.Toast.new(text)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)

    def _show_about(self):
        dialog = Adw.AboutDialog()
        dialog.set_application_name("Gnome App Manager")
        dialog.set_application_icon("system-software-install")
        dialog.set_version("1.0.0")
        dialog.set_developer_name("tiwut")
        dialog.set_developers(["tiwut <https://github.com/tiwut>"])
        dialog.set_website("https://github.com/tiwut")
        dialog.set_license_type(Gtk.License.GPL_3_0)
        dialog.set_comments(
            GLib.markup_escape_text(
                "Native GTK4 and Libadwaita application manager and deep residual cleaner for Linux, "
                "replicating Revo Uninstaller functionality across Flatpak, RPM, DEB, Pacman, Snap, and AppImages."
            )
        )
        dialog.present(self)
