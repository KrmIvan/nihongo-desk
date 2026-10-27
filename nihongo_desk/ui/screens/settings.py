"""Configuración: general, atajo global, estudio, modo juego y datos."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence
from PySide6.QtWidgets import QGridLayout, QKeySequenceEdit, QMessageBox, QSlider, QSpinBox, QWidget

from ...core.i18n import t
from ...core.paths import user_data_dir
from ..widgets import Segmented, Toggle, button, card, hbox, label, vbox
from .common import page, section


class SettingsScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        db = app.db
        body = QWidget()
        lay = vbox(body, (16, 6, 16, 16), 10)

        def row(parent_lay, text: str, widget: QWidget, stretch_label: bool = True):
            r = hbox(spacing=10)
            r.addWidget(label(text, wrap=True), 1 if stretch_label else 0)
            r.addWidget(widget)
            parent_lay.addLayout(r)

        def toggle(parent_lay, text: str, key: str, after=None):
            tg = Toggle(text, bool(db.get(key)))

            def changed(v):
                db.set(key, v)
                if after:
                    after()
            tg.toggled.connect(changed)
            parent_lay.addWidget(tg)
            return tg

        # ---- general
        lay.addWidget(section(t("set.general")))
        g = card()
        gl = vbox(g, (14, 12, 14, 12), 10)
        lang = Segmented([("es", "Español"), ("en", "English")], db.get("language"))
        lang.changed.connect(app.set_language)
        gl.addWidget(label(t("set.language")))
        gl.addWidget(lang)
        theme_sel = Segmented([("dark", t("set.theme.dark")), ("light", t("set.theme.light"))], db.get("theme"))
        theme_sel.changed.connect(app.set_theme)
        gl.addWidget(label(t("set.theme")))
        gl.addWidget(theme_sel)
        toggle(gl, t("set.on_top"), "always_on_top", app.apply_window_flags)
        op = QSlider(Qt.Orientation.Horizontal)
        op.setRange(60, 100)
        op.setValue(int(db.get("opacity") * 100))
        op.setFixedWidth(120)
        op.valueChanged.connect(lambda v: (db.set("opacity", v / 100), app.setWindowOpacity(v / 100)))
        row(gl, t("set.opacity"), op)
        toggle(gl, t("set.sounds"), "sounds")
        toggle(gl, t("set.close_tray"), "close_to_tray")
        lay.addWidget(g)

        # ---- atajo
        lay.addWidget(section(t("set.hotkey")))
        h = card()
        hl = vbox(h, (14, 12, 14, 12), 8)
        self.key_edit = QKeySequenceEdit(QKeySequence(db.get("hotkey")))
        self.key_edit.setMaximumSequenceLength(1)
        self.key_edit.editingFinished.connect(self._hotkey_changed)
        hl.addWidget(label(t("set.hotkey.help"), wrap=True))
        hl.addWidget(self.key_edit)
        self.hotkey_status = label(app.hotkey_status(), "faint", wrap=True)
        hl.addWidget(self.hotkey_status)
        lay.addWidget(h)

        # ---- estudio
        lay.addWidget(section(t("set.study")))
        s = card()
        sl = vbox(s, (14, 12, 14, 12), 10)
        fur = Segmented([(k, t(f"set.furigana.{k}")) for k in ("always", "after", "never")], db.get("furigana"))
        fur.changed.connect(lambda v: db.set("furigana", v))
        sl.addWidget(label(t("set.furigana"), wrap=True))
        sl.addWidget(fur)
        rom = Segmented([(k, t(f"set.romaji.{k}")) for k in ("after", "never")], db.get("romaji"))
        rom.changed.connect(lambda v: db.set("romaji", v))
        sl.addWidget(label(t("set.romaji"), wrap=True))
        sl.addWidget(rom)
        toggle(sl, t("set.kana_romaji"), "kana_romaji_explanations")
        for key, text, lo, hi in (("session_questions", t("set.session_len"), 5, 50),
                                  ("quick_minutes", t("set.quick_len"), 2, 30)):
            sp = QSpinBox()
            sp.setRange(lo, hi)
            sp.setValue(int(db.get(key)))
            sp.valueChanged.connect(lambda v, k=key: db.set(k, v))
            row(sl, text, sp)
        sl.addWidget(label(t("set.review_modules"), wrap=True))
        mods = db.get("review_modules")
        mgrid = QGridLayout()
        mgrid.setSpacing(8)
        for i, m in enumerate(("kana", "kanji", "vocab", "grammar")):
            tg = Toggle(t(f"module.{m}"), m in mods)
            tg.toggled.connect(lambda v, m=m: self._toggle_review_module(m, v))
            mgrid.addWidget(tg, i // 2, i % 2)
        sl.addLayout(mgrid)
        lay.addWidget(s)

        # ---- modo juego
        lay.addWidget(section(t("set.game")))
        gm = card()
        gml = vbox(gm, (14, 12, 14, 12), 10)
        toggle(gml, t("set.game.enable"), "game_mode", app.apply_game_mode)
        gml.addWidget(label(t("set.game.help"), "faint", wrap=True))
        toggle(gml, t("set.game.auto_hide"), "game_auto_hide")
        toggle(gml, t("set.game.on_top"), "game_on_top", app.apply_window_flags)
        toggle(gml, t("set.game.compact"), "game_compact", app.apply_game_mode)
        gml.addWidget(label(t("set.game.lol"), "faint", wrap=True))
        lay.addWidget(gm)

        # ---- datos
        lay.addWidget(section(t("set.data")))
        d = card()
        dl = vbox(d, (14, 12, 14, 12), 8)
        path = str(user_data_dir())
        r = hbox(spacing=8)
        r.addWidget(label(f"{t('set.data.folder')}: {path}", "faint", wrap=True), 1)
        r.addWidget(button("📂", "chip", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(path))))
        dl.addLayout(r)
        dl.addWidget(button(t("set.data.reset"), None, self._reset))
        dl.addWidget(label(t("set.about"), "faint", wrap=True))
        lay.addWidget(d)
        lay.addStretch()
        page(self, t("settings.title"), body)

    def _toggle_review_module(self, m: str, on: bool):
        mods = set(self.app.db.get("review_modules"))
        mods.add(m) if on else mods.discard(m)
        self.app.db.set("review_modules", sorted(mods))

    def _hotkey_changed(self):
        seq = self.key_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        if seq:
            self.app.set_hotkey(seq)
        self.hotkey_status.setText(self.app.hotkey_status())

    def _reset(self):
        if QMessageBox.question(self, t("set.data.reset"), t("set.data.reset.q")) == QMessageBox.StandardButton.Yes:
            self.app.db.reset_progress()
            self.app.db.set("last_session", None)
