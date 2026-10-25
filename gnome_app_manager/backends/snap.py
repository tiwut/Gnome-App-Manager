import os
import shutil
import subprocess
from typing import List
from ..models.app_info import AppItem
from ..models.location_info import StorageLocation, LocationCategory
from ..core.utils import get_path_size_and_count, is_root_needed


class SnapBackend:
    name = "snap"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("snap") is not None

    @classmethod
    def list_apps(cls) -> List[AppItem]:
        apps = []
        if not cls.is_available():
            return apps
        try:
            res = subprocess.run(["snap", "list"], capture_output=True, text=True)
            if res.returncode == 0:
                lines = res.stdout.strip().splitlines()
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 2:
                        snap_name = parts[0]
                        version = parts[1]
                        if snap_name in ["core", "core18", "core20", "core22", "core24", "bare", "snapd"]:
                            continue
                        apps.append(AppItem(
                            id=snap_name,
                            name=snap_name.capitalize(),
                            version=version,
                            backend="snap",
                            origin="canonical-snapcraft",
                            icon_name=snap_name,
                            summary=f"Snap package: {snap_name}",
                            exec_cmd=f"snap run {snap_name}"
                        ))
        except Exception:
            pass
        return apps

    @classmethod
    def get_uninstall_command(cls, app: AppItem) -> List[str]:
        return ["pkexec", "snap", "remove", "--purge", app.id]

    @classmethod
    def get_storage_locations(cls, app: AppItem) -> List[StorageLocation]:
        name = app.id
        home = os.path.expanduser("~")
        locations = []

        user_snap = os.path.join(home, "snap", name)
        if os.path.exists(user_snap):
            s, c = get_path_size_and_count(user_snap)
            locations.append(StorageLocation(
                path=user_snap,
                category=LocationCategory.SANDBOX,
                description="Snap user data, configurations and cache",
                exists=True,
                size_bytes=s,
                is_directory=True,
                requires_root=False,
                item_count=c
            ))

        for p, cat, desc in [
            (f"/var/snap/{name}", LocationCategory.SYSTEM_LIB, "System snap data directory"),
            (f"/snap/{name}", LocationCategory.SYSTEM_LIB, "Snap mount and installation files"),
            (f"/var/lib/snapd/desktop/applications/{name}_{name}.desktop", LocationCategory.SHORTCUTS, "Snap desktop launcher"),
        ]:
            if os.path.exists(p):
                s, c = get_path_size_and_count(p)
                locations.append(StorageLocation(
                    path=p,
                    category=cat,
                    description=desc,
                    exists=True,
                    size_bytes=s,
                    is_directory=os.path.isdir(p),
                    requires_root=is_root_needed(p),
                    item_count=c
                ))

        return locations
