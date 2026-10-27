"""Mascota: personajes, reacciones, configuración persistente y ventana (sin pantalla)."""
import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture()
def win(qapp, tmp_path):
    os.environ["NIHONGO_DESK_HOME"] = str(tmp_path)
    from nihongo_desk.ui.main_window import MainWindow
    w = MainWindow()
    w.db.set("sounds", False)
    w.show_window()
    w.mascot.notify("app_started")
    yield w
    w.quit()
    qapp.processEvents()


def test_characters_have_all_expressions(qapp):
    from nihongo_desk.mascot.character import EXPRESSIONS, all_characters
    chars = all_characters(reload=True)
    assert {"momo", "kurumi"} <= set(chars)
    for c in chars.values():
        assert set(EXPRESSIONS) <= set(c.available()), c.id
        assert c.has("neutral_blink") and c.has("happy_talk")
        pm = c.frame("happy", "blink", 200)
        assert pm.height() == 200 and not pm.isNull()


def test_new_character_with_single_image_falls_back(qapp, tmp_path):
    from nihongo_desk.mascot.character import Character, all_characters
    src = next(iter(all_characters().values())).files["neutral"]
    folder = tmp_path / "solo"
    (folder / "expressions").mkdir(parents=True)
    (folder / "expressions" / ("neutral" + src.suffix)).write_bytes(src.read_bytes())
    (folder / "manifest.json").write_text(json.dumps({"id": "solo", "name": {"es": "Solo"}}), encoding="utf-8")
    c = Character.load(folder)
    for e in ("celebrating", "sleeping", "confused", "inventada"):
        assert c.resolve(e) == "neutral"
    assert not c.frame("celebrating", "blink", 120).isNull()


def test_reactions_follow_study_events(win):
    mc = win.mascot
    played = []
    view = mc.window.view
    orig = view.play
    view.play = lambda r: (played.append(r.expr), orig(r))
    mc.notify("session_start")
    assert view.mood == "focused" or mc.pers.idle_mood == "focused"
    for _ in range(3):
        mc.notify("answer", ok=True)
    assert played[-1] == mc.pers.reactions["streak3"].expr
    mc.notify("answer", ok=False)
    assert played[-1] == mc.pers.reactions["wrong"].expr
    mc.cfg.set("react_wrong", False)
    n = len(played)
    mc.notify("answer", ok=False)
    assert len(played) == n           # desactivado: no reacciona
    mc.notify("session_end", accuracy=0.9)
    assert played[-1] == mc.pers.reactions["end_good"].expr
    assert mc.in_session is False


def test_errors_never_chain_into_blame(win):
    """Un fallo nunca deja a la mascota triste: siempre termina animando o pensando."""
    from nihongo_desk.mascot.personality import PERSONALITIES
    for p in PERSONALITIES.values():
        for key in ("wrong", "wrong3"):
            r = p.reactions[key]
            while r.then:
                r = r.then
            assert r.expr != "sad", (p.id, key)


def test_settings_persist_and_apply_live(win):
    mc = win.mascot
    mc.cfg.update(bg_mode="solid", bg_color="#fde4ec", size=200, character="kurumi", personality="shy")
    mc.load_character()
    mc.apply()
    assert mc.window.view.bg_mode == "solid" and mc.window.view.char.id == "kurumi"
    assert mc.window.view.char_h == 200 and mc.pers.id == "shy"
    stored = win.db.get("mascot")
    assert stored["bg_color"] == "#fde4ec" and stored["character"] == "kurumi"
    mc.cfg.reset_appearance()
    mc.load_character()
    mc.apply()
    assert mc.cfg["bg_mode"] == "transparent" and mc.char.id == "momo" and mc.cfg["size"] == 280


def test_visibility_rules(win):
    mc = win.mascot
    assert mc.window.isVisible()
    win.toggle_game_mode()
    assert not mc.window.isVisible()
    win.toggle_game_mode()
    assert mc.window.isVisible()
    win.hide_window()
    assert not mc.window.isVisible()
    win.show_window()
    assert mc.window.isVisible()
    mc.cfg.update(mode="integrated")
    mc.apply()
    assert not mc.window.isVisible() and win.mascot_strip.isVisible()
    mc.cfg.update(mode="off")
    mc.apply()
    assert not win.mascot_strip.isVisible()


def test_sleep_and_wake(win):
    mc = win.mascot
    mc.cfg.update(sleep=True, sleep_minutes=1)
    mc.last_activity = time.monotonic() - 120
    mc._idle_tick()
    assert mc.sleeping and mc.window.view.mood == "sleeping"
    mc._wake()
    assert not mc.sleeping and mc.window.view.mood != "sleeping"


def test_mascot_screen_builds(win):
    win.open_module("mascot")
    from nihongo_desk.ui.screens.mascot import MascotScreen
    scr = win.stack.currentWidget()
    assert isinstance(scr, MascotScreen)
    scr._set_color("#123456")
    assert win.mascot.cfg["bg_color"] == "#123456" and win.mascot.cfg["bg_mode"] == "solid"
    win.mascot.preview("celebrating")
    win.set_language("en")
    win.set_language("es")
