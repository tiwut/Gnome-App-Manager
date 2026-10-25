import os
import shutil
import subprocess
from typing import List, Optional
from ..models.app_info import AppItem
from ..models.location_info import StorageLocation, LocationCategory
from ..core.utils import get_path_size_and_count, is_root_needed


class PacmanBackend:
    name = "pacman"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("pacman") is not None

    @classmethod
    def get_package_for_file(cls, file_path: str) -> Optional[str]:
        if not cls.is_available() or not os.path.exists(file_path):
            return None
        try:
            res = subprocess.run(["pacman", "-Qo", file_path], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                parts = res.stdout.strip().split()
                if "owned by" in res.stdout:
                    idx = parts.index("by")
                    if idx + 1 < len(parts):
                        return parts[idx + 1]
        except Exception:
            pass
        return None

    @classmethod
    def get_uninstall_command(cls, app: AppItem) -> List[str]:
        pkg = app.package_name or app.id
        return ["pkexec", "pacman", "-Rns", "--noconfirm", pkg]

    @classmethod
    def get_storage_locations(cls, app: AppItem) -> List[StorageLocation]:
        pkg = app.package_name or app.id
        locations = []
        for base, cat, desc in [
            (f"/etc/{pkg}", LocationCategory.SYSTEM_ETC, "Arch system configuration"),
            (f"/var/lib/{pkg}", LocationCategory.SYSTEM_LIB, "Variable package data"),
            (f"/usr/share/{pkg}", LocationCategory.SYSTEM_LIB, "Shared assets"),
        ]:
            if os.path.exists(base):
                s, c = get_path_size_and_count(base)
                locations.append(StorageLocation(
                    path=base,
                    category=cat,
                    description=desc,
                    exists=True,
                    size_bytes=s,
                    is_directory=os.path.isdir(base),
                    requires_root=is_root_needed(base),
                    item_count=c
                ))
        return locations
