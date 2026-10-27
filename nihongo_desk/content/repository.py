"""Acceso de solo lectura al contenido japonés (content.db + gramática demo)."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Kanji:
    char: str
    jlpt: int
    onyomi: tuple[str, ...]
    kunyomi: tuple[str, ...]
    meanings: dict  # {"en": [...], "es": [...]}
    strokes: int | None = None

    @property
    def key(self) -> str:
        return self.char


@dataclass(frozen=True)
class Word:
    id: int
    word: str
    reading: str
    jlpt: int
    meanings: dict
    example_ja: str | None = None
    example_en: str | None = None
    example_target: str | None = None

    @property
    def key(self) -> str:
        return str(self.id)


@dataclass(frozen=True)
class GrammarItem:
    id: str
    jlpt: int
    type: str
    sentence: str = ""
    options: tuple[str, ...] = ()
    answer: str = ""
    tokens: tuple[str, ...] = ()
    accepted: tuple[tuple[str, ...], ...] = ()
    translation: dict = field(default_factory=dict)
    explanation: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return self.id


def meaning(m: dict, lang: str) -> tuple[list[str], str]:
    """Devuelve (significados, idioma real). Si falta el español, cae a inglés."""
    if m.get(lang):
        return m[lang], lang
    other = "en" if lang == "es" else "es"
    return m.get(other, []), other


class ContentRepo:
    def __init__(self, resources: Path):
        self.db = sqlite3.connect(str(resources / "content.db"), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        data = json.loads((resources / "grammar_demo.json").read_text(encoding="utf-8"))
        self.grammar = [GrammarItem(
            id=g["id"], jlpt=g["jlpt"], type=g["type"], sentence=g.get("sentence", ""),
            options=tuple(g.get("options", ())), answer=g.get("answer", ""), tokens=tuple(g.get("tokens", ())),
            accepted=tuple(tuple(a) for a in g.get("accepted", ())), translation=g["translation"],
            explanation=g["explanation"]) for g in data["items"]]
        self.meta = {r["key"]: r["value"] for r in self.db.execute("SELECT key, value FROM meta")}
        self._kanji_cache: dict[str, Kanji] = {}

    # ---- kanji ---------------------------------------------------------
    def _kanji(self, r: sqlite3.Row) -> Kanji:
        return Kanji(r["char"], r["jlpt"], tuple(json.loads(r["onyomi"])), tuple(json.loads(r["kunyomi"])),
                     {"en": json.loads(r["meanings_en"]), "es": json.loads(r["meanings_es"])}, r["strokes"])

    def kanji_by_levels(self, levels: list[int]) -> list[Kanji]:
        marks = ",".join("?" * len(levels)) or "0"
        rows = self.db.execute(f"SELECT * FROM kanji WHERE jlpt IN ({marks}) ORDER BY jlpt DESC, freq IS NULL, freq",
                               levels).fetchall()
        return [self._kanji(r) for r in rows]

    def kanji(self, char: str) -> Kanji | None:
        if char not in self._kanji_cache:
            r = self.db.execute("SELECT * FROM kanji WHERE char=?", (char,)).fetchone()
            if r is None:
                return None
            self._kanji_cache[char] = self._kanji(r)
        return self._kanji_cache[char]

    def kanji_count(self) -> dict[int, int]:
        return {r[0]: r[1] for r in self.db.execute("SELECT jlpt, COUNT(*) FROM kanji GROUP BY jlpt")}

    def words_with_kanji(self, char: str, limit: int = 4) -> list[Word]:
        rows = self.db.execute("SELECT * FROM vocab WHERE word LIKE ? AND word != ? ORDER BY jlpt DESC, length(word) LIMIT ?",
                               (f"%{char}%", char, limit)).fetchall()
        return [self._word(r) for r in rows]

    # ---- vocabulario ---------------------------------------------------
    def _word(self, r: sqlite3.Row) -> Word:
        return Word(r["id"], r["word"], r["reading"], r["jlpt"],
                    {"en": json.loads(r["meanings_en"]), "es": json.loads(r["meanings_es"])},
                    r["example_ja"], r["example_en"], r["example_target"])

    def words_by_levels(self, levels: list[int]) -> list[Word]:
        marks = ",".join("?" * len(levels)) or "0"
        return [self._word(r) for r in self.db.execute(f"SELECT * FROM vocab WHERE jlpt IN ({marks}) ORDER BY id", levels)]

    def word(self, wid: int | str) -> Word | None:
        r = self.db.execute("SELECT * FROM vocab WHERE id=?", (int(wid),)).fetchone()
        return self._word(r) if r else None

    def vocab_count(self) -> dict[int, int]:
        return {r[0]: r[1] for r in self.db.execute("SELECT jlpt, COUNT(*) FROM vocab GROUP BY jlpt")}

    # ---- gramática -----------------------------------------------------
    def grammar_by_levels(self, levels: list[int]) -> list[GrammarItem]:
        return [g for g in self.grammar if g.jlpt in levels]

    def grammar_item(self, gid: str) -> GrammarItem | None:
        return next((g for g in self.grammar if g.id == gid), None)

    def grammar_count(self) -> dict[int, int]:
        out: dict[int, int] = {}
        for g in self.grammar:
            out[g.jlpt] = out.get(g.jlpt, 0) + 1
        return out
