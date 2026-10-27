"""Repetición espaciada: variante simplificada de SM-2.

- Acierto: 1 día → 3 días → intervalo × facilidad. La facilidad sube un poco.
- Fallo: vuelve a aprendizaje (repaso en 10 min) y la facilidad baja.
Dominio 0–5 derivado del intervalo, para mostrar el progreso.
"""
from __future__ import annotations

from dataclasses import dataclass

DAY = 86400
RELEARN_DELAY = 10 * 60
MIN_EASE, MAX_EASE, START_EASE = 1.3, 3.0, 2.5
LEARNED_DAYS = 7  # a partir de aquí un elemento cuenta como "aprendido"


@dataclass
class ItemState:
    reps: int = 0          # aciertos seguidos
    interval: float = 0.0  # días
    ease: float = START_EASE
    lapses: int = 0
    correct: int = 0
    wrong: int = 0
    last_review: float | None = None
    due: float | None = None  # epoch; None = nunca visto

    @property
    def mastery(self) -> int:
        if self.correct == 0 and self.wrong == 0:
            return 0
        for level, days in ((5, 60), (4, 21), (3, LEARNED_DAYS), (2, 3)):
            if self.interval >= days:
                return level
        return 1

    @property
    def learned(self) -> bool:
        return self.interval >= LEARNED_DAYS

    def is_due(self, now: float) -> bool:
        return self.due is not None and self.due <= now

    @property
    def error_rate(self) -> float:
        total = self.correct + self.wrong
        return self.wrong / total if total else 0.0


def review(state: ItemState, correct: bool, now: float) -> ItemState:
    s = ItemState(**vars(state))
    s.last_review = now
    if correct:
        s.correct += 1
        s.reps += 1
        if s.reps == 1:
            s.interval = 1.0
        elif s.reps == 2:
            s.interval = 3.0
        else:
            s.interval = round(s.interval * s.ease, 1)
        s.ease = min(MAX_EASE, s.ease + 0.05)
        s.due = now + s.interval * DAY
    else:
        s.wrong += 1
        s.lapses += 1
        s.reps = 0
        s.interval = 0.0
        s.ease = max(MIN_EASE, s.ease - 0.2)
        s.due = now + RELEARN_DELAY
    return s
