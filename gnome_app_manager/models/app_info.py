from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class AppItem:
    id: str
    name: str
    version: str = "Unknown"
    backend: str = "system"
    origin: str = "local"
    icon_name: str = "application-x-executable"
    desktop_file: Optional[str] = None
    exec_cmd: Optional[str] = None
    summary: str = ""
    installed_size: int = 0
    is_user: bool = False
    install_date: Optional[str] = None
    package_name: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def backend_display(self) -> str:
        names = {
            "flatpak": "Flatpak",
            "rpm": "RPM (DNF)",
            "deb": "Debian (APT)",
            "pacman": "Arch (Pacman)",
            "snap": "Snap",
            "appimage": "AppImage",
            "custom": "Local App",
            "system": "System Package",
        }
        return names.get(self.backend, self.backend.capitalize())

    @property
    def formatted_size(self) -> str:
        if self.installed_size <= 0:
            return "Unknown size"
        val = float(self.installed_size)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if val < 1024.0:
                return f"{val:.1f} {unit}"
            val /= 1024.0
        return f"{val:.1f} PB"

    def get_search_terms(self) -> str:
        terms = [
            self.name,
            self.id,
            self.summary,
            self.backend,
            self.backend_display,
            self.package_name or "",
        ] + self.keywords + self.categories
        return " ".join(t.lower() for t in terms if t)
