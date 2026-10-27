"""Sonidos breves de acierto/fallo, generados la primera vez (sin archivos binarios)."""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from PySide6.QtCore import QUrl

RATE = 22050


def _tone(path: Path, notes: list[tuple[float, float]], volume: float = 0.35) -> None:
    frames = bytearray()
    for freq, dur in notes:
        n = int(RATE * dur)
        for i in range(n):
            env = min(1.0, i / 300) * (1 - i / n) ** 1.5  # ataque corto, caída suave
            frames += struct.pack("<h", int(32767 * volume * env * math.sin(2 * math.pi * freq * i / RATE)))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


class Sounds:
    def __init__(self, folder: Path):
        self.effects = {}
        try:
            from PySide6.QtMultimedia import QSoundEffect
        except ImportError:  # QtMultimedia no disponible: la app funciona en silencio
            return
        specs = {"ok": [(880, 0.07), (1318.5, 0.16)], "bad": [(246.9, 0.09), (196, 0.18)]}
        for name, notes in specs.items():
            path = folder / f"{name}.wav"
            if not path.exists():
                _tone(path, notes)
            eff = QSoundEffect()
            eff.setSource(QUrl.fromLocalFile(str(path)))
            eff.setVolume(0.5)
            self.effects[name] = eff

    def play(self, name: str) -> None:
        eff = self.effects.get(name)
        if eff:
            eff.play()
