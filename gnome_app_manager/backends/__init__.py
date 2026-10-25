from .detector import AppDetector
from .flatpak import FlatpakBackend
from .rpm_dnf import RpmDnfBackend
from .deb_apt import DebAptBackend
from .pacman import PacmanBackend
from .snap import SnapBackend
from .standalone import StandaloneBackend

__all__ = [
    "AppDetector",
    "FlatpakBackend",
    "RpmDnfBackend",
    "DebAptBackend",
    "PacmanBackend",
    "SnapBackend",
    "StandaloneBackend"
]
