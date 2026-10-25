import os
from typing import Callable, Optional
from gi.repository import Gtk, Adw, GdkPixbuf, Gio, GLib
from ..models.app_info import AppItem


class AppRow(Adw.ActionRow):
    def __init__(
        self,
        app: AppItem,
        on_inspect: Optional[Callable[[AppItem], None]] = None,
        on_uninstall: Optional[Callable[[AppItem], None]] = None,
        on_select_toggle: Optional[Callable[[AppItem, bool], None]] = None
    ):
        super().__init__()
        self.app = app
        self.on_inspect = on_inspect
        self.on_uninstall = on_uninstall
        self.on_select_toggle = on_select_toggle

        self.set_title(GLib.markup_escape_text(app.name))
        subtitle_parts = []
        if app.version and app.version != "Unknown":
            subtitle_parts.append(f"v{app.version}")
        subtitle_parts.append(app.id)
        if app.summary:
            clean_summary = app.summary[:60] + "..." if len(app.summary) > 60 else app.summary
            subtitle_parts.append(f"• {clean_summary}")
        self.set_subtitle(GLib.markup_escape_text(" ".join(subtitle_parts)))

        self.icon_image = Gtk.Image.new_from_icon_name(app.icon_name or "application-x-executable")
        self.icon_image.set_pixel_size(36)
        self.icon_image.add_css_class("app-icon")

        if app.icon_name and os.path.isabs(app.icon_name) and os.path.exists(app.icon_name):
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(app.icon_name, 36, 36, True)
                self.icon_image.set_from_pixbuf(pb)
            except Exception:
                pass

        self.add_prefix(self.icon_image)

        self.check_btn = Gtk.CheckButton()
        self.check_btn.set_valign(Gtk.Align.CENTER)
        self.check_btn.set_visible(False)
        self.check_btn.connect("toggled", self._on_checkbox_toggled)
        self.add_prefix(self.check_btn)

        suffix_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        suffix_box.set_valign(Gtk.Align.CENTER)

        backend_lbl = Gtk.Label(label=app.backend_display)
        backend_lbl.add_css_class("badge-pill")
        backend_lbl.add_css_class(f"badge-{app.backend}")
        suffix_box.append(backend_lbl)

        if app.installed_size > 0:
            size_lbl = Gtk.Label(label=app.formatted_size)
            size_lbl.add_css_class("size-pill")
            suffix_box.append(size_lbl)

        inspect_btn = Gtk.Button.new_from_icon_name("document-properties-symbolic")
        inspect_btn.set_tooltip_text("Inspect Storage & Data Locations")
        inspect_btn.add_css_class("flat")
        inspect_btn.connect("clicked", self._on_inspect_clicked)
        suffix_box.append(inspect_btn)

        uninstall_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        uninstall_btn.set_tooltip_text("Uninstall & Clean Leftovers")
        uninstall_btn.add_css_class("flat")
        uninstall_btn.add_css_class("destructive-action")
        uninstall_btn.connect("clicked", self._on_uninstall_clicked)
        suffix_box.append(uninstall_btn)

        self.add_suffix(suffix_box)
        self.set_activatable(True)
        self.connect("activated", self._on_row_activated)

    def set_batch_mode(self, enabled: bool):
        self.check_btn.set_visible(enabled)
        if not enabled:
            self.check_btn.set_active(False)

    def is_selected(self) -> bool:
        return self.check_btn.get_active()

    def set_selected(self, val: bool):
        self.check_btn.set_active(val)

    def _on_checkbox_toggled(self, btn):
        if self.on_select_toggle:
            self.on_select_toggle(self.app, btn.get_active())

    def _on_inspect_clicked(self, btn):
        if self.on_inspect:
            self.on_inspect(self.app)

    def _on_uninstall_clicked(self, btn):
        if self.on_uninstall:
            self.on_uninstall(self.app)

    def _on_row_activated(self, row):
        if self.check_btn.get_visible():
            self.check_btn.set_active(not self.check_btn.get_active())
        elif self.on_inspect:
            self.on_inspect(self.app)
