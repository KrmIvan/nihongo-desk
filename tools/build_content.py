"""Construye nihongo_desk/resources/content.db a partir de fuentes abiertas.

Fuentes (descargar en data/raw/, ver docs/DATA_SOURCES.md):
  - kanjidic2.xml.gz        EDRDG, CC BY-SA 4.0  -> lecturas, significados EN/ES
  - kanji.json              davidluzgouveia/kanji-data (MIT) -> nivel JLPT "nuevo" (listas de J. Waller)
  - JMdict.gz               EDRDG, CC BY-SA 4.0  -> glosas EN/ES del vocabulario
  - JMdict_e_examp.gz       EDRDG, CC BY-SA 4.0  -> frases de ejemplo (Tatoeba, CC BY 2.0 FR)
  - jlpt_vocab_n{1..5}.csv  jamsinclair/open-anki-jlpt-decks (listas de J. Waller, CC BY)

Uso:  python tools/build_content.py
"""
from __future__ import annotations

import csv
import gzip
import json
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "nihongo_desk" / "resources" / "content.db"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE kanji (
    id INTEGER PRIMARY KEY, char TEXT UNIQUE NOT NULL, jlpt INTEGER NOT NULL,
    strokes INTEGER, freq INTEGER,
    onyomi TEXT NOT NULL, kunyomi TEXT NOT NULL,      -- JSON list
    meanings_en TEXT NOT NULL, meanings_es TEXT NOT NULL  -- JSON list
);
CREATE TABLE vocab (
    id INTEGER PRIMARY KEY, word TEXT NOT NULL, reading TEXT NOT NULL, jlpt INTEGER NOT NULL,
    meanings_en TEXT NOT NULL, meanings_es TEXT NOT NULL,  -- JSON list
    example_ja TEXT, example_en TEXT, example_target TEXT,
    UNIQUE(word, reading)
);
CREATE INDEX vocab_jlpt ON vocab(jlpt);
CREATE INDEX kanji_jlpt ON kanji(jlpt);
"""


def clean_term(s: str) -> str:
    """'ございます (かん)' -> 'ございます'; '故～' -> '故'."""
    s = re.split(r"\s*[（(]", s.strip())[0]
    return s.replace("～", "").replace("〜", "").strip()


def load_kanjidic() -> dict[str, dict]:
    out = {}
    with gzip.open(RAW / "kanjidic2.xml.gz") as f:
        for _, el in ET.iterparse(f):
            if el.tag != "character":
                continue
            lit = el.findtext("literal")
            on, kun, en, es = [], [], [], []
            for r in el.iter("reading"):
                if r.get("r_type") == "ja_on":
                    on.append(r.text)
                elif r.get("r_type") == "ja_kun":
                    kun.append(r.text)
            for m in el.iter("meaning"):
                lang = m.get("m_lang")
                if lang is None:
                    en.append(m.text)
                elif lang == "es":
                    es.append(m.text)
            out[lit] = {"on": on, "kun": kun, "en": en, "es": es}
            el.clear()
    return out


def load_jmdict(path: Path) -> dict[tuple[str, str], dict]:
    """Indexa entradas por (forma, lectura) y por (lectura, lectura)."""
    index: dict[tuple[str, str], dict] = {}
    with gzip.open(path) as f:
        for _, el in ET.iterparse(f):
            if el.tag != "entry":
                continue
            kebs = [k.text for k in el.iter("keb")]
            rebs = [r.text for r in el.iter("reb")]
            en, es, examples = [], [], []
            for sense in el.iter("sense"):
                g_en = [g.text for g in sense.findall("gloss") if g.text and g.get(XML_LANG, "eng") == "eng"]
                g_es = [g.text for g in sense.findall("gloss") if g.text and g.get(XML_LANG) == "spa"]
                if g_en:
                    en.append("; ".join(g_en))
                if g_es:
                    es.append("; ".join(g_es))
                for ex in sense.findall("example"):
                    sents = {s.get(XML_LANG): s.text for s in ex.findall("ex_sent")}
                    if "jpn" in sents and "eng" in sents:
                        examples.append((sents["jpn"], sents["eng"], ex.findtext("ex_text")))
            entry = {"en": en, "es": es, "examples": examples}
            for r in rebs:
                for k in kebs or [r]:
                    key = (k, r)
                    if key in index:  # mezcla: conserva el que tenga más datos
                        prev = index[key]
                        for fld in ("en", "es", "examples"):
                            if not prev[fld]:
                                prev[fld] = entry[fld]
                    else:
                        index[key] = dict(entry)
            el.clear()
    return index


def main() -> int:
    for name in ("kanjidic2.xml.gz", "kanji.json", "JMdict.gz", "JMdict_e_examp.gz"):
        if not (RAW / name).exists():
            print(f"Falta {RAW / name}. Ver docs/DATA_SOURCES.md", file=sys.stderr)
            return 1

    print("KANJIDIC2…")
    kd = load_kanjidic()
    levels = json.loads((RAW / "kanji.json").read_text(encoding="utf-8"))

    print("JMdict (glosas EN/ES)…")
    jm = load_jmdict(RAW / "JMdict.gz")
    print("JMdict (ejemplos)…")
    jm_ex = load_jmdict(RAW / "JMdict_e_examp.gz")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.unlink(missing_ok=True)
    db = sqlite3.connect(OUT)
    db.executescript(SCHEMA)

    n_kanji = 0
    for ch, info in levels.items():
        lvl = info.get("jlpt_new")
        if not lvl or ch not in kd:
            continue
        k = kd[ch]
        db.execute(
            "INSERT INTO kanji(char,jlpt,strokes,freq,onyomi,kunyomi,meanings_en,meanings_es) VALUES (?,?,?,?,?,?,?,?)",
            (ch, lvl, info.get("strokes"), info.get("freq"), json.dumps(k["on"], ensure_ascii=False),
             json.dumps(k["kun"], ensure_ascii=False), json.dumps(k["en"], ensure_ascii=False),
             json.dumps(k["es"], ensure_ascii=False)),
        )
        n_kanji += 1

    n_vocab = n_es = n_ex = 0
    for lvl in (5, 4, 3, 2, 1):
        with open(RAW / f"jlpt_vocab_n{lvl}.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                word, reading = clean_term(row["expression"]), clean_term(row["reading"])
                if not word or not reading:
                    continue
                hit = jm.get((word, reading)) or {}
                ex_hit = jm_ex.get((word, reading)) or {}
                en = hit.get("en") or [row["meaning"]]
                es = hit.get("es") or []
                ex = next((e for e in ex_hit.get("examples", []) if e[2] and e[2] in e[0]), None)
                cur = db.execute(
                    "INSERT OR IGNORE INTO vocab(word,reading,jlpt,meanings_en,meanings_es,example_ja,example_en,example_target)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (word, reading, lvl, json.dumps(en[:3], ensure_ascii=False), json.dumps(es[:3], ensure_ascii=False),
                     ex[0] if ex else None, ex[1] if ex else None, ex[2] if ex else None),
                )
                if cur.rowcount:
                    n_vocab += 1
                    n_es += bool(es)
                    n_ex += bool(ex)

    meta = {
        "built_with": "tools/build_content.py",
        "jlpt_notice": "Los niveles JLPT son no oficiales (listas de Jonathan Waller); la JLPT no publica listas desde 2010.",
        "licenses": "KANJIDIC2/JMdict: EDRDG CC BY-SA 4.0. Ejemplos: Tatoeba CC BY 2.0 FR. Listas JLPT: J. Waller CC BY. kanji-data: MIT.",
        "kanji_count": str(n_kanji), "vocab_count": str(n_vocab),
    }
    db.executemany("INSERT INTO meta VALUES (?,?)", meta.items())
    db.commit()
    db.execute("VACUUM")
    db.close()
    print(f"kanji={n_kanji} vocab={n_vocab} vocab_con_es={n_es} vocab_con_ejemplo={n_ex} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
