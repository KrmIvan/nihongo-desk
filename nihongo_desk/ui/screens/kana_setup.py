"""Selección de hiragana / katakana / ambos, grupos y tipo de ejercicio."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QPushButton, QWidget

from ...content import kana as kana_data
from ...core.i18n import t
from .. import theme
from ..widgets import ChipGroup, Segmented, Toggle, button, hbox, label, vbox
from .common import page, questions_selector, section, start_footer

SCRIPTS = [("h", "あ", "kana.hira", "ひらがな"), ("k", "ア", "kana.kata", "カタカナ"), ("hk", "あア", "kana.both", "")]


class KanaSetupScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        cfg = app.db.get("kana_setup")
        body = QWidget()
        lay = vbox(body, (16, 6, 16, 12), 10)

        # sistema: tres tarjetas grandes
        lay.addWidget(section(t("kana.system")))
        row = hbox(spacing=8)
        self.script_group = QButtonGroup(self)
        current = "".join(cfg["scripts"])
        self.script_btns: dict[str, QPushButton] = {}
        for key, glyph, name, native in SCRIPTS:
            b = QPushButton()
            b.setProperty("kind", "bigchoice")
            b.setCheckable(True)
            b.setChecked(key == current)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(86)
            bl = vbox(b, (4, 8, 4, 8), 0)
            g = label(glyph, jp_px=30)
            g.setAlignment(Qt.AlignmentFlag.AlignCenter)
            n = label(t(name), "h2")
            n.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bl.addWidget(g)
            bl.addWidget(n)
            if native:
                s = label(native, "faint")
                s.setStyleSheet(theme.jp_css(11, 400))
                s.setAlignment(Qt.AlignmentFlag.AlignCenter)
                bl.addWidget(s)
            for w in bl.parentWidget().findChildren(type(g)):
                w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.script_group.addButton(b)
            self.script_btns[key] = b
            b.clicked.connect(self._refresh_glyphs)
            row.addWidget(b)
        lay.addLayout(row)

        # grupos
        gh = hbox(spacing=6)
        gh.addWidget(section(t("kana.groups")))
        gh.addStretch()
        gh.addWidget(button(t("all"), "ghost", lambda: self.groups.set_all(True)))
        gh.addWidget(button(t("none"), "ghost", lambda: self.groups.set_all(False)))
        lay.addLayout(gh)
        self.groups = ChipGroup([(g, g) for g in kana_data.BASE_GROUPS],
                                [g for g in cfg["groups"] if g in kana_data.BASE_GROUPS], columns=5, jp=True)
        self.groups.changed.connect(self._update_count)
        lay.addWidget(self.groups)

        lay.addWidget(section(t("kana.extra")))
        self.extras = {}
        for g in kana_data.EXTRA_GROUPS:
            tg = Toggle(t(f"kana.{g}"), g in cfg["groups"])
            tg.toggled.connect(self._update_count)
            self.extras[g] = tg
            lay.addWidget(tg)

        # ejercicio
        lay.addWidget(section(t("kana.exercise")))
        self.exercise = Segmented([(e, t(f"ex.kana.{e}")) for e in ("choice", "write", "inverse")], cfg["exercise"])
        self.exercise.changed.connect(lambda _: self._update_difficulty())
        lay.addWidget(self.exercise)
        lay.addWidget(label(t("ex.kana.help"), "faint", wrap=True))

        lay.addWidget(section(t("difficulty")))
        self.difficulty = Segmented([(d, t(f"diff.{d}")) for d in ("easy", "normal", "hard")], cfg["difficulty"])
        lay.addWidget(self.difficulty)
        self.diff_help = label(t("diff.help"), "faint", wrap=True)
        lay.addWidget(self.diff_help)

        lay.addWidget(section(t("questions")))
        self.count = questions_selector(app.db.get("session_questions"))
        lay.addWidget(self.count)
        self.weak = Toggle(t("weak_only"), cfg.get("weak_only", False))
        lay.addWidget(self.weak)
        lay.addStretch()

        footer, self.start_btn, self.info = start_footer("", self.start)
        page(self, t("kana.title"), body, footer)
        self._refresh_glyphs()
        self._update_difficulty()

    def _scripts(self) -> list[str]:
        key = next(k for k, b in self.script_btns.items() if b.isChecked()) if any(
            b.isChecked() for b in self.script_btns.values()) else "h"
        return list(key)

    def _refresh_glyphs(self):
        scripts = self._scripts()
        for g, b in self.groups.buttons.items():
            first = kana_data.select(["h"], [g])[0]
            glyph = first.char if scripts != ["k"] else kana_data.to_katakana(first.char)
            if scripts == ["h", "k"]:
                glyph += kana_data.to_katakana(first.char)
            b.setText(f"{glyph}  {g}")
        self._update_count()

    def _update_difficulty(self):
        on = self.exercise.value() != "write"
        self.difficulty.setEnabled(on)
        self.diff_help.setVisible(on)

    def _groups(self) -> list[str]:
        return self.groups.selected() + [g for g, tg in self.extras.items() if tg.isChecked()]

    def _update_count(self):
        n = len(kana_data.select(self._scripts(), self._groups()))
        self.info.setText(t("chars_selected", n=n))
        self.start_btn.setEnabled(n > 0)

    def config(self) -> dict:
        return {"scripts": self._scripts(), "groups": self._groups(), "exercise": self.exercise.value() or "choice",
                "difficulty": self.difficulty.value() or "normal", "weak_only": self.weak.isChecked()}

    def start(self):
        if not self.start_btn.isEnabled():
            return
        cfg = self.config()
        n = int(self.count.value() or 15)
        self.app.db.set("kana_setup", cfg)
        self.app.db.set("session_questions", n)
        names = {"h": t("kana.hira"), "k": t("kana.kata"), "hk": t("kana.both")}
        self.app.start_module_session("kana", cfg, n, f"{t('module.kana')} · {names[''.join(cfg['scripts'])]}")
