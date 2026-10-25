#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gnome_app_manager.app import GnomeAppManager


def main():
    app = GnomeAppManager()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
