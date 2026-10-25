import os
import shutil
import subprocess
from typing import List, Optional
from ..models.app_info import AppItem
from ..models.location_info import StorageLocation, LocationCategory
from ..core.utils import get_path_size_and_count, is_root_needed


class RpmDnfBackend:
    name = "rpm"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("rpm") is not None and (shutil.which("dnf") is not None or shutil.which("rpm") is not None)

    @classmethod
    def get_package_for_file(cls, file_path: str) -> Optional[str]:
        if not shutil.which("rpm") or not os.path.exists(file_path):
            return None
        try:
            res = subprocess.run(["rpm", "-qf", "--qf", "%{NAME}", file_path],
                                 capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass
        return None

    @classmethod
    def batch_resolve_files(cls, file_paths: List[str]) -> dict:
        result = {}
        if not shutil.which("rpm") or not file_paths:
            return result

        valid_files = [f for f in file_paths if os.path.exists(f)]
        if not valid_files:
            return result

        try:
            cmd = ["rpm", "-qf", "--qf", "%{FILENAMES}\t%{NAME}\t%{VERSION}\t%{SIZE}\n"] + valid_files
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 or res.stdout:
                for line in res.stdout.strip().splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 4:
                        fn, name, ver, sz = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
                        try:
                            sz_val = int(sz)
                        except ValueError:
                            sz_val = 0
                        result[fn] = {"name": name, "version": ver, "size": sz_val}
        except Exception:
            pass
        return result

    @classmethod
    def get_package_size(cls, pkg_name: str) -> int:
        try:
            res = subprocess.run(["rpm", "-q", "--qf", "%{SIZE}", pkg_name],
                                 capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return int(res.stdout.strip())
        except Exception:
            pass
        return 0

    @classmethod
    def get_uninstall_command(cls, app: AppItem) -> List[str]:
        pkg = app.package_name or app.id
        if shutil.which("dnf"):
            return ["pkexec", "dnf", "remove", "-y", pkg]
        return ["pkexec", "rpm", "-e", pkg]

    @classmethod
    def get_storage_locations(cls, app: AppItem) -> List[StorageLocation]:
        pkg = app.package_name or app.id
        locations = []
        if not shutil.which("rpm"):
            return locations

        try:
            res = subprocess.run(["rpm", "-qc", pkg], capture_output=True, text=True)
            if res.returncode == 0:
                for line in res.stdout.strip().splitlines():
                    p = line.strip()
                    if p and os.path.exists(p):
                        s, c = get_path_size_and_count(p)
                        locations.append(StorageLocation(
                            path=p,
                            category=LocationCategory.SYSTEM_ETC,
                            description="RPM-tracked configuration file",
                            exists=True,
                            size_bytes=s,
                            is_directory=os.path.isdir(p),
                            requires_root=is_root_needed(p),
                            item_count=c
                        ))
        except Exception:
            pass

        for base, cat, desc in [
            (f"/etc/{pkg}", LocationCategory.SYSTEM_ETC, "System configuration folder"),
            (f"/var/lib/{pkg}", LocationCategory.SYSTEM_LIB, "System variable data folder"),
            (f"/var/log/{pkg}", LocationCategory.SYSTEM_LIB, "System log files"),
            (f"/usr/share/{pkg}", LocationCategory.SYSTEM_LIB, "Shared application assets"),
            (f"/usr/lib64/{pkg}", LocationCategory.SYSTEM_LIB, "Shared system libraries"),
            (f"/usr/lib/{pkg}", LocationCategory.SYSTEM_LIB, "System libraries"),
            (f"/etc/xdg/autostart/{pkg}.desktop", LocationCategory.SERVICES, "System autostart entry"),
            (f"/etc/systemd/system/{pkg}.service", LocationCategory.SERVICES, "Systemd system daemon"),
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
