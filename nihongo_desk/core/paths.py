"""Rutas de recursos (solo lectura) y de datos del usuario (lectura/escritura)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "NihongoDesk"


def resources_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))  # PyInstaller o código fuente
    if (base / "nihongo_desk").is_dir():
        base = base / "nihongo_desk"
    return base / "resources"


def user_data_dir() -> Path:
    """Windows: %APPDATA%\\NihongoDesk · Linux: $XDG_DATA_HOME/NihongoDesk (~/.local/share)."""
    override = os.environ.get("NIHONGO_DESK_HOME")
    if override:
        path = Path(override)
    elif sys.platform == "win32":
        path = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        path = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def assets_dir() -> Path:
    """Ilustraciones e iconos (``nihongo_desk/assets``)."""
    return resources_dir().parent / "assets"
