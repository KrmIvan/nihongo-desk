"""Preferencias de la mascota, guardadas en ``user.db`` bajo la clave ``mascot``."""
from __future__ import annotations

from typing import Any

DEFAULTS: dict[str, Any] = {
    "mode": "floating",          # floating | integrated | off
    "visible": True,             # la ventana flotante se muestra (además de mode)
    "character": "momo",
    "personality": None,         # None = la del personaje
    "size": 280,                 # alto del personaje en px (ventana flotante)
    "bg_mode": "transparent",    # transparent | solid
    "bg_color": "#2b2f3a",
    "corner": "bottom_right",    # bottom_right | bottom_left | top_right | top_left | custom
    "pos": None,                 # [x, y] si corner == custom
    "on_top": True,
    "click_through": False,      # los clics atraviesan la mascota
    "follow_app": True,          # se oculta/muestra con la ventana principal (y el atajo)
    "hide_in_game": True,
    "animations": True,
    "idle_moves": True,
    "blink": True,
    "messages": True,
    "translation": True,
    "greetings": True,
    "react_correct": True,
    "react_wrong": True,
    "celebrations": True,
    "sleep": True,
    "sleep_minutes": 5,
}

PRESET_COLORS = [
    ("night", "#1f2330"), ("slate", "#3a3f4b"), ("lavender", "#e9defa"), ("sky", "#dff1fb"),
    ("sakura", "#fde4ec"), ("mint", "#dcf3e6"), ("cream", "#fbf3e1"), ("white", "#ffffff"),
]


class MascotConfig:
    def __init__(self, db):
        self.db = db
        stored = db.get("mascot") or {}
        self.data = {**DEFAULTS, **{k: v for k, v in stored.items() if k in DEFAULTS}}

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.db.set("mascot", self.data)

    def update(self, **values) -> None:
        self.data.update(values)
        self.db.set("mascot", self.data)

    def reset_appearance(self) -> None:
        """Restaura apariencia (no las preferencias de reacciones)."""
        for k in ("character", "personality", "size", "bg_mode", "bg_color", "corner", "pos", "on_top",
                  "click_through", "animations", "idle_moves", "blink"):
            self.data[k] = DEFAULTS[k]
        self.db.set("mascot", self.data)
