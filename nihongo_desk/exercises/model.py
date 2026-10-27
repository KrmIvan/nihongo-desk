"""Modelo de pregunta independiente de la interfaz."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from ..content import romaji
from ..content.kana import to_hiragana as kata_to_hira


@dataclass
class Question:
    module: str            # kana | kanji | vocab | grammar
    key: str               # clave del elemento (o claves separadas por | en "match")
    level: int
    exercise: str
    kind: str              # choice | text | match | order
    instruction: str
    prompt: str = ""
    prompt_jp: bool = True
    reading: str = ""      # furigana opcional sobre el prompt
    reading_is_answer: bool = False
    hint: str = ""         # línea secundaria bajo el prompt
    options: list[str] = field(default_factory=list)
    options_jp: bool = True
    answer_index: int = -1
    accepted: set[str] = field(default_factory=set)
    input_mode: str = "romaji"   # romaji | kana
    pairs: list[tuple[str, str, str]] = field(default_factory=list)   # (izquierda, derecha, clave)
    tokens: list[str] = field(default_factory=list)
    accepted_orders: list[list[str]] = field(default_factory=list)
    correct_display: str = ""
    explanation: str = ""
    details: list[tuple[str, str]] = field(default_factory=list)
    romaji: str = ""

    def check(self, response) -> bool:
        if self.kind == "choice":
            return response == self.answer_index
        if self.kind == "text":
            return normalize(response, self.input_mode) in {normalize(a, self.input_mode) for a in self.accepted}
        if self.kind == "order":
            return list(response) in self.accepted_orders
        raise ValueError(self.kind)


def normalize(text: str, mode: str) -> str:
    s = unicodedata.normalize("NFKC", text or "").strip().lower().replace(" ", "")
    if mode == "kana":
        s = kata_to_hira(romaji.to_hiragana(s.replace(".", "")))
    return s
