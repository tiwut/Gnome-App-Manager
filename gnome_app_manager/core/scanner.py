import glob
import os
import re
import shlex
from typing import List, Set, Dict, Optional

from ..models.app_info import AppItem
from ..models.location_info import StorageLocation, LeftoverItem, LocationCategory
from .utils import get_path_size_and_count, is_root_needed

CRITICAL_PROTECTED_PATHS = {
    "/", "/bin", "/sbin", "/lib", "/lib64", "/usr", "/usr/bin", "/usr/sbin",
    "/usr/lib", "/usr/lib64", "/usr/share", "/usr/local", "/usr/local/bin",
    "/usr/local/lib", "/usr/local/share", "/etc", "/etc/xdg", "/etc/systemd",
    "/var", "/var/lib", "/var/log", "/var/cache", "/var/spool", "/tmp", "/run",
    "/dev", "/proc", "/sys", "/boot", "/home", "/root", "/opt", "/srv", "/mnt",
    os.path.expanduser("~"),
    os.path.expanduser("~/.config"),
    os.path.expanduser("~/.cache"),
    os.path.expanduser("~/.local"),
    os.path.expanduser("~/.local/share"),
    os.path.expanduser("~/.local/state"),
    os.path.expanduser("~/.local/share/applications"),
    os.path.expanduser("~/.var"),
    os.path.expanduser("~/.var/app"),
    os.path.expanduser("~/snap"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
}


class ResidualScanner:
    @classmethod
    def generate_app_tokens(cls, app: AppItem) -> Set[str]:
        tokens = set()

        def add_clean(s: Optional[str]):
            if not s:
                return
            s_clean = s.strip()
            if len(s_clean) >= 3:
                tokens.add(s_clean)
                tokens.add(s_clean.lower())
                slug = re.sub(r'[^a-zA-Z0-9]', '-', s_clean).strip('-')
                if len(slug) >= 3:
                    tokens.add(slug.lower())
                underscore = re.sub(r'[^a-zA-Z0-9]', '_', s_clean).strip('_')
                if len(underscore) >= 3:
                    tokens.add(underscore.lower())
                condensed = re.sub(r'[^a-zA-Z0-9]', '', s_clean)
                if len(condensed) >= 3:
                    tokens.add(condensed.lower())

        add_clean(app.id)

        if "." in app.id:
            parts = app.id.split(".")
            for p in parts:
                if len(p) >= 3 and p not in ["org", "com", "net", "io", "app", "dev", "ai"]:
                    add_clean(p)

        add_clean(app.name)

        if app.package_name:
            add_clean(app.package_name)

        if app.desktop_file:
            base = os.path.basename(app.desktop_file).replace(".desktop", "")
            add_clean(base)

        if app.exec_cmd:
            try:
                parts = shlex.split(app.exec_cmd)
                if parts:
                    bin_name = os.path.basename(parts[0])
                    add_clean(bin_name)
            except Exception:
                pass

        generic_blacklist = {
            "application", "manager", "system", "gnome", "desktop", "client",
            "launcher", "editor", "viewer", "player", "tool", "stable",
            "release", "linux", "default", "install", "installer", "origin",
            "fedora", "ubuntu", "debian", "arch", "flatpak", "snap"
        }
        filtered = {t for t in tokens if t.lower() not in generic_blacklist and len(t) >= 3}
        return filtered

    @classmethod
    def is_safe_to_touch(cls, path: str) -> bool:
        if not path:
            return False
        norm = os.path.realpath(os.path.abspath(os.path.expanduser(path)))
        if norm in CRITICAL_PROTECTED_PATHS:
            return False
        if norm.count("/") <= 1:
            return False
        if norm == os.path.realpath(os.path.expanduser("~")):
            return False
        return True

    @classmethod
    def inspect_app_storage(cls, app: AppItem) -> List[StorageLocation]:
        locations_map: Dict[str, StorageLocation] = {}

        from ..backends.detector import AppDetector
        backend_locs = AppDetector.get_storage_locations(app)
        for loc in backend_locs:
            if cls.is_safe_to_touch(loc.path):
                locations_map[loc.path] = loc

        tokens = cls.generate_app_tokens(app)
        home = os.path.expanduser("~")

        user_bases = [
            (os.path.join(home, ".config"), LocationCategory.CONFIG, "User configuration directory"),
            (os.path.join(home, ".cache"), LocationCategory.CACHE, "User cache and temporary data"),
            (os.path.join(home, ".local", "share"), LocationCategory.DATA, "Local application documents and state"),
            (os.path.join(home, ".local", "state"), LocationCategory.DATA, "Application state and logs"),
            (os.path.join(home, ".var", "app"), LocationCategory.SANDBOX, "Flatpak user sandbox storage"),
            (os.path.join(home, "snap"), LocationCategory.SANDBOX, "Snap user data directory"),
        ]

        for base_dir, cat, desc in user_bases:
            if not os.path.exists(base_dir):
                continue
            for token in tokens:
                target = os.path.join(base_dir, token)
                if os.path.exists(target) and target not in locations_map and cls.is_safe_to_touch(target):
                    size, count = get_path_size_and_count(target)
                    locations_map[target] = StorageLocation(
                        path=target,
                        category=cat,
                        description=desc,
                        exists=True,
                        size_bytes=size,
                        is_directory=os.path.isdir(target),
                        requires_root=False,
                        item_count=count
                    )

        for token in tokens:
            dot_path = os.path.join(home, f".{token}")
            if os.path.exists(dot_path) and dot_path not in locations_map and cls.is_safe_to_touch(dot_path):
                size, count = get_path_size_and_count(dot_path)
                locations_map[dot_path] = StorageLocation(
                    path=dot_path,
                    category=LocationCategory.CONFIG,
                    description="Legacy home dotfile/folder",
                    exists=True,
                    size_bytes=size,
                    is_directory=os.path.isdir(dot_path),
                    requires_root=False,
                    item_count=count
                )

        shortcut_targets = [
            os.path.join(home, ".local", "share", "applications", f"{app.id}.desktop"),
            os.path.join(home, "Desktop", f"{app.id}.desktop"),
            os.path.join(home, ".config", "autostart", f"{app.id}.desktop"),
            os.path.join(home, ".config", "systemd", "user", f"{app.id}.service"),
        ]
        if app.desktop_file:
            shortcut_targets.append(app.desktop_file)

        for token in tokens:
            shortcut_targets.append(os.path.join(home, ".config", "autostart", f"{token}.desktop"))
            shortcut_targets.append(os.path.join(home, ".config", "systemd", "user", f"{token}.service"))
            shortcut_targets.append(os.path.join(home, "Desktop", f"{token}.desktop"))

        for st in set(shortcut_targets):
            if os.path.exists(st) and st not in locations_map and cls.is_safe_to_touch(st):
                size, count = get_path_size_and_count(st)
                cat = LocationCategory.SERVICES if ("autostart" in st or "systemd" in st) else LocationCategory.SHORTCUTS
                locations_map[st] = StorageLocation(
                    path=st,
                    category=cat,
                    description="Launcher or background autostart entry",
                    exists=True,
                    size_bytes=size,
                    is_directory=False,
                    requires_root=is_root_needed(st),
                    item_count=1
                )

        system_bases = [
            ("/etc", LocationCategory.SYSTEM_ETC, "System configuration folder"),
            ("/etc/xdg/autostart", LocationCategory.SERVICES, "System-wide autostart launcher"),
            ("/etc/systemd/system", LocationCategory.SERVICES, "Systemd system unit"),
            ("/var/lib", LocationCategory.SYSTEM_LIB, "System package data"),
            ("/var/log", LocationCategory.SYSTEM_LIB, "System log files"),
            ("/var/cache", LocationCategory.CACHE, "System cache"),
            ("/opt", LocationCategory.SYSTEM_LIB, "Application installation directory"),
            ("/usr/share", LocationCategory.SYSTEM_LIB, "Application shared data and assets"),
        ]

        for sys_base, cat, desc in system_bases:
            if not os.path.exists(sys_base):
                continue
            for token in tokens:
                target = os.path.join(sys_base, token)
                if os.path.exists(target) and target not in locations_map and cls.is_safe_to_touch(target):
                    size, count = get_path_size_and_count(target)
                    locations_map[target] = StorageLocation(
                        path=target,
                        category=cat,
                        description=desc,
                        exists=True,
                        size_bytes=size,
                        is_directory=os.path.isdir(target),
                        requires_root=is_root_needed(target),
                        item_count=count
                    )

        return sorted(
            list(locations_map.values()),
            key=lambda l: (not l.exists, -l.size_bytes, l.category.value)
        )

    @classmethod
    def scan_leftovers(cls, app: AppItem, mode: str = "moderate") -> List[LeftoverItem]:
        tokens = cls.generate_app_tokens(app)
        home = os.path.expanduser("~")
        leftovers: Dict[str, LeftoverItem] = {}

        def add_leftover(path: str, cat: LocationCategory, reason: str):
            if not os.path.exists(path):
                return
            if not cls.is_safe_to_touch(path):
                return
            if path in leftovers:
                return

            size, _ = get_path_size_and_count(path)
            is_dir = os.path.isdir(path)
            req_root = is_root_needed(path)

            leftovers[path] = LeftoverItem(
                path=path,
                category=cat,
                size_bytes=size,
                is_directory=is_dir,
                requires_root=req_root,
                selected=True,
                reason=reason
            )

        if app.backend == "flatpak" or "flatpak" in app.origin.lower():
            sandbox = os.path.join(home, ".var", "app", app.id)
            add_leftover(sandbox, LocationCategory.SANDBOX, "Residual Flatpak user sandbox data and configs")
            user_override = os.path.join(home, ".local", "share", "flatpak", "overrides", app.id)
            add_leftover(user_override, LocationCategory.CONFIG, "Flatpak user permission override")

        for token in tokens:
            cache_p = os.path.join(home, ".cache", token)
            add_leftover(cache_p, LocationCategory.CACHE, f"User cache matching '{token}'")

        for token in tokens:
            cfg_p = os.path.join(home, ".config", token)
            add_leftover(cfg_p, LocationCategory.CONFIG, f"User configuration folder matching '{token}'")

        if mode in ["moderate", "deep", "advanced"]:
            for token in tokens:
                share_p = os.path.join(home, ".local", "share", token)
                add_leftover(share_p, LocationCategory.DATA, f"Local application data folder for '{token}'")
                state_p = os.path.join(home, ".local", "state", token)
                add_leftover(state_p, LocationCategory.DATA, f"Application state and log folder for '{token}'")

            for token in tokens:
                df1 = os.path.join(home, f".{token}")
                add_leftover(df1, LocationCategory.CONFIG, f"Legacy dotfile/folder in home directory (~/.{token})")
                df2 = os.path.join(home, f".{token}rc")
                add_leftover(df2, LocationCategory.CONFIG, f"Legacy rc configuration file (~/.{token}rc)")

            desktop_patterns = [
                os.path.join(home, ".local", "share", "applications", f"{app.id}.desktop"),
                os.path.join(home, "Desktop", f"{app.id}.desktop"),
            ]
            for token in tokens:
                desktop_patterns.append(os.path.join(home, ".local", "share", "applications", f"*{token}*.desktop"))
                desktop_patterns.append(os.path.join(home, "Desktop", f"*{token}*.desktop"))

            for pat in desktop_patterns:
                for match in glob.glob(pat):
                    add_leftover(match, LocationCategory.SHORTCUTS, "User desktop application launcher")

            for token in tokens:
                for match in glob.glob(os.path.join(home, ".config", "autostart", f"*{token}*.desktop")):
                    add_leftover(match, LocationCategory.SERVICES, "User session autostart entry")
                for match in glob.glob(os.path.join(home, ".config", "systemd", "user", f"*{token}*.service")):
                    add_leftover(match, LocationCategory.SERVICES, "User systemd background daemon")
                for match in glob.glob(os.path.join(home, ".config", "systemd", "user", f"*{token}*.timer")):
                    add_leftover(match, LocationCategory.SERVICES, "User systemd timer schedule")

            for token in tokens:
                snap_u = os.path.join(home, "snap", token)
                add_leftover(snap_u, LocationCategory.SANDBOX, "Residual snap data in home folder")

        if mode in ["deep", "advanced"]:
            for token in tokens:
                etc_p = os.path.join("/etc", token)
                add_leftover(etc_p, LocationCategory.SYSTEM_ETC, f"Residual system configuration folder in /etc/{token}")
                etc_conf = os.path.join("/etc", f"{token}.conf")
                add_leftover(etc_conf, LocationCategory.SYSTEM_ETC, f"Residual system config file (/etc/{token}.conf)")
                etc_def = os.path.join("/etc", "default", token)
                add_leftover(etc_def, LocationCategory.SYSTEM_ETC, f"System default environment file (/etc/default/{token})")
                etc_xdg = os.path.join("/etc", "xdg", token)
                add_leftover(etc_xdg, LocationCategory.SYSTEM_ETC, f"Global XDG configuration in /etc/xdg/{token}")

                for match in glob.glob(f"/etc/xdg/autostart/*{token}*.desktop"):
                    add_leftover(match, LocationCategory.SERVICES, "System-wide autostart launcher")
                for match in glob.glob(f"/etc/systemd/system/*{token}*.service"):
                    add_leftover(match, LocationCategory.SERVICES, "Systemd service definition")

            for token in tokens:
                for base, cat, desc in [
                    (f"/var/lib/{token}", LocationCategory.SYSTEM_LIB, f"Variable package data in /var/lib/{token}"),
                    (f"/var/log/{token}", LocationCategory.SYSTEM_LIB, f"Application log files in /var/log/{token}"),
                    (f"/var/cache/{token}", LocationCategory.CACHE, f"System cache directory in /var/cache/{token}"),
                    (f"/opt/{token}", LocationCategory.SYSTEM_LIB, f"Application installation folder in /opt/{token}"),
                    (f"/usr/share/{token}", LocationCategory.SYSTEM_LIB, f"Application shared resources in /usr/share/{token}"),
                    (f"/usr/local/share/{token}", LocationCategory.SYSTEM_LIB, f"Local application assets in /usr/local/share/{token}"),
                ]:
                    add_leftover(base, cat, desc)

            for token in tokens:
                for match in glob.glob(f"/usr/share/bash-completion/completions/*{token}*"):
                    add_leftover(match, LocationCategory.SYSTEM_LIB, "Bash shell command completion")
                for match in glob.glob(f"/usr/share/zsh/site-functions/*{token}*"):
                    add_leftover(match, LocationCategory.SYSTEM_LIB, "Zsh shell command completion")
                for match in glob.glob(f"/usr/share/fish/vendor_completions.d/*{token}*.fish"):
                    add_leftover(match, LocationCategory.SYSTEM_LIB, "Fish shell command completion")
                for match in glob.glob(f"/usr/share/pixmaps/*{token}*"):
                    add_leftover(match, LocationCategory.ICONS, "Application icon in /usr/share/pixmaps")
                for match in glob.glob(os.path.join(home, ".local", "share", "icons", "**", f"*{token}*")):
                    add_leftover(match, LocationCategory.ICONS, "User cached icon")

        if app.desktop_file and os.path.exists(app.desktop_file):
            add_leftover(app.desktop_file, LocationCategory.SHORTCUTS, "Original desktop application launcher")

        return sorted(
            list(leftovers.values()),
            key=lambda item: (item.requires_root, item.category.value, -item.size_bytes)
        )
