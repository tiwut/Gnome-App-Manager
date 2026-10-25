import os
import sys
from gi.repository import Gtk, Adw, Gio, Gdk

from .ui.window import MainWindow


class GnomeAppManager(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.GnomeAppManager",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )
        self.window: MainWindow = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._load_css()

    def do_activate(self):
        if not self.window:
            self.window = MainWindow(application=self)
        self.window.present()

    def _load_css(self):
        css_file = os.path.join(os.path.dirname(__file__), "ui", "styles.css")
        if os.path.isfile(css_file):
            provider = Gtk.CssProvider()
            try:
                provider.load_from_path(css_file)
                display = Gdk.Display.get_default()
                if display:
                    Gtk.StyleContext.add_provider_for_display(
                        display,
                        provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                    )
            except Exception:
                pass
