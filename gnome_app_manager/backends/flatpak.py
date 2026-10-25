import os
import shutil
import subprocess
from typing import List, Dict, Any, Optional
from ..models.app_info import AppItem
from ..models.location_info import StorageLocation, LocationCategory
from ..core.utils import get_path_size_and_count, is_root_needed


class FlatpakBackend:
    name = "flatpak"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("flatpak") is not None

    @classmethod
    def list_apps(cls) -> List[AppItem]:
        apps = []
        if not cls.is_available():
            return apps

        try:
            cmd = [
                "flatpak", "list", "--app",
                "--columns=application,name,version,size,installation,origin,description"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            for line in res.stdout.strip().splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                
                app_id = parts[0].strip()
                app_name = parts[1].strip() if len(parts) > 1 and parts[1].strip() else app_id
                version = parts[2].strip() if len(parts) > 2 and parts[2].strip() else "Unknown"
                size_str = parts[3].strip() if len(parts) > 3 else ""
                installation = parts[4].strip() if len(parts) > 4 else "system"
                origin = parts[5].strip() if len(parts) > 5 else "flathub"
                summary = parts[6].strip() if len(parts) > 6 else ""

                is_user = (installation == "user")
                size_bytes = cls._parse_size(size_str)
                desktop_file = cls._find_desktop_file(app_id, is_user)

                item = AppItem(
                    id=app_id,
                    name=app_name,
                    version=version,
                    backend="flatpak",
                    origin=origin,
                    icon_name=app_id,
                    desktop_file=desktop_file,
                    exec_cmd=f"flatpak run {app_id}",
                    summary=summary,
                    installed_size=size_bytes,
                    is_user=is_user,
                    raw_data={
                        "installation": installation,
                        "origin": origin,
                    }
                )
                apps.append(item)
        except Exception:
            pass
        return apps

    @classmethod
    def get_uninstall_command(cls, app: AppItem, purge_data: bool = True) -> List[str]:
        cmd = ["flatpak", "uninstall", "-y"]
        if purge_data:
            cmd.append("--delete-data")
        if app.is_user:
            cmd.append("--user")
        else:
            cmd.append("--system")
        cmd.append(app.id)

        if not app.is_user and os.geteuid() != 0:
            return ["pkexec"] + cmd
        return cmd

    @classmethod
    def get_storage_locations(cls, app: AppItem) -> List[StorageLocation]:
        app_id = app.id
        home = os.path.expanduser("~")
        locations = []

        sandbox_path = os.path.join(home, ".var", "app", app_id)
        size, count = get_path_size_and_count(sandbox_path)
        locations.append(StorageLocation(
            path=sandbox_path,
            category=LocationCategory.SANDBOX,
            description="Flatpak sandbox environment (Contains user config, cache, and local data)",
            exists=os.path.exists(sandbox_path),
            size_bytes=size,
            is_directory=True,
            requires_root=False,
            item_count=count
        ))

        for sub, cat, desc in [
            ("config", LocationCategory.CONFIG, "Sandboxed configuration files"),
            ("cache", LocationCategory.CACHE, "Sandboxed cache & temp files"),
            ("data", LocationCategory.DATA, "Sandboxed application documents & data"),
        ]:
            p = os.path.join(sandbox_path, sub)
            if os.path.exists(p):
                s, c = get_path_size_and_count(p)
                locations.append(StorageLocation(
                    path=p,
                    category=cat,
                    description=desc,
                    exists=True,
                    size_bytes=s,
                    is_directory=True,
                    requires_root=False,
                    item_count=c
                ))

        if app.is_user:
            user_inst = os.path.join(home, ".local", "share", "flatpak", "app", app_id)
            s, c = get_path_size_and_count(user_inst)
            locations.append(StorageLocation(
                path=user_inst,
                category=LocationCategory.SYSTEM_LIB,
                description="User Flatpak binaries and runtime files",
                exists=os.path.exists(user_inst),
                size_bytes=s,
                is_directory=True,
                requires_root=False,
                item_count=c
            ))
        else:
            sys_inst = os.path.join("/var/lib/flatpak/app", app_id)
            s, c = get_path_size_and_count(sys_inst)
            locations.append(StorageLocation(
                path=sys_inst,
                category=LocationCategory.SYSTEM_LIB,
                description="System Flatpak binaries and runtime files",
                exists=os.path.exists(sys_inst),
                size_bytes=s,
                is_directory=True,
                requires_root=True,
                item_count=c
            ))

        user_override = os.path.join(home, ".local", "share", "flatpak", "overrides", app_id)
        if os.path.exists(user_override):
            s, c = get_path_size_and_count(user_override)
            locations.append(StorageLocation(
                path=user_override,
                category=LocationCategory.CONFIG,
                description="User permission overrides for this Flatpak",
                exists=True,
                size_bytes=s,
                is_directory=os.path.isdir(user_override),
                requires_root=False,
                item_count=c
            ))

        export_paths = [
            os.path.join(home, ".local", "share", "flatpak", "exports", "share", "applications", f"{app_id}.desktop"),
            f"/var/lib/flatpak/exports/share/applications/{app_id}.desktop",
            os.path.join(home, ".local", "share", "applications", f"{app_id}.desktop"),
            os.path.join(home, "Desktop", f"{app_id}.desktop"),
        ]
        for ep in export_paths:
            if os.path.exists(ep):
                s, c = get_path_size_and_count(ep)
                locations.append(StorageLocation(
                    path=ep,
                    category=LocationCategory.SHORTCUTS,
                    description="Desktop launcher / shortcut",
                    exists=True,
                    size_bytes=s,
                    is_directory=False,
                    requires_root=is_root_needed(ep),
                    item_count=1
                ))

        return locations

    @classmethod
    def _parse_size(cls, size_str: str) -> int:
        if not size_str:
            return 0
        try:
            parts = size_str.replace("\xa0", " ").strip().split()
            if not parts:
                return 0
            val = float(parts[0])
            unit = parts[1].upper() if len(parts) > 1 else "B"
            mult = 1
            if "K" in unit:
                mult = 1024
            elif "M" in unit:
                mult = 1024 * 1024
            elif "G" in unit:
                mult = 1024 * 1024 * 1024
            elif "T" in unit:
                mult = 1024 * 1024 * 1024 * 1024
            return int(val * mult)
        except Exception:
            return 0

    @classmethod
    def _find_desktop_file(cls, app_id: str, is_user: bool) -> Optional[str]:
        candidates = [
            os.path.expanduser(f"~/.local/share/flatpak/exports/share/applications/{app_id}.desktop"),
            f"/var/lib/flatpak/exports/share/applications/{app_id}.desktop",
            os.path.expanduser(f"~/.local/share/applications/{app_id}.desktop"),
            f"/usr/share/applications/{app_id}.desktop"
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return None
