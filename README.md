# Gnome App Manager

### Modern GTK4 \& Libadwaita Revo-Style Uninstaller \& Storage Inspector for Linux

**Gnome App Manager** is a native, state-of-the-art GNOME application built with **GTK4** and **Libadwaita** that replicates and elevates the **Revo Uninstaller** experience on Linux.

It discovers all installed applications across **Flatpak**, **RPM / DNF**, **Debian / APT**, **Arch / Pacman**, **Canonical Snap**, and standalone **AppImages**, inspects **where every single app stores its data**, and executes clean removals with deep residual scans for lingering files, folders, and system entries.

---

## One-Line Quick Install (Any Linux Distro)

To install **Gnome App Manager** on any Linux distribution (Fedora, Ubuntu, Debian, Arch Linux, openSUSE, etc.), run:

```
curl -fsSL https://raw.githubusercontent.com/tiwut/Gnome-App-Manager/main/install.sh | bash
```

*or:*

```
bash -c "$(curl -fsSL https://raw.githubusercontent.com/tiwut/Gnome-App-Manager/main/install.sh)"
```

This universal installer automatically:

1. Detects your distribution package manager (`dnf`, `apt`, `pacman`, `zypper`) and ensures runtime dependencies (`python3-gobject`, `gtk4`, `libadwaita`, `git`) are present.
2. Clones or updates the repository to `~/.local/share/gnome-app-manager`.
3. Installs the SVG application icon and `.desktop` launcher to your user application menu.
4. Creates a `gnome-app-manager` binary symlink in `~/.local/bin/`.

---

## Running Locally

If running from source:

```
./run.sh
```

or:

```
python3 main.py
```

To install from local source:

```
./install.sh
```

---

## Features

- **Multi-Backend Package Discovery**:
    - **Flatpak**: User \& system runtimes, sandbox sizes, origins (`flathub`, `fedora`).
    - **RPM / DNF**: Batch querying of RPM package ownership, file lists, and sizes.
    - **Debian / APT**: Package mapping via `dpkg` and purging with `apt-get purge`.
    - **Arch / Pacman**: Clean dependency removal via `pacman -Rns`.
    - **Snap**: Integration with `snap list` and `--purge` removal.
    - **AppImages \& Standalone Apps**: Discovers standalone `.desktop` files, binary executables, and AppImage wrappers.
- **Data Storage Inspector ("Where does each app store its data?")**:
    - **User Configuration**: `~/.config/<app>`, `~/.config/<vendor>/<app>`, `~/.<app>`, `~/.<app>rc`
    - **User Cache \& Temp**: `~/.cache/<app>`, `~/.cache/<vendor>/<app>`
    - **Local State \& Shared Data**: `~/.local/share/<app>`, `~/.local/state/<app>`
    - **Container Sandbox**: `~/.var/app/<app-id>` (Flatpak sandbox environments) \& `~/snap/<app>`
    - **Desktop Shortcuts \& Launchers**: `~/.local/share/applications/`, `/usr/share/applications/`, `~/Desktop/`
    - **Autostart \& Daemons**: `~/.config/autostart/`, `/etc/xdg/autostart/`, `~/.config/systemd/user/`
    - **System Configuration**: `/etc/<app>`, `/etc/<app>.conf`, `/etc/default/<app>`, `/etc/xdg/`
    - **System Libraries \& Var Data**: `/var/lib/<app>`, `/var/log/<app>`, `/var/cache/<app>`, `/opt/<app>`, `/usr/share/<app>`
    - **Icons, MIME, \& Completions**: `/usr/share/icons/`, `/usr/share/pixmaps/`, `/usr/share/bash-completion/`
- **Revo Uninstaller-Style Multi-Stage Wizard**:
    - **Profile Selection**: Safe, Moderate (Recommended), and Advanced / Deep scan profiles.
    - **Native Uninstaller Execution**: Embedded terminal streaming live output from `flatpak`, `dnf`, `apt`, etc.
    - **Deep Residual Leftover Scanner**: Finds orphan files and folders left behind.
    - **Interactive Review**: Categorized lists with checkboxes, file sizes, and root permission indicators.
    - **Clean Removal**: Deletes selected items with a single administrator prompt for system files.
- **Multi-App Batch Uninstaller**:
    - Select multiple applications using the checklist toggle to queue and batch uninstall.
