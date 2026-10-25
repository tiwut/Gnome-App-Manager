import glob
import os
import shutil
import subprocess
from typing import List, Dict, Optional, Tuple

from ..models.app_info import AppItem
from ..models.location_info import StorageLocation
from ..core.utils import parse_desktop_file, get_path_size_and_count
from .flatpak import FlatpakBackend
from .rpm_dnf import RpmDnfBackend
from .deb_apt import DebAptBackend
from .pacman import PacmanBackend
from .snap import SnapBackend
from .standalone import StandaloneBackend


class AppDetector:
    @classmethod
    def discover_all_apps(cls, include_nodisplay: bool = False) -> List[AppItem]:
        all_apps: Dict[str, AppItem] = {}

        flatpaks = FlatpakBackend.list_apps()
        for f_app in flatpaks:
            all_apps[f_app.id] = f_app

        snaps = SnapBackend.list_apps()
        for s_app in snaps:
            all_apps[s_app.id] = s_app

        desktop_dirs = [
            os.path.expanduser("~/.local/share/applications"),
            "/usr/local/share/applications",
            "/usr/share/applications",
        ]

        desktop_files = []
        for d in desktop_dirs:
            if os.path.isdir(d):
                desktop_files.extend(glob.glob(os.path.join(d, "*.desktop")))

        has_rpm = RpmDnfBackend.is_available()
        has_apt = DebAptBackend.is_available()
        has_pacman = PacmanBackend.is_available()

        rpm_batch_info = {}
        if has_rpm:
            rpm_batch_info = RpmDnfBackend.batch_resolve_files(desktop_files)

        covered_desktop_bases = set()
        for f_id in all_apps.keys():
            covered_desktop_bases.add(f_id.lower())
            covered_desktop_bases.add(f"{f_id.lower()}.desktop")

        for df in desktop_files:
            base_name = os.path.basename(df)
            app_key = base_name.replace(".desktop", "")

            if app_key.lower() in covered_desktop_bases or base_name.lower() in covered_desktop_bases:
                for k, existing in all_apps.items():
                    if k.lower() == app_key.lower() and not existing.desktop_file:
                        existing.desktop_file = df
                continue

            entry = parse_desktop_file(df)
            if not entry:
                continue

            if not include_nodisplay:
                if entry.get("NoDisplay", "").lower() == "true":
                    continue
                if entry.get("Type", "Application") != "Application":
                    continue

            name = entry.get("Name")
            if not name:
                continue

            exec_cmd = entry.get("Exec", "")
            icon = entry.get("Icon", "application-x-executable")
            comment = entry.get("Comment", "") or entry.get("GenericName", "")
            categories = [c.strip() for c in entry.get("Categories", "").split(";") if c.strip()]
            keywords = [k.strip() for k in entry.get("Keywords", "").split(";") if k.strip()]

            backend = "system"
            origin = "system"
            package_name = None
            installed_size = 0
            is_user = df.startswith(os.path.expanduser("~"))

            if ".appimage" in exec_cmd.lower() or (df.endswith(".desktop") and "appimage" in df.lower()):
                backend = "appimage"
                origin = "AppImage"
                bin_path = StandaloneBackend.extract_binary_path(
                    AppItem(id=app_key, name=name, exec_cmd=exec_cmd)
                )
                if bin_path and os.path.exists(bin_path):
                    installed_size, _ = get_path_size_and_count(bin_path)
            elif is_user:
                backend = "custom"
                origin = "user"
            elif has_rpm and df in rpm_batch_info:
                info = rpm_batch_info[df]
                backend = "rpm"
                origin = "dnf/rpm"
                package_name = info["name"]
                installed_size = info["size"]
            elif has_apt:
                pkg = DebAptBackend.get_package_for_file(df)
                if pkg:
                    backend = "deb"
                    origin = "apt/dpkg"
                    package_name = pkg
                    installed_size = DebAptBackend.get_package_size(pkg)
            elif has_pacman:
                pkg = PacmanBackend.get_package_for_file(df)
                if pkg:
                    backend = "pacman"
                    origin = "pacman"
                    package_name = pkg

            app_item = AppItem(
                id=app_key,
                name=name,
                version=entry.get("Version", "Unknown"),
                backend=backend,
                origin=origin,
                icon_name=icon,
                desktop_file=df,
                exec_cmd=exec_cmd,
                summary=comment,
                installed_size=installed_size,
                is_user=is_user,
                package_name=package_name,
                categories=categories,
                keywords=keywords,
                raw_data={"desktop_entry": entry}
            )

            all_apps[app_key] = app_item

        return sorted(list(all_apps.values()), key=lambda a: a.name.lower())

    @classmethod
    def get_backend_handler(cls, app: AppItem):
        if app.backend == "flatpak":
            return FlatpakBackend
        elif app.backend == "rpm":
            return RpmDnfBackend
        elif app.backend == "deb":
            return DebAptBackend
        elif app.backend == "pacman":
            return PacmanBackend
        elif app.backend == "snap":
            return SnapBackend
        elif app.backend == "appimage" or app.backend == "custom":
            return StandaloneBackend
        return None

    @classmethod
    def get_uninstall_command(cls, app: AppItem, purge_data: bool = True) -> List[str]:
        handler = cls.get_backend_handler(app)
        if handler:
            if handler == FlatpakBackend:
                return handler.get_uninstall_command(app, purge_data=purge_data)
            return handler.get_uninstall_command(app)

        if app.desktop_file:
            return ["rm", "-f", app.desktop_file]
        return ["echo", f"No native uninstaller found for {app.name}"]

    @classmethod
    def get_storage_locations(cls, app: AppItem) -> List[StorageLocation]:
        locations: List[StorageLocation] = []
        handler = cls.get_backend_handler(app)
        if handler and hasattr(handler, "get_storage_locations"):
            locations.extend(handler.get_storage_locations(app))
        return locations
