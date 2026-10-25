from gi.repository import Gtk, Adw, GLib
from typing import List, Callable, Optional
from ..models.app_info import AppItem
from .uninstall_dialog import UninstallDialog


class BatchUninstallDialog(Adw.Window):
    def __init__(self, parent_window: Gtk.Window, apps: List[AppItem], on_complete_refresh: Optional[Callable[[], None]] = None):
        super().__init__()
        self.set_transient_for(parent_window)
        self.set_modal(True)
        self.set_default_size(600, 480)
        self.set_title("Batch Uninstallation")

        self.parent_window = parent_window
        self.apps = list(apps)
        self.on_complete_refresh = on_complete_refresh
        self.current_index = 0

        self.toolbar_view = Adw.ToolbarView()
        self.set_content(self.toolbar_view)

        header = Adw.HeaderBar()
        self.toolbar_view.add_top_bar(header)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(550)
        self.toolbar_view.set_content(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(20)
        box.set_margin_end(20)
        clamp.set_child(box)

        title = Gtk.Label(label=f"Uninstall {len(self.apps)} Applications")
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        box.append(title)

        desc = Gtk.Label(label="Each application will be uninstalled using its native uninstaller followed by a residual leftover scan.")
        desc.set_halign(Gtk.Align.START)
        desc.set_wrap(True)
        desc.add_css_class("dim-label")
        box.append(desc)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_min_content_height(240)

        group = Adw.PreferencesGroup()
        group.set_title("Queue for Removal")

        for app in self.apps:
            row = Adw.ActionRow()
            row.set_title(GLib.markup_escape_text(app.name))
            row.set_subtitle(GLib.markup_escape_text(f"{app.backend_display} • {app.id}"))
            icon = Gtk.Image.new_from_icon_name(app.icon_name or "application-x-executable")
            row.add_prefix(icon)
            group.add(row)

        scrolled.set_child(group)
        box.append(scrolled)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button.new_with_label("Cancel")
        cancel_btn.connect("clicked", lambda b: self.close())
        btn_box.append(cancel_btn)

        start_btn = Gtk.Button.new_with_label("Begin Batch Process")
        start_btn.add_css_class("suggested-action")
        start_btn.add_css_class("destructive-action")
        start_btn.connect("clicked", self._start_batch)
        btn_box.append(start_btn)

        box.append(btn_box)

    def _start_batch(self, btn):
        self.close()
        self._run_next_app()

    def _run_next_app(self):
        if self.current_index < len(self.apps):
            app = self.apps[self.current_index]
            self.current_index += 1

            def on_app_done():
                self._run_next_app()

            wizard = UninstallDialog(self.parent_window, app, on_complete_refresh=on_app_done)
            wizard.present()
        else:
            if self.on_complete_refresh:
                self.on_complete_refresh()
