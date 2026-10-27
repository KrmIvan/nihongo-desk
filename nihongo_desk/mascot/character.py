"""Personajes: se descubren en ``assets/characters/<id>/manifest.json``.

Convención de archivos en ``expressions/`` (PNG o WebP, con transparencia):
    <expresión>.webp        fotograma principal
    <expresión>_blink.webp  ojos cerrados (parpadeo), opcional
    <expresión>_talk.webp   boca abierta (al hablar), opcional
Una expresión que falte se sustituye por la más parecida (``FALLBACK``), así
que un personaje nuevo puede empezar con un único ``neutral.png``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPixmap

from ..core.paths import assets_dir

EXPRESSIONS = ["neutral", "happy", "very_happy", "focused", "thinking", "surprised", "confused",
               "sad", "shy", "encouraging", "celebrating", "sleeping", "greeting"]

FALLBACK = {
    "happy": "neutral", "very_happy": "happy", "celebrating": "very_happy", "encouraging": "happy",
    "greeting": "happy", "shy": "happy", "focused": "neutral", "thinking": "focused",
    "surprised": "neutral", "confused": "thinking", "sad": "thinking", "sleeping": "neutral",
}


IMAGE_SUFFIXES = (".png", ".webp")


def characters_dir() -> Path:
    return assets_dir() / "characters"


@dataclass
class Character:
    id: str
    folder: Path
    names: dict
    personality: str
    accent: str = "#f08fb0"
    bust: tuple = (0.1, 0.0, 0.8, 0.32)
    credits: str = ""
    files: dict = field(default_factory=dict)          # "happy" / "happy_blink" -> Path
    _cache: dict = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, folder: Path) -> "Character":
        data = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        files: dict[str, Path] = {}
        exprs = data.get("expressions", "auto")
        if exprs == "auto":
            for img in sorted((folder / "expressions").iterdir()) if (folder / "expressions").is_dir() else []:
                if img.suffix.lower() in IMAGE_SUFFIXES:
                    files[img.stem] = img
        else:
            for name, spec in exprs.items():
                for kind in ("image", "blink", "talk"):
                    if spec.get(kind):
                        files[name if kind == "image" else f"{name}_{kind}"] = folder / spec[kind]
        return cls(id=data["id"], folder=folder, names=data.get("name", {}),
                   personality=data.get("personality", "calm"), accent=data.get("accent", "#f08fb0"),
                   bust=tuple(data.get("bust", (0.1, 0.0, 0.8, 0.32))), credits=data.get("credits", ""),
                   files=files)

    def name(self, lang: str) -> str:
        return self.names.get(lang) or self.names.get("en") or self.id

    # ---- expresiones ---------------------------------------------------
    def has(self, expr: str) -> bool:
        return expr in self.files

    def resolve(self, expr: str) -> str:
        seen = set()
        while expr not in self.files and expr not in seen:
            seen.add(expr)
            expr = FALLBACK.get(expr, "neutral")
        if expr not in self.files:
            expr = next(iter(self.files))
        return expr

    def available(self) -> list[str]:
        base = [e for e in self.files if not e.endswith(("_blink", "_talk"))]
        return [e for e in EXPRESSIONS if e in base] + [e for e in base if e not in EXPRESSIONS]

    def frame(self, expr: str, variant: str = "", height: int = 0) -> QPixmap:
        """Fotograma de ``expr`` (variant: '', 'blink', 'talk') escalado a ``height`` px."""
        base = self.resolve(expr)
        key = f"{base}_{variant}" if variant and f"{base}_{variant}" in self.files else base
        ck = (key, height)
        if ck not in self._cache:
            raw = self._cache.get((key, 0))
            if raw is None:
                raw = QPixmap(str(self.files[key]))
                self._cache[(key, 0)] = raw
            if height and not raw.isNull():
                self._cache[ck] = raw.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation)
            else:
                return raw
        return self._cache[ck]

    def bust_rect(self, pm: QPixmap) -> QRectF:
        x, y, w, h = self.bust
        return QRectF(pm.width() * x, pm.height() * y, pm.width() * w, pm.height() * h)

    def clear_cache(self):
        self._cache.clear()


_characters: dict[str, Character] | None = None


def all_characters(reload: bool = False) -> dict[str, Character]:
    global _characters
    if _characters is None or reload:
        found = {}
        root = characters_dir()
        if root.is_dir():
            for folder in sorted(root.iterdir()):
                if (folder / "manifest.json").is_file():
                    try:
                        c = Character.load(folder)
                    except (OSError, ValueError, KeyError):
                        continue
                    if c.files:
                        found[c.id] = c
        _characters = found
    return _characters


def get_character(cid: str) -> Character | None:
    chars = all_characters()
    return chars.get(cid) or next(iter(chars.values()), None)
