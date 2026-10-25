import os
import subprocess
from gi.repository import Gtk, Adw, GdkPixbuf, Gdk, Gio, GLib
from typing import Callable, Optional, List

from ..models.app_info import AppItem
from ..models.location_info import StorageLocation, LocationCategory
from ..core.scanner import ResidualScanner
from ..core.utils import format_bytes


class AppDetailView(Gtk.ScrolledWindow):
    def __init__(self, on_uninstall: Optional[Callable[[AppItem], None]] = None):
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.on_uninstall = on_uninstall
        self.current_app: Optional[AppItem] = None

        self.clamp = Adw.Clamp()
        self.clamp.set_maximum_size(900)
        self.clamp.set_tightening_threshold(700)
        self.set_child(self.clamp)

        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.content_box.set_margin_top(24)
        self.content_box.set_margin_bottom(36)
        self.content_box.set_margin_start(16)
        self.content_box.set_margin_end(16)
        self.clamp.set_child(self.content_box)

        self.placeholder = Adw.StatusPage()
        self.placeholder.set_icon_name("document-properties-symbolic")
        self.placeholder.set_title("No Application Selected")
        self.placeholder.set_description("Select an application from the list to inspect its storage locations, configuration files, and system entries.")
        self.content_box.append(self.placeholder)

    def clear(self):
        self.current_app = None
        while self.content_box.get_first_child():
            self.content_box.remove(self.content_box.get_first_child())
        self.content_box.append(self.placeholder)

    def load_app(self, app: AppItem):
        self.current_app = app

        while self.content_box.get_first_child():
            self.content_box.remove(self.content_box.get_first_child())

        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        hero.add_css_class("hero-box")

        icon_img = Gtk.Image.new_from_icon_name(app.icon_name or "application-x-executable")
        icon_img.set_pixel_size(64)
        icon_img.add_css_class("app-icon")
        if app.icon_name and os.path.isabs(app.icon_name) and os.path.exists(app.icon_name):
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(app.icon_name, 64, 64, True)
                icon_img.set_from_pixbuf(pb)
            except Exception:
                pass
        hero.append(icon_img)

        meta_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        meta_box.set_hexpand(True)

        title_lbl = Gtk.Label(label=app.name)
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.add_css_class("title-1")
        meta_box.append(title_lbl)

        sub_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sub_box.set_halign(Gtk.Align.START)

        b_lbl = Gtk.Label(label=app.backend_display)
        b_lbl.add_css_class("badge-pill")
        b_lbl.add_css_class(f"badge-{app.backend}")
        sub_box.append(b_lbl)

        if app.version and app.version != "Unknown":
            v_lbl = Gtk.Label(label=f"v{app.version}")
            v_lbl.add_css_class("size-pill")
            sub_box.append(v_lbl)

        if app.installed_size > 0:
            s_lbl = Gtk.Label(label=app.formatted_size)
            s_lbl.add_css_class("size-pill")
            sub_box.append(s_lbl)

        meta_box.append(sub_box)

        id_lbl = Gtk.Label(label=f"Package ID: {app.id}")
        id_lbl.set_halign(Gtk.Align.START)
        id_lbl.add_css_class("dim-label")
        id_lbl.set_wrap(True)
        meta_box.append(id_lbl)

        if app.summary:
            desc_lbl = Gtk.Label(label=app.summary)
            desc_lbl.set_halign(Gtk.Align.START)
            desc_lbl.set_wrap(True)
            meta_box.append(desc_lbl)

        hero.append(meta_box)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        btn_box.set_valign(Gtk.Align.CENTER)

        uninst_btn = Gtk.Button.new_with_label("Uninstall & Clean")
        uninst_btn.set_icon_name("user-trash-symbolic")
        uninst_btn.add_css_class("destructive-action")
        uninst_btn.add_css_class("suggested-action")
        uninst_btn.connect("clicked", lambda b: self._trigger_uninstall())
        btn_box.append(uninst_btn)

        if app.desktop_file:
            open_desk_btn = Gtk.Button.new_with_label("Open Shortcut")
            open_desk_btn.set_icon_name("document-open-symbolic")
            open_desk_btn.add_css_class("flat")
            open_desk_btn.connect("clicked", lambda b: self._open_path(app.desktop_file))
            btn_box.append(open_desk_btn)

        hero.append(btn_box)
        self.content_box.append(hero)

        locations = ResidualScanner.inspect_app_storage(app)

        existing_locs = [l for l in locations if l.exists]
        total_storage = sum(l.size_bytes for l in existing_locs)

        summary_group = Adw.PreferencesGroup()
        summary_group.set_title("Storage Overview")
        summary_group.set_description(
            f"Found {len(existing_locs)} active storage locations consuming approximately {format_bytes(total_storage)}."
        )
        self.content_box.append(summary_group)

        categories_dict = {}
        for loc in locations:
            cat = loc.category
            if cat not in categories_dict:
                categories_dict[cat] = []
            categories_dict[cat].append(loc)

        for cat, cat_locs in categories_dict.items():
            group = Adw.PreferencesGroup()
            group.set_title(GLib.markup_escape_text(cat.value))

            for loc in cat_locs:
                row = Adw.ActionRow()
                row.set_title(GLib.markup_escape_text(loc.path))
                
                perm_text = "Requires Root" if loc.requires_root else "User Accessible"
                desc = f"{loc.description} • {perm_text}"
                row.set_subtitle(GLib.markup_escape_text(desc))

                icon = Gtk.Image.new_from_icon_name(cat.icon_name)
                row.add_prefix(icon)

                s_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                s_box.set_valign(Gtk.Align.CENTER)

                if loc.exists:
                    sz_lbl = Gtk.Label(label=loc.formatted_size)
                    sz_lbl.add_css_class("size-pill")
                    s_box.append(sz_lbl)

                    reveal_btn = Gtk.Button.new_from_icon_name("folder-open-symbolic")
                    reveal_btn.set_tooltip_text("Reveal in File Manager")
                    reveal_btn.add_css_class("flat")
                    reveal_btn.connect("clicked", lambda b, p=loc.path: self._reveal_path(p))
                    s_box.append(reveal_btn)
                else:
                    absent_lbl = Gtk.Label(label="Not Present")
                    absent_lbl.add_css_class("dim-label")
                    s_box.append(absent_lbl)

                copy_btn = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
                copy_btn.set_tooltip_text("Copy Path")
                copy_btn.add_css_class("flat")
                copy_btn.connect("clicked", lambda b, p=loc.path: self._copy_path(p))
                s_box.append(copy_btn)

                row.add_suffix(s_box)
                group.add(row)

            self.content_box.append(group)

    def _trigger_uninstall(self):
        if self.current_app and self.on_uninstall:
            self.on_uninstall(self.current_app)

    def _reveal_path(self, path: str):
        if not os.path.exists(path):
            return
        target = path if os.path.isdir(path) else os.path.dirname(path)
        try:
            subprocess.Popen(["xdg-open", target])
        except Exception:
            pass

    def _open_path(self, path: str):
        if os.path.exists(path):
            try:
                subprocess.Popen(["xdg-open", path])
            except Exception:
                pass

    def _copy_path(self, path: str):
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(path)
