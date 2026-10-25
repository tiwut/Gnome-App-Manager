#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/tiwut/gnome-app-manager.git"
INSTALL_DIR="$HOME/.local/share/gnome-app-manager"
APPS_DIR="$HOME/.local/share/applications"
ICONS_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
BIN_DIR="$HOME/.local/bin"

mkdir -p "$APPS_DIR"
mkdir -p "$ICONS_DIR"
mkdir -p "$BIN_DIR"

if [ -f "$(dirname "${BASH_SOURCE[0]}")/main.py" ]; then
    SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    if command -v dnf >/dev/null 2>&1; then
        rpm -q python3-gobject libadwaita gtk4 git >/dev/null 2>&1 || {
            echo "Installing dependencies..."
            pkexec dnf install -y python3-gobject libadwaita gtk4 git || true
        }
    elif command -v apt-get >/dev/null 2>&1; then
        dpkg -s python3-gi gir1.2-adw-1 git >/dev/null 2>&1 || {
            echo "Installing dependencies..."
            pkexec apt-get update && pkexec apt-get install -y python3-gi gir1.2-adw-1 gir1.2-gtk-4.0 git || true
        }
    elif command -v pacman >/dev/null 2>&1; then
        pacman -Qi python-gobject libadwaita git >/dev/null 2>&1 || {
            echo "Installing dependencies..."
            pkexec pacman -Sy --noconfirm python-gobject libadwaita gtk4 git || true
        }
    elif command -v zypper >/dev/null 2>&1; then
        rpm -q python3-gobject typelib-1_0-Adw-1 git >/dev/null 2>&1 || {
            echo "Installing dependencies..."
            pkexec zypper install -y python3-gobject typelib-1_0-Adw-1 typelib-1_0-Gtk-4_0 git || true
        }
    fi

    if [ -d "$INSTALL_DIR/.git" ]; then
        echo "Updating Gnome App Manager..."
        git -C "$INSTALL_DIR" pull --quiet
    else
        echo "Downloading Gnome App Manager..."
        rm -rf "$INSTALL_DIR"
        git clone --quiet --depth=1 "$REPO_URL" "$INSTALL_DIR"
    fi
    SOURCE_DIR="$INSTALL_DIR"
fi

cp "$SOURCE_DIR/data/io.github.GnomeAppManager.svg" "$ICONS_DIR/io.github.GnomeAppManager.svg"

cat <<EOF > "$APPS_DIR/io.github.GnomeAppManager.desktop"
[Desktop Entry]
Name=Gnome App Manager
GenericName=Application Manager & Uninstaller
Comment=Cleanly uninstall applications and purge residual files, caches, and system configs
Exec=$BIN_DIR/gnome-app-manager
Icon=io.github.GnomeAppManager
Terminal=false
Type=Application
Categories=GNOME;GTK;System;Settings;PackageManager;
Keywords=Uninstall;Remove;Cleaner;Revo;Flatpak;RPM;DNF;Cache;Residual;
StartupNotify=true
EOF

cat <<EOF > "$BIN_DIR/gnome-app-manager"
#!/usr/bin/env bash
exec python3 "$SOURCE_DIR/main.py" "\$@"
EOF
chmod +x "$BIN_DIR/gnome-app-manager"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Gnome App Manager successfully installed!"
echo "Developer: github.com/tiwut"
echo "Run 'gnome-app-manager' or find it in your GNOME application menu."
