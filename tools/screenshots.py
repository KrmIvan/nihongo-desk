"""Genera capturas de todas las pantallas en docs/screens/ (sin mostrar ventanas).

Uso:  QT_QPA_PLATFORM=offscreen python tools/screenshots.py
Usa un perfil temporal con algo de progreso simulado para que las estadísticas tengan datos.
"""
from __future__ import annotations

import os
import random
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["NIHONGO_DESK_HOME"] = tempfile.mkdtemp(prefix="nd_shots_")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

OUT = ROOT / "docs" / "screens"


def seed(db):
    rng = random.Random(3)
    now = time.time()
    keys = [f"h:{c}" for c in "あいうえおかきくけこさしすせそたちつてとなにぬねの"]
    for day in range(6, -1, -1):
        for k in rng.sample(keys, 12):
            db.record("kana", k, 0, "choice", rng.random() > 0.25, rng.randint(1500, 5000), now - day * 86400 - 600)
    for c in "日月火水木金土人山川":
        db.record("kanji", c, 5, "meaning", rng.random() > 0.3, 3000, now - 2 * 86400)
    db.set("last_module", "kana")


def main():
    app = QApplication(sys.argv)
    from nihongo_desk.ui import theme
    from nihongo_desk.ui.main_window import MainWindow
    app.setFont(theme.app_font())
    OUT.mkdir(parents=True, exist_ok=True)
    win = MainWindow()
    seed(win.db)
    win.resize(420, 680)
    win.show()
    win.engine.rng.seed(7)

    def shot(name: str):
        app.processEvents()
        QTimer.singleShot(0, lambda: None)
        for _ in range(5):
            app.processEvents()
            time.sleep(0.06)
        win.grab().save(str(OUT / f"{name}.png"))
        print("captura", name)

    steps = []

    def add(fn, name):
        steps.append((fn, name))

    add(win.go_home, "01_inicio")
    add(lambda: win.open_module("kana"), "02_kana_seleccion")
    add(lambda: win.open_module("kanji"), "03_kanji_nivel")
    add(lambda: win.open_module("vocab"), "04_vocab_nivel")
    add(lambda: win.start_module_session("kana", {"scripts": ["h"], "groups": ["a", "ka", "na"],
                                                  "exercise": "choice", "difficulty": "normal"}, 10, "Kana · Hiragana"),
        "05_sesion_kana_pregunta")

    def answer_wrong():
        scr = win.stack.currentWidget()
        scr.choose((scr.q.answer_index + 1) % len(scr.q.options))
    add(answer_wrong, "06_sesion_kana_fallo")

    def kana_write():
        win.start_module_session("kana", {"scripts": ["k"], "groups": ["sa", "ta"], "exercise": "write",
                                          "difficulty": "normal"}, 10, "Kana · Katakana")
        scr = win.stack.currentWidget()
        scr.text_input.raw = list(scr.q.accepted)[0]
        scr.text_input.setText(scr.text_input.raw)
        scr.main_action()
    add(kana_write, "07_sesion_kana_escrita_acierto")

    def kanji_q():
        win.start_module_session("kanji", {"levels": [5], "exercise": "meaning"}, 10, "Kanji · N5")
        scr = win.stack.currentWidget()
        scr.choose(scr.q.answer_index)
    add(kanji_q, "08_sesion_kanji_ficha")

    def vocab_q():
        win.start_module_session("vocab", {"levels": [5], "exercise": "reading_write"}, 10, "Vocabulario · N5")
    add(vocab_q, "09_sesion_vocab_escribir")

    add(lambda: win.start_module_session("kanji", {"levels": [5], "exercise": "match"}, 6, "Kanji · N5"),
        "10_sesion_kanji_relacionar")
    add(lambda: win.open_module("grammar"), "11_gramatica_nivel")

    def grammar_q():
        win.start_module_session("grammar", {"levels": [5], "exercise": "particle"}, 10, "Gramática · N5")
        scr = win.stack.currentWidget()
        scr.choose(scr.q.answer_index)
    add(grammar_q, "12_sesion_gramatica_particula")

    def grammar_order():
        win.start_module_session("grammar", {"levels": [5], "exercise": "order"}, 10, "Gramática · N5")
        scr = win.stack.currentWidget()
        scr.order._add(0)
    add(grammar_order, "13_sesion_gramatica_ordenar")

    def summary():
        from nihongo_desk.exercises.session import Session
        s = Session("kana", "Kana · Hiragana", [{}] * 10, answered=10, correct=8, seconds=94,
                    missed=[("ぬ", "ぬ = nu"), ("め", "め = me")])
        win.finish_session(s)
    add(summary, "14_resumen")
    add(lambda: win.open_module("stats"), "15_estadisticas")
    add(lambda: win.open_module("settings"), "16_configuracion")
    add(lambda: (win.set_language("en"), win.go_home()), "17_home_english")
    add(lambda: (win.set_theme("light"), win.set_language("es"), win.go_home()), "18_inicio_tema_claro")

    def light_session():
        win.start_module_session("vocab", {"levels": [5], "exercise": "ja_meaning"}, 10, "Vocabulario · N5")
        scr = win.stack.currentWidget()
        scr.choose(scr.q.answer_index)
    add(light_session, "19_sesion_vocab_claro")

    for fn, name in steps:
        fn()
        shot(name)
    win.set_theme("dark")
    win.quit()


if __name__ == "__main__":
    main()
