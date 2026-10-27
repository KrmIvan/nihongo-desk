"""Ventana flotante principal: barra de título propia, navegación y comportamiento de escritorio."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QFrame, QMenu, QSizeGrip, QStackedWidget,
                               QSystemTrayIcon, QToolButton, QWidget)

from ..content.repository import ContentRepo
from ..core import i18n
from ..core.i18n import t
from ..core.paths import assets_dir, resources_dir, user_data_dir
from ..core.userdb import UserDB
from ..exercises.engine import Engine
from ..exercises.session import Session
from ..mascot import MascotController
from ..platform.hotkey import HotkeyManager
from . import theme
from .screens.home import HomeScreen
from .screens.kana_setup import KanaSetupScreen
from .screens.level_setup import LevelSetupScreen
from .screens.mascot import MascotScreen
from .screens.session import SessionScreen, SummaryScreen
from .screens.settings import SettingsScreen
from .screens.stats import StatsScreen
from .sounds import Sounds
from .widgets import fade_in, hbox, label, vbox

DEFAULT_SIZE = (400, 640)
COMPACT_SIZE = (360, 540)


def app_icon() -> QIcon:
    daruma = assets_dir() / "icons" / "daruma.png"
    if daruma.is_file():
        return QIcon(str(daruma))
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#e2574c"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(4, 4, 56, 56, 12, 12)
    p.setPen(QColor("white"))
    p.setFont(theme.jp_font(38, QFont.Weight.Bold))
    p.drawText(QRect(4, 2, 56, 56), Qt.AlignmentFlag.AlignCenter, "日")
    p.end()
    return QIcon(pm)


class TitleBar(QFrame):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.setObjectName("TitleBar")
        self.setFixedHeight(40)
        lay = hbox(self, (10, 0, 6, 0), 4)

        def tb(text: str, tip: str, cb, checkable=False, name="TitleBtn") -> QToolButton:
            b = QToolButton()
            b.setObjectName(name)
            b.setText(text)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(cb)
            return b

        self.back = tb("←", t("back"), win.go_home)
        lay.addWidget(self.back)
        logo = label()
        logo.setFixedSize(24, 24)
        logo.setPixmap(app_icon().pixmap(24, 24))
        lay.addWidget(logo)
        self.name = label(t("app.title"))
        self.name.setObjectName("AppName")
        lay.addWidget(self.name)
        lay.addStretch()
        self.lang = tb("", t("tip.lang"), win.toggle_language, name="LangBtn")
        lay.addWidget(self.lang)
        self.game = tb("遊", t("tip.game"), win.toggle_game_mode, checkable=True)
        lay.addWidget(self.game)
        self.theme = tb("◐", t("tip.theme"), win.toggle_theme)
        lay.addWidget(self.theme)
        self.dock_l = tb("⇤", t("tip.dock_left"), lambda: win.dock("left"))
        self.dock_r = tb("⇥", t("tip.dock_right"), lambda: win.dock("right"))
        lay.addWidget(self.dock_l)
        lay.addWidget(self.dock_r)
        self.pin = tb("◆", t("tip.pin"), win.toggle_pin, checkable=True)
        lay.addWidget(self.pin)
        self.hide_btn = tb("—", "", win.hide_window)
        lay.addWidget(self.hide_btn)
        self.refresh()

    def refresh(self):
        db = self.win.db
        self.lang.setText("ES" if db.get("language") == "es" else "EN")
        self.pin.setChecked(self.win.effective_on_top())
        self.pin.setText("◆" if self.pin.isChecked() else "◇")
        self.game.setChecked(bool(db.get("game_mode")))
        self.hide_btn.setToolTip(t("tip.hide", hotkey=db.get("hotkey")))
        for b, key in ((self.lang, "tip.lang"), (self.game, "tip.game"), (self.theme, "tip.theme"),
                       (self.dock_l, "tip.dock_left"), (self.dock_r, "tip.dock_right"), (self.pin, "tip.pin"),
                       (self.back, "back")):
            b.setToolTip(t(key))
        self.name.setText(t("app.title"))

    # arrastrar la ventana / doble clic para tamaño compacto
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            handle = self.win.windowHandle()
            if handle and handle.startSystemMove():
                return
            self._drag = e.globalPosition().toPoint() - self.win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if getattr(self, "_drag", None) is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.win.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None
        self.win.save_geometry_soon()

    def mouseDoubleClickEvent(self, e):
        self.win.toggle_compact()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.db = UserDB(user_data_dir() / "user.db")
        self.repo = ContentRepo(resources_dir())
        self.engine = Engine(self.repo, self.db)
        self.sounds = Sounds(user_data_dir())
        i18n.set_language(self.db.get("language"))
        theme.set_current(self.db.get("theme"))
        self.route: tuple = ("home",)
        self.current_session: Session | None = None

        self.setWindowTitle("Nihongo Desk")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(320, 420)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)

        root = QFrame(self)
        root.setObjectName("Root")
        outer = vbox(self)
        outer.addWidget(root)
        lay = vbox(root, (1, 1, 1, 1), 0)
        self.title = TitleBar(self)
        lay.addWidget(self.title)
        self.mascot_strip = QFrame()
        self.mascot_strip.setObjectName("MascotStrip")
        self.mascot_strip_lay = vbox(self.mascot_strip, (6, 2, 6, 2), 0)
        self.mascot_strip.hide()
        lay.addWidget(self.mascot_strip)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)
        self.grip = QSizeGrip(self)
        self.grip.resize(16, 16)

        self._geo_timer = QTimer(self, singleShot=True, interval=500, timeout=self._save_geometry)
        self.hotkeys = HotkeyManager()
        self.hotkeys.activated.connect(self.toggle_visible)
        self.hotkeys.register(self.db.get("hotkey"))
        self.mascot = MascotController(self)
        self._setup_tray()

        self.apply_theme()
        self.apply_window_flags()
        self.setWindowOpacity(float(self.db.get("opacity")))
        self._restore_geometry()
        self.go_home()

    # =================================================================
    # navegación
    # =================================================================
    def _show(self, widget: QWidget, route: tuple):
        old = self.stack.currentWidget()
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)
        if old is not None:
            self.stack.removeWidget(old)
            old.deleteLater()
        self.route = route
        self.title.back.setVisible(route[0] not in ("home", "session"))
        self.title.name.setVisible(route[0] in ("home", "session"))
        fade_in(widget, 180)
        widget.setFocus()

    def toast(self, text: str, ms: int = 2600):
        """Aviso breve no bloqueante sobre la parte inferior de la ventana."""
        lb = label(text, wrap=True)
        lb.setParent(self)
        lb.setObjectName("Toast")
        lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lb.setFixedWidth(self.width() - 48)
        lb.adjustSize()
        lb.move(24, self.height() - lb.height() - 80)
        lb.show()
        lb.raise_()
        fade_in(lb, 200)
        QTimer.singleShot(ms, lb.deleteLater)

    def go_home(self):
        self.current_session = None
        self._show(HomeScreen(self), ("home",))
        self.mascot.notify("home")

    def open_module(self, key: str):
        if key == "kana":
            self._show(KanaSetupScreen(self), ("kana",))
        elif key in ("kanji", "vocab", "grammar"):
            self._show(LevelSetupScreen(self, key), ("level", key))
        elif key == "review":
            self.start_review()
        elif key == "stats":
            self._show(StatsScreen(self), ("stats",))
        elif key == "settings":
            self._show(SettingsScreen(self), ("settings",))
        elif key == "mascot":
            self._show(MascotScreen(self), ("mascot",))
        if key in ("kana", "kanji", "vocab", "grammar"):
            self.db.set("last_module", key)

    def _setups(self) -> dict:
        return {m: self.db.get(f"{m}_setup") for m in ("kana", "kanji", "vocab", "grammar")}

    def _start(self, session: Session):
        if not session.specs:
            msg = {"review": "session.no_due"}.get(session.module, "session.empty")
            if session.origin.get("cfg", {}).get("weak_only"):
                msg = "session.empty.weak"
            self.toast(t(msg))
            return
        self.current_session = session
        self.save_session(session)
        self.mascot.notify("session_start")
        self._show(SessionScreen(self, session), ("session",))

    def start_module_session(self, module: str, cfg: dict, n: int, title: str):
        specs = self.engine.plan(module, cfg, n)
        self._start(Session(module, title, specs, origin={"kind": "module", "module": module, "cfg": cfg, "n": n}))

    def start_review(self):
        specs = self.engine.plan_review(self.db.get("review_modules"), self._setups())
        self._start(Session("review", t("home.review_now"), specs, origin={"kind": "review"}))

    def start_quick(self):
        minutes = int(self.db.get("quick_minutes"))
        specs = self.engine.plan_quick(self.db.get("review_modules"), self._setups(), self.db.get("last_module"))
        self._start(Session("quick", t("home.quick", m=minutes), specs, origin={"kind": "quick"},
                            time_limit=minutes * 60))

    def continue_session(self):
        data = self.db.get("last_session")
        if data:
            s = Session.from_json(data)
            self.current_session = s
            self.mascot.notify("session_start")
            self._show(SessionScreen(self, s), ("session",))

    def save_session(self, s: Session):
        self.db.set("last_session", None if s.finished() else s.to_json())

    def discard_session(self):
        self.db.set("last_session", None)

    def finish_session(self, s: Session):
        self.db.set("last_session", None)
        self._show(SummaryScreen(self, s), ("summary",))
        self.mascot.notify("session_end", accuracy=s.correct / s.answered if s.answered else 0.0)

    def again(self, s: Session):
        o = s.origin
        if o.get("kind") == "module":
            self.start_module_session(o["module"], o["cfg"], o["n"], s.title)
        elif o.get("kind") == "quick":
            self.start_quick()
        else:
            self.start_review()

    def rebuild_current(self):
        kind = self.route[0]
        if kind == "session" and self.current_session:
            self.stack.currentWidget().retranslate()
        elif kind == "summary":
            pass
        elif kind == "level":
            self.open_module(self.route[1])
        elif kind in ("kana", "stats", "settings", "mascot"):
            self.open_module(kind)
        else:
            self.go_home()

    # =================================================================
    # apariencia
    # =================================================================
    def apply_theme(self):
        theme.set_current(self.db.get("theme"))
        QApplication.instance().setStyleSheet(theme.stylesheet(self.db.get("theme")))

    def set_theme(self, name: str):
        self.db.set("theme", name)
        self.apply_theme()
        self.rebuild_current()

    def toggle_theme(self):
        self.set_theme("light" if self.db.get("theme") == "dark" else "dark")

    def set_language(self, lang: str):
        self.db.set("language", lang)
        i18n.set_language(lang)
        self.title.refresh()
        self._retranslate_tray()
        self.rebuild_current()

    def toggle_language(self):
        self.set_language("en" if self.db.get("language") == "es" else "es")

    def play(self, name: str):
        if self.db.get("sounds") and not self.db.get("game_mode"):
            self.sounds.play(name)

    # =================================================================
    # ventana: siempre visible, modo juego, acoplado, geometría
    # =================================================================
    def effective_on_top(self) -> bool:
        if self.db.get("game_mode"):
            return bool(self.db.get("game_on_top"))
        return bool(self.db.get("always_on_top"))

    def apply_window_flags(self):
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.effective_on_top())
        if visible:  # cambiar las flags oculta la ventana: se vuelve a mostrar
            self.show()
        self.title.refresh()

    def toggle_pin(self):
        key = "game_on_top" if self.db.get("game_mode") else "always_on_top"
        self.db.set(key, not self.db.get(key))
        self.apply_window_flags()

    def apply_game_mode(self):
        on = bool(self.db.get("game_mode"))
        if on and self.db.get("game_compact"):
            if not self.db.get("geometry_normal"):
                g = self.geometry()
                self.db.set("geometry_normal", [g.x(), g.y(), g.width(), g.height()])
            self.resize(*COMPACT_SIZE)
        elif not on and self.db.get("geometry_normal"):
            self.setGeometry(*self.db.get("geometry_normal"))
            self.db.set("geometry_normal", None)
        self.apply_window_flags()

    def toggle_game_mode(self):
        self.db.set("game_mode", not self.db.get("game_mode"))
        self.apply_game_mode()
        self.mascot.notify("game_mode")
        if self.route[0] == "settings":
            self.open_module("settings")

    def toggle_compact(self):
        w, h = COMPACT_SIZE if self.width() > COMPACT_SIZE[0] + 10 else DEFAULT_SIZE
        self.resize(w, h)
        self.save_geometry_soon()

    def dock(self, side: str):
        screen = (self.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        w = min(self.width(), screen.width())
        h = screen.height() - 16
        x = screen.left() + 8 if side == "left" else screen.right() - w - 8
        self.setGeometry(x, screen.top() + 8, w, h)
        self.save_geometry_soon()

    def _restore_geometry(self):
        geo = self.db.get("geometry")
        if geo:
            rect = QRect(*geo)
            if any(s.availableGeometry().intersects(rect) for s in QGuiApplication.screens()):
                self.setGeometry(rect)
                return
        screen = QGuiApplication.primaryScreen().availableGeometry()
        w, h = DEFAULT_SIZE
        self.setGeometry(screen.right() - w - 24, screen.top() + (screen.height() - h) // 2, w, h)

    def save_geometry_soon(self):
        self._geo_timer.start()

    def _save_geometry(self):
        if self.db.get("game_mode") and self.db.get("game_compact"):
            return  # el tamaño compacto no sustituye al tamaño normal guardado
        g = self.geometry()
        self.db.set("geometry", [g.x(), g.y(), g.width(), g.height()])

    def moveEvent(self, e):
        super().moveEvent(e)
        self.save_geometry_soon()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.grip.move(self.width() - self.grip.width() - 2, self.height() - self.grip.height() - 2)
        self.grip.raise_()
        self.save_geometry_soon()

    # =================================================================
    # mostrar / ocultar, atajo, bandeja
    # =================================================================
    def toggle_visible(self):
        if self.isVisible() and self.isActiveWindow():
            self.hide_window()
        else:
            self.show_window()

    def show_window(self):
        was_visible = self.isVisible()
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.raise_()
        self.activateWindow()
        if not was_visible:
            self.mascot.notify("app_shown")

    def hide_window(self):
        self._save_geometry()
        self.hide()
        self.mascot.notify("app_hidden")

    def notify_mascot(self, event: str, **data):
        self.mascot.notify(event, **data)

    def apply_mascot_strip(self):
        """Muestra la mascota integrada (busto) bajo la barra de título si ese es el modo elegido."""
        on = self.mascot.cfg["mode"] == "integrated" and self.mascot.char is not None
        if on and self.mascot_strip_lay.count() == 0:
            self.mascot_strip_lay.addWidget(self.mascot.make_embedded())
        self.mascot_strip.setVisible(on)

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == e.Type.ActivationChange and not self.isActiveWindow():
            if self.db.get("game_mode") and self.db.get("game_auto_hide"):
                QTimer.singleShot(250, self._auto_hide)

    def _auto_hide(self):
        if QApplication.activeWindow() is None and QApplication.activeModalWidget() is None and self.isVisible():
            self.hide_window()

    def set_hotkey(self, seq: str):
        if self.hotkeys.register(seq):
            self.db.set("hotkey", seq)
        else:
            self.hotkeys.register(self.db.get("hotkey"))  # vuelve al anterior
            self.hotkeys.status = "fail"
            self.hotkeys.sequence = seq
        self.title.refresh()

    def hotkey_status(self) -> str:
        st, seq = self.hotkeys.status, self.hotkeys.sequence
        if st == "ok":
            return t("set.hotkey.ok", k=seq)
        if st == "wayland":
            return t("set.hotkey.wayland")
        return t("set.hotkey.fail", k=seq)

    def _setup_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        menu = QMenu()
        self.act_show = QAction(menu)
        self.act_show.triggered.connect(self.toggle_visible)
        self.act_quit = QAction(menu)
        self.act_quit.triggered.connect(self.quit)
        self.act_mascot = QAction(menu)
        self.act_mascot.triggered.connect(self.mascot.toggle_floating)
        self.act_mascot_input = QAction(menu)
        self.act_mascot_input.triggered.connect(lambda: (self.mascot.cfg.set("click_through", False), self.mascot.apply()))
        menu.addAction(self.act_show)
        menu.addAction(self.act_mascot)
        menu.addAction(self.act_mascot_input)
        menu.addSeparator()
        menu.addAction(self.act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.toggle_visible()
                                    if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self._retranslate_tray()
        self.tray.show()

    def _retranslate_tray(self):
        if self.tray:
            self.act_show.setText(t("tray.show"))
            self.act_quit.setText(t("tray.quit"))
            self.act_mascot.setText(t("tray.mascot"))
            self.act_mascot_input.setText(t("tray.mascot_input"))
            self.tray.setToolTip(f"Nihongo Desk · {self.db.get('hotkey')}")

    def handle_command(self, cmd: str):
        if cmd == "toggle":
            self.toggle_visible()
        elif cmd == "show":
            self.show_window()
        elif cmd == "quit":
            self.quit()

    def closeEvent(self, e):
        if self.db.get("close_to_tray") and self.tray and not getattr(self, "_quitting", False):
            e.ignore()
            self.hide_window()
            if not self.db.get("game_mode") and not self.db.get("tray_notice_shown"):
                self.tray.showMessage("Nihongo Desk", t("tray.hidden", k=self.db.get("hotkey")), app_icon(), 3000)
                self.db.set("tray_notice_shown", True)
            return
        self._save_geometry()
        self.hotkeys.unregister()
        self.mascot.shutdown()
        e.accept()
        QApplication.instance().quit()

    def quit(self):
        self._quitting = True
        self.close()
