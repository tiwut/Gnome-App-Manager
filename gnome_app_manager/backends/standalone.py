import os
import shlex
from typing import List, Optional
from ..models.app_info import AppItem
from ..models.location_info import StorageLocation, LocationCategory
from ..core.utils import get_path_size_and_count, is_root_needed


class StandaloneBackend:
    name = "appimage"

    @classmethod
    def get_uninstall_command(cls, app: AppItem) -> List[str]:
        targets = []
        if app.desktop_file and os.path.exists(app.desktop_file):
            targets.append(app.desktop_file)

        bin_path = cls.extract_binary_path(app)
        if bin_path and os.path.exists(bin_path):
            targets.append(bin_path)

        if not targets:
            return ["true"]

        needs_root = any(is_root_needed(t) for t in targets)
        cmd = ["rm", "-f"] + targets
        if needs_root:
            return ["pkexec"] + cmd
        return cmd

    @classmethod
    def extract_binary_path(cls, app: AppItem) -> Optional[str]:
        if not app.exec_cmd:
            return None
        try:
            parts = shlex.split(app.exec_cmd)
            for part in parts:
                if part.startswith("%"):
                    continue
                expanded = os.path.expanduser(part)
                if os.path.isfile(expanded):
                    return expanded
        except Exception:
            pass
        return None

    @classmethod
    def get_storage_locations(cls, app: AppItem) -> List[StorageLocation]:
        locations = []
        if app.desktop_file and os.path.exists(app.desktop_file):
            s, c = get_path_size_and_count(app.desktop_file)
            locations.append(StorageLocation(
                path=app.desktop_file,
                category=LocationCategory.SHORTCUTS,
                description="Desktop entry shortcut",
                exists=True,
                size_bytes=s,
                is_directory=False,
                requires_root=is_root_needed(app.desktop_file),
                item_count=1
            ))

        bin_path = cls.extract_binary_path(app)
        if bin_path and os.path.exists(bin_path):
            s, c = get_path_size_and_count(bin_path)
            locations.append(StorageLocation(
                path=bin_path,
                category=LocationCategory.DATA,
                description="Application executable / AppImage binary",
                exists=True,
                size_bytes=s,
                is_directory=False,
                requires_root=is_root_needed(bin_path),
                item_count=1
            ))

        return locations
