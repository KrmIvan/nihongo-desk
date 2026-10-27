"""Recorre la interfaz sin pantalla: sesiones completas de todos los módulos."""
import os
import random

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def win(tmp_path_factory):
    os.environ["NIHONGO_DESK_HOME"] = str(tmp_path_factory.mktemp("home"))
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from nihongo_desk.ui.main_window import MainWindow
    w = MainWindow()
    w.db.set("sounds", False)
    w.show()
    yield w
    w.quit()
    app.processEvents()


def answer_current(win, rng):
    from nihongo_desk.ui.screens.session import SessionScreen
    scr = win.stack.currentWidget()
    assert isinstance(scr, SessionScreen)
    q = scr.q
    good = rng.random() < 0.6
    if q.kind == "choice":
        scr.choose(q.answer_index if good else (q.answer_index + 1) % len(q.options))
    elif q.kind == "text":
        value = next(iter(q.accepted)) if good else "zzz"
        scr.text_input.raw = value
        scr.text_input.setText(value)
        scr.main_action()
    elif q.kind == "order":
        for _ in range(len(scr.order.bank)):
            scr.order._add(0)
        scr.main_action()
    elif q.kind == "match":
        for key in list(scr.match.pairs):
            scr.match._pick_left(key)
            scr.match._pick_right(key)
    assert scr.answered, q.kind
    scr.main_action()  # siguiente


def run_session(win, rng, max_q=40):
    from nihongo_desk.ui.screens.session import SessionScreen, SummaryScreen
    for _ in range(max_q):
        if isinstance(win.stack.currentWidget(), SummaryScreen):
            return True
        answer_current(win, rng)
    return isinstance(win.stack.currentWidget(), SummaryScreen) or isinstance(win.stack.currentWidget(), SessionScreen)


def test_all_modules(win):
    rng = random.Random(5)
    cases = [
        ("kana", {"scripts": ["h", "k"], "groups": ["a", "ka", "dakuten", "yoon"], "exercise": "choice", "difficulty": "hard"}),
        ("kana", {"scripts": ["k"], "groups": ["sa"], "exercise": "write", "difficulty": "normal"}),
        ("kana", {"scripts": ["h"], "groups": ["na"], "exercise": "inverse", "difficulty": "easy"}),
        ("kanji", {"levels": [5], "exercise": "mixed"}),
        ("kanji", {"levels": [5, 4], "exercise": "match"}),
        ("vocab", {"levels": [5], "exercise": "mixed"}),
        ("grammar", {"levels": [5, 4], "exercise": "mixed"}),
    ]
    for module, cfg in cases:
        win.start_module_session(module, cfg, 8, module)
        assert run_session(win, rng)
    for key in ("kana", "kanji", "vocab", "grammar", "stats", "settings"):
        win.open_module(key)
    assert win.db.totals()["answers"] > 40


def test_language_switch_and_continue(win):
    rng = random.Random(9)
    win.start_module_session("vocab", {"levels": [5], "exercise": "ja_meaning"}, 6, "vocab")
    answer_current(win, rng)
    win.set_language("en")
    scr = win.stack.currentWidget()
    assert scr.q.instruction == "What does it mean?"
    win.set_language("es")
    win.go_home()  # salir a mitad
    assert win.db.get("last_session")["index"] == 1
    win.continue_session()
    assert run_session(win, rng)
    win.start_review()
    win.start_quick()
    answer_current(win, rng)
    win.toggle_theme()
    win.toggle_game_mode()
    win.toggle_game_mode()
    win.toggle_theme()
