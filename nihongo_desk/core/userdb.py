"""Base de datos local del usuario (SQLite): ajustes, estado SRS, historial."""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .srs import ItemState, review

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS items (
    module TEXT NOT NULL, item_key TEXT NOT NULL, level INTEGER NOT NULL DEFAULT 0,
    reps INTEGER NOT NULL DEFAULT 0, interval REAL NOT NULL DEFAULT 0, ease REAL NOT NULL DEFAULT 2.5,
    lapses INTEGER NOT NULL DEFAULT 0, correct INTEGER NOT NULL DEFAULT 0, wrong INTEGER NOT NULL DEFAULT 0,
    last_review REAL, due REAL,
    PRIMARY KEY (module, item_key)
);
CREATE INDEX IF NOT EXISTS items_due ON items(due);
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY, ts REAL NOT NULL, module TEXT NOT NULL, item_key TEXT NOT NULL,
    level INTEGER NOT NULL, exercise TEXT NOT NULL, correct INTEGER NOT NULL, ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS answers_ts ON answers(ts);
"""

DEFAULTS: dict[str, Any] = {
    "language": "es",                 # es | en  (interfaz y significados)
    "theme": "dark",                  # dark | light
    "always_on_top": True,
    "hotkey": "Ctrl+Shift+J",
    "geometry": None,                 # [x, y, w, h]
    "opacity": 1.0,
    "sounds": True,
    "game_mode": False,
    "game_auto_hide": True,           # ocultar al perder el foco (solo modo juego)
    "game_on_top": True,
    "game_compact": True,
    "close_to_tray": True,
    "furigana": "after",              # always | after | never
    "romaji": "never",                # after | never
    "kana_romaji_explanations": True,
    "session_questions": 15,
    "quick_minutes": 5,
    "review_modules": ["kana", "kanji", "vocab", "grammar"],
    "last_module": None,
    "kana_setup": {"scripts": ["h"], "groups": ["a", "ka", "sa", "ta", "na"], "exercise": "choice",
                   "difficulty": "normal", "weak_only": False},
    "kanji_setup": {"levels": [5], "exercise": "meaning", "weak_only": False, "picked": []},
    "vocab_setup": {"levels": [5], "exercise": "ja_meaning", "weak_only": False, "picked": []},
    "grammar_setup": {"levels": [5], "exercise": "mixed"},
    "last_session": None,
}


class UserDB:
    def __init__(self, path: Path | str):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)
        self.conn.commit()

    # ---- ajustes -------------------------------------------------------
    def get(self, key: str) -> Any:
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if row is None:
            default = DEFAULTS.get(key)
            return json.loads(json.dumps(default))  # copia
        return json.loads(row["value"])

    def set(self, key: str, value: Any) -> None:
        self.conn.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, json.dumps(value, ensure_ascii=False)))
        self.conn.commit()

    # ---- estado SRS ----------------------------------------------------
    def state(self, module: str, key: str) -> ItemState:
        row = self.conn.execute("SELECT * FROM items WHERE module=? AND item_key=?", (module, key)).fetchone()
        if row is None:
            return ItemState()
        return ItemState(**{k: row[k] for k in ("reps", "interval", "ease", "lapses", "correct", "wrong",
                                                 "last_review", "due")})

    def states(self, module: str) -> dict[str, ItemState]:
        rows = self.conn.execute("SELECT * FROM items WHERE module=?", (module,)).fetchall()
        return {r["item_key"]: ItemState(**{k: r[k] for k in ("reps", "interval", "ease", "lapses", "correct",
                                                               "wrong", "last_review", "due")}) for r in rows}

    def record(self, module: str, key: str, level: int, exercise: str, correct: bool, ms: int,
               now: float | None = None) -> ItemState:
        now = now or time.time()
        s = review(self.state(module, key), correct, now)
        self.conn.execute(
            "INSERT OR REPLACE INTO items(module,item_key,level,reps,interval,ease,lapses,correct,wrong,last_review,due)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (module, key, level, s.reps, s.interval, s.ease, s.lapses, s.correct, s.wrong, s.last_review, s.due))
        self.conn.execute("INSERT INTO answers(ts,module,item_key,level,exercise,correct,ms) VALUES (?,?,?,?,?,?,?)",
                          (now, module, key, level, exercise, int(correct), min(ms, 60_000)))
        self.conn.commit()
        return s

    def due_items(self, modules: list[str], now: float | None = None, limit: int = 200) -> list[sqlite3.Row]:
        now = now or time.time()
        marks = ",".join("?" * len(modules)) or "''"
        return self.conn.execute(
            f"SELECT module,item_key,level FROM items WHERE due<=? AND module IN ({marks}) ORDER BY due LIMIT ?",
            (now, *modules, limit)).fetchall()

    def due_count(self, modules: list[str], now: float | None = None) -> dict[str, int]:
        now = now or time.time()
        out = {m: 0 for m in modules}
        for r in self.conn.execute("SELECT module, COUNT(*) n FROM items WHERE due<=? GROUP BY module", (now,)):
            if r["module"] in out:
                out[r["module"]] = r["n"]
        return out

    def weakest(self, module: str | None = None, limit: int = 10) -> list[sqlite3.Row]:
        where = "WHERE wrong>0" + (" AND module=?" if module else "")
        args = (module,) if module else ()
        return self.conn.execute(
            f"SELECT module,item_key,level,correct,wrong, CAST(wrong AS REAL)/(correct+wrong) rate FROM items {where}"
            " ORDER BY rate DESC, wrong DESC LIMIT ?", (*args, limit)).fetchall()

    # ---- estadísticas --------------------------------------------------
    def level_progress(self, module: str) -> dict[int, dict[str, int]]:
        out: dict[int, dict[str, int]] = {}
        for r in self.conn.execute(
                "SELECT level, COUNT(*) seen, SUM(interval>=7) learned FROM items WHERE module=? GROUP BY level",
                (module,)):
            out[r["level"]] = {"seen": r["seen"], "learned": r["learned"] or 0}
        return out

    def daily_counts(self, days: int = 7, today: date | None = None) -> list[tuple[date, int, int]]:
        today = today or date.today()
        start = datetime.combine(today - timedelta(days=days - 1), datetime.min.time()).timestamp()
        counts: dict[date, list[int]] = {today - timedelta(days=i): [0, 0] for i in range(days)}
        for r in self.conn.execute("SELECT ts, correct FROM answers WHERE ts>=?", (start,)):
            d = datetime.fromtimestamp(r["ts"]).date()
            if d in counts:
                counts[d][0] += 1
                counts[d][1] += r["correct"]
        return [(d, *counts[d]) for d in sorted(counts)]

    def streak(self, today: date | None = None) -> int:
        today = today or date.today()
        days = {datetime.fromtimestamp(r[0]).date() for r in self.conn.execute("SELECT ts FROM answers")}
        d = today if today in days else today - timedelta(days=1)
        n = 0
        while d in days:
            n += 1
            d -= timedelta(days=1)
        return n

    def totals(self) -> dict[str, Any]:
        r = self.conn.execute("SELECT COUNT(*) n, COALESCE(SUM(correct),0) ok, COALESCE(SUM(ms),0) ms FROM answers").fetchone()
        t0 = datetime.combine(date.today(), datetime.min.time()).timestamp()
        today = self.conn.execute("SELECT COUNT(*) n, COALESCE(SUM(ms),0) ms FROM answers WHERE ts>=?", (t0,)).fetchone()
        return {"answers": r["n"], "correct": r["ok"], "minutes": r["ms"] / 60000,
                "today_answers": today["n"], "today_minutes": today["ms"] / 60000}

    def module_totals(self) -> dict[str, dict[str, int]]:
        out = {}
        for r in self.conn.execute("SELECT module, COUNT(*) n, COALESCE(SUM(correct),0) ok FROM answers GROUP BY module"):
            out[r["module"]] = {"answers": r["n"], "correct": r["ok"]}
        return out

    def reset_progress(self) -> None:
        self.conn.executescript("DELETE FROM items; DELETE FROM answers;")
        self.conn.commit()
