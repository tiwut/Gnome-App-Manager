from dataclasses import dataclass
from enum import Enum
from typing import Optional


class LocationCategory(str, Enum):
    CONFIG = "User Configuration"
    CACHE = "Cache & Temporary Files"
    DATA = "Application Data & State"
    SANDBOX = "Container Sandbox (~/.var, snap)"
    SHORTCUTS = "Shortcuts & Desktop Entries"
    SERVICES = "Services & Autostart Daemons"
    SYSTEM_ETC = "System Configuration (/etc)"
    SYSTEM_LIB = "System Libraries & Data (/var, /usr)"
    ICONS = "Icons, Pixmaps & MIME"
    OTHER = "Other Residual Items"

    @property
    def icon_name(self) -> str:
        icons = {
            LocationCategory.CONFIG: "preferences-system-symbolic",
            LocationCategory.CACHE: "edit-clear-all-symbolic",
            LocationCategory.DATA: "folder-documents-symbolic",
            LocationCategory.SANDBOX: "package-x-generic-symbolic",
            LocationCategory.SHORTCUTS: "emblem-symbolic-link-symbolic",
            LocationCategory.SERVICES: "system-run-symbolic",
            LocationCategory.SYSTEM_ETC: "system-file-manager-symbolic",
            LocationCategory.SYSTEM_LIB: "drive-harddisk-symbolic",
            LocationCategory.ICONS: "image-x-generic-symbolic",
            LocationCategory.OTHER: "dialog-information-symbolic",
        }
        return icons.get(self, "folder-symbolic")


@dataclass
class StorageLocation:
    path: str
    category: LocationCategory
    description: str
    exists: bool = False
    size_bytes: int = 0
    is_directory: bool = False
    requires_root: bool = False
    item_count: int = 0

    @property
    def formatted_size(self) -> str:
        if not self.exists:
            return "Not present"
        size = float(self.size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


@dataclass
class LeftoverItem:
    path: str
    category: LocationCategory
    size_bytes: int = 0
    is_directory: bool = False
    requires_root: bool = False
    selected: bool = True
    reason: str = ""

    @property
    def formatted_size(self) -> str:
        size = float(self.size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
