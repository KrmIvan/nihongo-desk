"""Conversión romaji → hiragana para escribir lecturas sin IME japonés.

Admite Hepburn y Kunrei (shi/si, tsu/tu, ja/zya…), consonante doble → っ
y "nn"/"n'" → ん. `convert_live` deja sin convertir el final pendiente para
poder usarse mientras se escribe.
"""
from __future__ import annotations

_TABLE = {
    "a": "あ", "i": "い", "u": "う", "e": "え", "o": "お",
    "ka": "か", "ki": "き", "ku": "く", "ke": "け", "ko": "こ",
    "sa": "さ", "si": "し", "shi": "し", "su": "す", "se": "せ", "so": "そ",
    "ta": "た", "ti": "ち", "chi": "ち", "tu": "つ", "tsu": "つ", "te": "て", "to": "と",
    "na": "な", "ni": "に", "nu": "ぬ", "ne": "ね", "no": "の",
    "ha": "は", "hi": "ひ", "hu": "ふ", "fu": "ふ", "he": "へ", "ho": "ほ",
    "ma": "ま", "mi": "み", "mu": "む", "me": "め", "mo": "も",
    "ya": "や", "yu": "ゆ", "yo": "よ",
    "ra": "ら", "ri": "り", "ru": "る", "re": "れ", "ro": "ろ",
    "wa": "わ", "wo": "を", "nn": "ん", "n'": "ん",
    "ga": "が", "gi": "ぎ", "gu": "ぐ", "ge": "げ", "go": "ご",
    "za": "ざ", "zi": "じ", "ji": "じ", "zu": "ず", "ze": "ぜ", "zo": "ぞ",
    "da": "だ", "di": "ぢ", "du": "づ", "de": "で", "do": "ど",
    "ba": "ば", "bi": "び", "bu": "ぶ", "be": "べ", "bo": "ぼ",
    "pa": "ぱ", "pi": "ぴ", "pu": "ぷ", "pe": "ぺ", "po": "ぽ",
    "sha": "しゃ", "shu": "しゅ", "sho": "しょ", "she": "しぇ",
    "cha": "ちゃ", "chu": "ちゅ", "cho": "ちょ", "che": "ちぇ",
    "ja": "じゃ", "ju": "じゅ", "jo": "じょ", "je": "じぇ",
    "fa": "ふぁ", "fi": "ふぃ", "fe": "ふぇ", "fo": "ふぉ",
    "xa": "ぁ", "xi": "ぃ", "xu": "ぅ", "xe": "ぇ", "xo": "ぉ", "xtu": "っ", "xtsu": "っ",
    "xya": "ゃ", "xyu": "ゅ", "xyo": "ょ", "-": "ー",
}
for _c, _base in {"k": "き", "s": "し", "t": "ち", "c": "ち", "n": "に", "h": "ひ", "m": "み", "r": "り",
                  "g": "ぎ", "z": "じ", "j": "じ", "d": "ぢ", "b": "び", "p": "ぴ"}.items():
    for _v, _small in (("a", "ゃ"), ("u", "ゅ"), ("o", "ょ")):
        _TABLE.setdefault(f"{_c}y{_v}", _base + _small)

_MAXLEN = max(len(k) for k in _TABLE)
_CONSONANTS = set("bcdfghjklmnpqrstvwxyz")


def _convert(text: str, final: bool) -> str:
    s = text.lower()
    out: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch not in _CONSONANTS and ch not in "aiueo-'":
            out.append(ch)  # kana ya escritos, espacios, etc.
            i += 1
            continue
        # consonante doble -> っ (excepto nn)
        if ch in _CONSONANTS and ch != "n" and i + 1 < len(s) and s[i + 1] == ch:
            out.append("っ")
            i += 1
            continue
        # n seguida de consonante (no y) -> ん;  "nn" + vocal/y -> ん + n… (onna -> おんな)
        if ch == "n" and i + 1 < len(s) and s[i + 1] in _CONSONANTS and s[i + 1] != "y":
            if s[i + 1] != "n":
                out.append("ん")
                i += 1
                continue
            if i + 2 < len(s) and s[i + 2] in "aiueoy":
                out.append("ん")
                i += 1
                continue
        for ln in range(min(_MAXLEN, len(s) - i), 0, -1):
            chunk = s[i:i + ln]
            if chunk in _TABLE:
                out.append(_TABLE[chunk])
                i += ln
                break
        else:
            rest = s[i:]
            if final:
                out.append("ん" if rest == "n" else rest)
                return "".join(out)
            if any(k.startswith(rest) for k in _TABLE):
                out.append(rest)
                return "".join(out)
            out.append(ch)
            i += 1
    return "".join(out)


def to_hiragana(text: str) -> str:
    """Conversión completa (al enviar la respuesta)."""
    return _convert(text, final=True)


def convert_live(text: str) -> str:
    """Conversión mientras se escribe: el romaji incompleto queda tal cual."""
    return _convert(text, final=False)


def kana_to_romaji(text: str) -> str:
    """Kana → romaji Hepburn (para mostrar la pronunciación si el usuario lo pide)."""
    from .kana import ALL_KANA, to_hiragana as k2h

    table = {k.char: k.romaji for k in ALL_KANA if k.script == "h"}
    table.update({"ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o", "ゃ": "ya", "ゅ": "yu", "ょ": "yo"})
    s = k2h(text)
    out: list[str] = []
    i, double = 0, False
    while i < len(s):
        if s[i] == "っ":
            double = True
            i += 1
            continue
        if s[i] == "ー" and out:
            out.append(out[-1][-1])
            i += 1
            continue
        chunk = s[i:i + 2] if s[i:i + 2] in table else s[i]
        r = table.get(chunk, chunk)
        if double and r and r[0] not in "aiueon":
            r = ("t" if r.startswith("ch") else r[0]) + r
        double = False
        out.append(r)
        i += len(chunk)
    return "".join(out)
