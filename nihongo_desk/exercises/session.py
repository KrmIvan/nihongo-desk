"""Estado de una sesión de estudio (serializable para poder continuarla)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .engine import Engine
from .model import Question


@dataclass
class Session:
    module: str                  # kana | kanji | vocab | grammar | review | quick
    title: str
    specs: list[dict]
    origin: dict = field(default_factory=dict)  # cómo se creó (para «otra ronda»)
    index: int = 0
    correct: int = 0
    answered: int = 0
    seconds: float = 0.0
    time_limit: float | None = None  # segundos (sesión rápida)
    missed: list[tuple[str, str]] = field(default_factory=list)  # (prompt, respuesta)

    @property
    def total(self) -> int:
        return len(self.specs) if self.time_limit is None else max(len(self.specs), 1)

    def finished(self) -> bool:
        if self.index >= len(self.specs):
            return True
        return self.time_limit is not None and self.seconds >= self.time_limit

    def next_question(self, engine: Engine) -> Question | None:
        while not self.finished():
            q = engine.build(self.specs[self.index])
            if q is not None:
                return q
            self.index += 1  # elemento inexistente (contenido cambiado): se salta
        return None

    def record(self, engine: Engine, q: Question, correct: bool, ms: int, item_key: str | None = None) -> None:
        engine.db.record(q.module, item_key or q.key, q.level, q.exercise, correct, ms)

    def advance(self, q: Question, correct: bool, elapsed: float) -> None:
        self.answered += 1
        self.correct += int(correct)
        self.seconds += min(elapsed, 120)
        if not correct:
            self.missed.append((q.prompt or q.correct_display, q.correct_display))
        self.index += 1

    def to_json(self) -> dict:
        return {k: getattr(self, k) for k in ("module", "title", "specs", "origin", "index", "correct", "answered",
                                              "seconds", "time_limit", "missed")}

    @classmethod
    def from_json(cls, d: dict) -> "Session":
        s = cls(**d)
        s.missed = [tuple(m) for m in s.missed]
        return s
