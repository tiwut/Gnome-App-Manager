import os
import shutil
import subprocess
from typing import List, Optional
from ..models.app_info import AppItem
from ..models.location_info import StorageLocation, LocationCategory
from ..core.utils import get_path_size_and_count, is_root_needed


class DebAptBackend:
    name = "deb"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("dpkg") is not None and shutil.which("apt-get") is not None

    @classmethod
    def get_package_for_file(cls, file_path: str) -> Optional[str]:
        if not shutil.which("dpkg") or not os.path.exists(file_path):
            return None
        try:
            res = subprocess.run(["dpkg", "-S", file_path], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                line = res.stdout.strip().splitlines()[0]
                pkg = line.split(":")[0].strip()
                return pkg
        except Exception:
            pass
        return None

    @classmethod
    def get_package_size(cls, pkg_name: str) -> int:
        if not shutil.which("dpkg-query"):
            return 0
        try:
            res = subprocess.run(
                ["dpkg-query", "-W", "-f=${Installed-Size}", pkg_name],
                capture_output=True, text=True
            )
            if res.returncode == 0 and res.stdout.strip():
                return int(res.stdout.strip()) * 1024
        except Exception:
            pass
        return 0

    @classmethod
    def get_uninstall_command(cls, app: AppItem) -> List[str]:
        pkg = app.package_name or app.id
        return ["pkexec", "apt-get", "purge", "-y", pkg]

    @classmethod
    def get_storage_locations(cls, app: AppItem) -> List[StorageLocation]:
        pkg = app.package_name or app.id
        locations = []
        for base, cat, desc in [
            (f"/etc/{pkg}", LocationCategory.SYSTEM_ETC, "APT configuration folder"),
            (f"/var/lib/{pkg}", LocationCategory.SYSTEM_LIB, "APT variable state data"),
            (f"/var/log/{pkg}", LocationCategory.SYSTEM_LIB, "Application logs"),
            (f"/usr/share/{pkg}", LocationCategory.SYSTEM_LIB, "Application shared data"),
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
