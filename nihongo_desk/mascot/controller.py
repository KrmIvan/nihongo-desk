"""Conecta los eventos de estudio con las reacciones de la mascota.

La aplicación solo llama a ``controller.notify(evento, **datos)``; el motor
de ejercicios no sabe nada de la mascota. Eventos:

    app_started · app_shown · app_hidden · game_mode · home
    session_start · answer(ok) · session_end(accuracy)
"""
from __future__ import annotations

import random
import time

from PySide6.QtCore import QEvent, QObject, QPoint, QTimer
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QApplication, QMenu

from ..core.i18n import language, t
from . import personality as P
from . import strings  # noqa: F401  (registra los textos)
from .animator import MascotView
from .character import Character, all_characters, get_character
from .config import MascotConfig
from .window import MascotWindow

SIZES = [("S", 180), ("M", 240), ("L", 300), ("XL", 380)]
MIN_SIZE, MAX_SIZE = 140, 520
CHAT_GAP_S = 25          # silencio mínimo entre frases normales
BACK_AFTER_S = 60        # saluda al volver si estuvo oculta al menos esto


class MascotController(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.cfg = MascotConfig(app.db)
        self.rng = random.Random()
        self.window: MascotWindow | None = None
        self.embedded: MascotView | None = None
        self.preview_views: list[MascotView] = []
        self.char: Character | None = None
        self.pers = P.get("calm")
        self.in_session = False
        self.streak = 0
        self.wrong_streak = 0
        self.last_chat = 0.0
        self.last_activity = time.monotonic()
        self.hidden_at: float | None = None
        self.sleeping = False
        self.next_fidget = time.monotonic() + self.rng.uniform(50, 110)
        self._win_key = None
        self.idle_timer = QTimer(self, interval=5000, timeout=self._idle_tick)
        self.idle_timer.start()
        QApplication.instance().installEventFilter(self)
        self.load_character()

    # ================================================================ personaje
    def load_character(self):
        self.char = get_character(self.cfg["character"])
        pid = self.cfg["personality"] or (self.char.personality if self.char else "calm")
        self.pers = P.get(pid)

    def characters(self) -> dict[str, Character]:
        return all_characters()

    def set_character(self, cid: str):
        self.cfg.update(character=cid, personality=None)
        self.load_character()
        self.apply()
        self.react("greet_first", force_phrase=False)

    def set_personality(self, pid: str):
        self.cfg.set("personality", pid)
        self.load_character()
        self.apply()
        self.react("pet")

    # ================================================================ vistas
    def views(self) -> list[MascotView]:
        vs = [v for v in (self.window.view if self.window else None, self.embedded) if v is not None]
        return vs + [v for v in self.preview_views if v is not None]

    def _configure(self, v: MascotView, floating: bool):
        v.set_character(self.char)
        v.set_personality(self.pers)
        v.set_flags(animations=self.cfg["animations"], blink=self.cfg["blink"], idle_moves=self.cfg["idle_moves"])
        if floating:
            v.set_height(self.cfg["size"])
            v.set_background(self.cfg["bg_mode"], self.cfg["bg_color"])
        v.set_mood(self._mood())

    def make_embedded(self) -> MascotView:
        """Vista de busto para el panel principal (la coloca MainWindow)."""
        if self.embedded is None:
            self.embedded = MascotView("bust")
            self.embedded.set_height(92)
        self._configure(self.embedded, False)
        return self.embedded

    def make_preview(self, height: int = 230) -> MascotView:
        v = MascotView("full")
        v.set_height(height)
        self._configure(v, False)
        v.set_background(self.cfg["bg_mode"], self.cfg["bg_color"])
        self.preview_views = [p for p in self.preview_views if _alive(p)] + [v]
        v.destroyed.connect(lambda *_: self._drop_preview(v))
        return v

    def _drop_preview(self, v):
        self.preview_views = [p for p in self.preview_views if p is not v and _alive(p)]

    def floating_wanted(self) -> bool:
        c = self.cfg
        if not self.char or c["mode"] != "floating" or not c["visible"]:
            return False
        if c["hide_in_game"] and self.app.db.get("game_mode"):
            return False
        if c["follow_app"] and not self.app.isVisible():
            return False
        return True

    def apply(self):
        """Aplica la configuración actual sin reiniciar (recrea la ventana si cambian sus banderas)."""
        self.preview_views = [p for p in self.preview_views if _alive(p)]
        c = self.cfg
        key = (c["bg_mode"] == "transparent", bool(c["on_top"]), bool(c["click_through"]))
        if self.window and key != self._win_key:  # transparencia y banderas solo se fijan al crearla
            self.window.close()
            self.window.deleteLater()
            self.window = None
        if self.floating_wanted():
            if self.window is None:
                self.window = MascotWindow(*key)
                self._win_key = key
                self.window.clicked.connect(lambda: self.react("pet"))
                self.window.double_clicked.connect(self.app.show_window)
                self.window.moved.connect(self._moved)
                self.window.menu_requested.connect(self._menu)
                self.window.resize_requested.connect(self._wheel_resize)
                self._configure(self.window.view, True)
                self.window.sync_size()
                self.window.place(c["corner"], c["pos"])
                self.window.show()
            else:
                self._configure(self.window.view, True)
                self.window.sync_size()
            if c["corner"] != "custom":
                self.window.place(c["corner"], None)
            if not self.window.isVisible():
                self.window.show()
        elif self.window:
            self.window.hide()
        if self.embedded is not None:
            self._configure(self.embedded, False)
        for v in self.preview_views:
            self._configure(v, False)
            v.set_background(c["bg_mode"], c["bg_color"])
        if hasattr(self.app, "apply_mascot_strip"):
            self.app.apply_mascot_strip()

    def _moved(self, pos: QPoint):
        self.cfg.update(corner="custom", pos=[pos.x(), pos.y()])

    def _wheel_resize(self, step: int):
        self.set_size(self.cfg["size"] + 20 * step)

    def set_size(self, h: int):
        self.cfg.set("size", max(MIN_SIZE, min(MAX_SIZE, int(h))))
        self.apply()

    def toggle_floating(self):
        if self.cfg["mode"] != "floating":
            self.cfg.update(mode="floating", visible=True)
        else:
            self.cfg.set("visible", not (self.window and self.window.isVisible()))
        self.apply()

    def _menu(self, at: QPoint):
        m = QMenu()
        m.addAction(t("mascot.menu.open"), self.app.show_window)
        m.addAction(t("mascot.menu.customize"), lambda: (self.app.show_window(), self.app.open_module("mascot")))
        sizes = m.addMenu(t("mascot.menu.size"))
        group = QActionGroup(sizes)
        for name, h in SIZES:
            a = QAction(f"{name} · {h}px", sizes, checkable=True)
            a.setChecked(abs(self.cfg["size"] - h) < 10)
            a.triggered.connect(lambda _=False, h=h: self.set_size(h))
            group.addAction(a)
            sizes.addAction(a)
        on_top = m.addAction(t("mascot.on_top"))
        on_top.setCheckable(True)
        on_top.setChecked(bool(self.cfg["on_top"]))
        on_top.triggered.connect(lambda v: (self.cfg.set("on_top", v), self.apply()))
        ct = m.addAction(t("mascot.click_through"))
        ct.setCheckable(True)
        ct.triggered.connect(lambda v: (self.cfg.set("click_through", v), self.apply()))
        m.addSeparator()
        m.addAction(t("mascot.menu.hide"), lambda: (self.cfg.set("visible", False), self.apply()))
        m.exec(at)

    def shutdown(self):
        if self.window:
            self.window.close()

    # ================================================================ estado de ánimo y reacciones
    def _mood(self) -> str:
        if self.sleeping:
            return "sleeping"
        return "focused" if self.in_session else self.pers.idle_mood

    def _set_mood(self):
        for v in self.views():
            v.set_mood(self._mood())

    def preview(self, expr: str):
        for v in self.views():
            v.preview(expr)

    def react(self, key: str, force_phrase: bool | None = None):
        r = self.pers.reactions.get(key)
        if r is None:
            return
        for v in self.views():
            v.play(r)
        self._maybe_say(r, force_phrase)

    def _maybe_say(self, r: P.Reaction, force: bool | None):
        while r is not None:
            if r.phrase:
                important = r.phrase in ("end_good", "end_ok", "greet_first", "greet_back")
                now = time.monotonic()
                ok = force if force is not None else (
                    self.cfg["messages"] and self.rng.random() < min(1.0, r.chance * self.pers.chattiness)
                    and (important or now - self.last_chat > CHAT_GAP_S))
                if ok:
                    ph = P.phrase(self.pers, r.phrase, self.rng)
                    if ph:
                        self.last_chat = now
                        self._say(ph)
                    return
            r = r.then

    def _say(self, ph: tuple[str, str, str]):
        ja, es, en = ph
        tr = (es if language() == "es" else en) if self.cfg["translation"] else ""
        for v in self.views():
            v.say(ja, tr)

    # ================================================================ eventos de la app
    def notify(self, event: str, **data):
        c = self.cfg
        if event == "app_started":
            self.apply()
            if c["greetings"]:
                QTimer.singleShot(600, lambda: self.react("greet_first"))
        elif event == "app_shown":
            away = self.hidden_at is not None and time.monotonic() - self.hidden_at > BACK_AFTER_S
            self.hidden_at = None
            self.apply()
            self._wake(silent=True)
            if away and c["greetings"]:
                QTimer.singleShot(300, lambda: self.react("greet_back"))
        elif event == "app_hidden":
            self.hidden_at = time.monotonic()
            self.apply()
        elif event == "game_mode":
            self.apply()
        elif event == "home":
            self.in_session = False
            self._set_mood()
        elif event == "session_start":
            self.in_session = True
            self.streak = self.wrong_streak = 0
            self._set_mood()
        elif event == "answer":
            self._answer(bool(data.get("ok")))
        elif event == "session_end":
            self.in_session = False
            self._set_mood()
            if c["celebrations"]:
                self.react("end_good" if data.get("accuracy", 0) >= 0.8 else "end_ok")

    def _answer(self, ok: bool):
        c = self.cfg
        if ok:
            self.streak += 1
            self.wrong_streak = 0
            if c["celebrations"] and self.streak >= 5 and self.streak % 5 == 0:
                self.react("streak5")
            elif c["celebrations"] and self.streak == 3:
                self.react("streak3")
            elif c["react_correct"]:
                self.react("correct")
        else:
            self.streak = 0
            self.wrong_streak += 1
            if c["react_wrong"]:
                self.react("wrong3" if self.wrong_streak == 3 else "wrong")

    # ================================================================ inactividad
    def eventFilter(self, obj, e):
        if e.type() in (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress):
            self.last_activity = time.monotonic()
            if self.sleeping:
                self._wake()
        return False

    def _wake(self, silent: bool = False):
        self.last_activity = time.monotonic()
        if self.sleeping:
            self.sleeping = False
            self._set_mood()
            if not silent:
                self.react("wake")

    def _idle_tick(self):
        now = time.monotonic()
        c = self.cfg
        if c["sleep"] and not self.sleeping and now - self.last_activity > c["sleep_minutes"] * 60:
            self.sleeping = True
            self._set_mood()
            return
        if (c["idle_moves"] and c["animations"] and not self.sleeping and not self.in_session
                and now >= self.next_fidget):
            self.next_fidget = now + self.rng.uniform(60, 150)
            if all(v.reaction is None for v in self.views()):
                self.react("fidget")


def _alive(w) -> bool:
    try:
        w.objectName()
        return True
    except RuntimeError:
        return False
