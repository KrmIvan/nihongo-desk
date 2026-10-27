"""Tablas de kana (hiragana; el katakana se deriva por desplazamiento Unicode).

Cada entrada: (kana, romaji Hepburn, variantes aceptadas, grupo).
Grupos: fila base (a, ka, …), "dakuten", "handakuten", "yoon".
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Kana:
    char: str
    romaji: str
    variants: tuple[str, ...]
    group: str
    script: str  # "h" | "k"

    @property
    def key(self) -> str:
        return f"{self.script}:{self.char}"

    def accepted(self) -> set[str]:
        return {self.romaji, *self.variants}


_BASE = [
    ("あ", "a", (), "a"), ("い", "i", (), "a"), ("う", "u", (), "a"), ("え", "e", (), "a"), ("お", "o", (), "a"),
    ("か", "ka", (), "ka"), ("き", "ki", (), "ka"), ("く", "ku", (), "ka"), ("け", "ke", (), "ka"), ("こ", "ko", (), "ka"),
    ("さ", "sa", (), "sa"), ("し", "shi", ("si",), "sa"), ("す", "su", (), "sa"), ("せ", "se", (), "sa"), ("そ", "so", (), "sa"),
    ("た", "ta", (), "ta"), ("ち", "chi", ("ti",), "ta"), ("つ", "tsu", ("tu",), "ta"), ("て", "te", (), "ta"), ("と", "to", (), "ta"),
    ("な", "na", (), "na"), ("に", "ni", (), "na"), ("ぬ", "nu", (), "na"), ("ね", "ne", (), "na"), ("の", "no", (), "na"),
    ("は", "ha", (), "ha"), ("ひ", "hi", (), "ha"), ("ふ", "fu", ("hu",), "ha"), ("へ", "he", (), "ha"), ("ほ", "ho", (), "ha"),
    ("ま", "ma", (), "ma"), ("み", "mi", (), "ma"), ("む", "mu", (), "ma"), ("め", "me", (), "ma"), ("も", "mo", (), "ma"),
    ("や", "ya", (), "ya"), ("ゆ", "yu", (), "ya"), ("よ", "yo", (), "ya"),
    ("ら", "ra", (), "ra"), ("り", "ri", (), "ra"), ("る", "ru", (), "ra"), ("れ", "re", (), "ra"), ("ろ", "ro", (), "ra"),
    ("わ", "wa", (), "wa"), ("を", "wo", ("o",), "wa"), ("ん", "n", ("nn",), "wa"),
]
_DAKUTEN = [
    ("が", "ga", ()), ("ぎ", "gi", ()), ("ぐ", "gu", ()), ("げ", "ge", ()), ("ご", "go", ()),
    ("ざ", "za", ()), ("じ", "ji", ("zi",)), ("ず", "zu", ()), ("ぜ", "ze", ()), ("ぞ", "zo", ()),
    ("だ", "da", ()), ("ぢ", "ji", ("di", "dji")), ("づ", "zu", ("du", "dzu")), ("で", "de", ()), ("ど", "do", ()),
    ("ば", "ba", ()), ("び", "bi", ()), ("ぶ", "bu", ()), ("べ", "be", ()), ("ぼ", "bo", ()),
]
_HANDAKUTEN = [("ぱ", "pa", ()), ("ぴ", "pi", ()), ("ぷ", "pu", ()), ("ぺ", "pe", ()), ("ぽ", "po", ())]
_YOON = [
    ("きゃ", "kya", ()), ("きゅ", "kyu", ()), ("きょ", "kyo", ()),
    ("しゃ", "sha", ("sya",)), ("しゅ", "shu", ("syu",)), ("しょ", "sho", ("syo",)),
    ("ちゃ", "cha", ("tya", "cya")), ("ちゅ", "chu", ("tyu", "cyu")), ("ちょ", "cho", ("tyo", "cyo")),
    ("にゃ", "nya", ()), ("にゅ", "nyu", ()), ("にょ", "nyo", ()),
    ("ひゃ", "hya", ()), ("ひゅ", "hyu", ()), ("ひょ", "hyo", ()),
    ("みゃ", "mya", ()), ("みゅ", "myu", ()), ("みょ", "myo", ()),
    ("りゃ", "rya", ()), ("りゅ", "ryu", ()), ("りょ", "ryo", ()),
    ("ぎゃ", "gya", ()), ("ぎゅ", "gyu", ()), ("ぎょ", "gyo", ()),
    ("じゃ", "ja", ("zya", "jya")), ("じゅ", "ju", ("zyu", "jyu")), ("じょ", "jo", ("zyo", "jyo")),
    ("びゃ", "bya", ()), ("びゅ", "byu", ()), ("びょ", "byo", ()),
    ("ぴゃ", "pya", ()), ("ぴゅ", "pyu", ()), ("ぴょ", "pyo", ()),
]

BASE_GROUPS = ["a", "ka", "sa", "ta", "na", "ha", "ma", "ya", "ra", "wa"]
EXTRA_GROUPS = ["dakuten", "handakuten", "yoon"]

# Pares que suelen confundirse (se usan como distractores en dificultad alta
# y en la explicación tras un fallo).
CONFUSABLE = {
    "h": [("ぬ", "め"), ("ね", "れ"), ("れ", "わ"), ("ね", "わ"), ("る", "ろ"), ("さ", "ち"), ("き", "さ"),
          ("は", "ほ"), ("い", "り"), ("こ", "に"), ("う", "つ"), ("あ", "お"), ("ま", "も"), ("し", "つ")],
    "k": [("シ", "ツ"), ("ソ", "ン"), ("ク", "ケ"), ("ウ", "ワ"), ("チ", "テ"), ("ノ", "メ"), ("ス", "ヌ"),
          ("コ", "ユ"), ("フ", "ワ"), ("ア", "マ"), ("セ", "ヤ"), ("ル", "レ")],
}


def to_katakana(s: str) -> str:
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


def to_hiragana(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def _build() -> list[Kana]:
    rows: list[Kana] = []
    for script in ("h", "k"):
        conv = (lambda x: x) if script == "h" else to_katakana
        for ch, ro, var, grp in _BASE:
            rows.append(Kana(conv(ch), ro, var, grp, script))
        for table, grp in ((_DAKUTEN, "dakuten"), (_HANDAKUTEN, "handakuten"), (_YOON, "yoon")):
            for ch, ro, var in table:
                rows.append(Kana(conv(ch), ro, var, grp, script))
    return rows


ALL_KANA: list[Kana] = _build()
BY_KEY: dict[str, Kana] = {k.key: k for k in ALL_KANA}


def select(scripts: list[str], groups: list[str]) -> list[Kana]:
    return [k for k in ALL_KANA if k.script in scripts and k.group in groups]


def confusables_of(k: Kana) -> list[str]:
    out = []
    for a, b in CONFUSABLE[k.script]:
        if k.char == a:
            out.append(b)
        elif k.char == b:
            out.append(a)
    return out
