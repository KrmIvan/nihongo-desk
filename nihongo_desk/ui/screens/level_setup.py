"""Selección de nivel JLPT y tipo de ejercicio (kanji, vocabulario, gramática)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLineEdit, QListWidget, QListWidgetItem, QProgressBar,
                               QPushButton, QWidget)

from ...content.repository import meaning
from ...core.i18n import language, t
from ...exercises.engine import GRAMMAR_EXERCISES, KANJI_EXERCISES, VOCAB_EXERCISES
from ..widgets import ChipGroup, Toggle, button, hbox, label, vbox
from .common import page, questions_selector, section, start_footer

EXERCISES = {
    "kanji": KANJI_EXERCISES + ["mixed"],
    "vocab": VOCAB_EXERCISES + ["audio", "mixed"],
    "grammar": GRAMMAR_EXERCISES + ["mixed"],
}


class LevelButton(QPushButton):
    def __init__(self, level: int, count_text: str, pct: int | None, enabled: bool):
        super().__init__()
        self.level = level
        self.setProperty("kind", "level")
        self.setCheckable(True)
        self.setEnabled(enabled)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(66)
        lay = vbox(self, (12, 8, 12, 9), 3)
        top = hbox(spacing=6)
        name = label(f"N{level}", "h2")
        top.addWidget(name)
        top.addStretch()
        cnt = label(count_text, "faint")
        top.addWidget(cnt)
        lay.addLayout(top)
        bar = QProgressBar()
        bar.setTextVisible(False)
        bar.setRange(0, 100)
        bar.setValue(pct or 0)
        bar.setProperty("tone", "ok")
        lay.addWidget(bar)
        sub = label(t("level.progress", p=pct) if enabled else t("level.empty"), "faint")
        lay.addWidget(sub)
        for w in (name, cnt, bar, sub):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


class ItemPicker(QDialog):
    """Lista con búsqueda para elegir kanji o palabras concretas."""

    def __init__(self, parent, items: list[tuple[str, str]], picked: set[str]):
        super().__init__(parent)
        self.setWindowTitle(t("picker.title"))
        self.resize(360, 480)
        lay = vbox(self, (12, 12, 12, 12), 8)
        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText(t("picker.search"))
        self.search.textChanged.connect(self._filter)
        lay.addWidget(self.search)
        self.list = QListWidget()
        for key, text in items:
            it = QListWidgetItem(text)
            it.setData(Qt.ItemDataRole.UserRole, key)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if key in picked else Qt.CheckState.Unchecked)
            self.list.addItem(it)
        lay.addWidget(self.list, 1)
        row = hbox()
        row.addWidget(button(t("picker.clear"), "ghost", self._clear))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        row.addWidget(bb)
        lay.addLayout(row)

    def _filter(self, text: str):
        text = text.lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(text) and text not in it.text().lower())

    def _clear(self):
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.CheckState.Unchecked)

    def picked(self) -> list[str]:
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.CheckState.Checked]


class LevelSetupScreen(QWidget):
    def __init__(self, app, module: str):
        super().__init__()
        self.app, self.module = app, module
        self.cfg = app.db.get(f"{module}_setup")
        repo = app.repo
        counts = {"kanji": repo.kanji_count, "vocab": repo.vocab_count, "grammar": repo.grammar_count}[module]()
        progress = app.db.level_progress(module)

        body = QWidget()
        lay = vbox(body, (16, 6, 16, 12), 10)
        lay.addWidget(section(t("level.pick")))
        grid = hbox(spacing=8)
        self.level_btns: list[LevelButton] = []
        col_a, col_b = vbox(spacing=8), vbox(spacing=8)
        for i, lvl in enumerate((5, 4, 3, 2, 1)):
            total = counts.get(lvl, 0)
            learned = progress.get(lvl, {}).get("learned", 0)
            pct = round(100 * learned / total) if total else None
            b = LevelButton(lvl, t(f"level.items.{module}", n=total), pct, total > 0)
            b.setChecked(lvl in self.cfg["levels"] and total > 0)
            b.toggled.connect(self._changed)
            self.level_btns.append(b)
            (col_a if i % 2 == 0 else col_b).addWidget(b)
        col_b.addStretch()
        grid.addLayout(col_a, 1)
        grid.addLayout(col_b, 1)
        lay.addLayout(grid)
        lay.addWidget(label(t("grammar.notice" if module == "grammar" else "level.notice"), "faint", wrap=True))

        self.picked: list[str] = [str(x) for x in self.cfg.get("picked", [])]
        if module != "grammar":
            row = hbox()
            self.pick_btn = button(t("level.choose_items"), "chip", self._pick)
            row.addWidget(self.pick_btn)
            row.addStretch()
            lay.addLayout(row)

        lay.addWidget(section(t("kana.exercise")))
        self.exercises = ChipGroup([(e, t(f"ex.{module}.{e}")) for e in EXERCISES[module]], [self.cfg["exercise"]],
                                   multi=False, columns=2)
        if "audio" in self.exercises.buttons:
            self.exercises.buttons["audio"].setEnabled(False)
        lay.addWidget(self.exercises)

        lay.addWidget(section(t("questions")))
        self.count = questions_selector(app.db.get("session_questions"))
        lay.addWidget(self.count)
        self.weak = Toggle(t("weak_only"), self.cfg.get("weak_only", False))
        lay.addWidget(self.weak)
        lay.addStretch()

        footer, self.start_btn, self.info = start_footer("", self.start)
        page(self, t(f"level.title.{module}"), body, footer)
        self._changed()

    def _levels(self) -> list[int]:
        return [b.level for b in self.level_btns if b.isChecked()]

    def _changed(self):
        levels = self._levels()
        if self.module != "grammar":
            self.pick_btn.setText(t("level.picked", n=len(self.picked)) if self.picked else t("level.choose_items"))
            self.pick_btn.setChecked(bool(self.picked))
        if self.picked:
            self.info.setText(t("level.picked", n=len(self.picked)))
        else:
            self.info.setText(" + ".join(f"N{lv}" for lv in levels))
        self.start_btn.setEnabled(bool(levels) or bool(self.picked))

    def _pick(self):
        levels = self._levels() or [5]
        lang = language()
        if self.module == "kanji":
            items = [(k.char, f"{k.char}   N{k.jlpt}   {', '.join(meaning(k.meanings, lang)[0][:2])}")
                     for k in self.app.repo.kanji_by_levels(levels)]
        else:
            items = [(w.key, f"{w.word}【{w.reading}】  N{w.jlpt}   {(meaning(w.meanings, lang)[0] or [''])[0][:40]}")
                     for w in self.app.repo.words_by_levels(levels)]
        dlg = ItemPicker(self, items, set(self.picked))
        if dlg.exec():
            self.picked = dlg.picked()
            self._changed()

    def start(self):
        if not self.start_btn.isEnabled():
            return
        cfg = {"levels": self._levels() or [5], "exercise": (self.exercises.selected() or ["mixed"])[0],
               "weak_only": self.weak.isChecked()}
        if self.module != "grammar":
            cfg["picked"] = self.picked
        n = int(self.count.value() or 15)
        self.app.db.set(f"{self.module}_setup", cfg)
        self.app.db.set("session_questions", n)
        lv = " ".join(f"N{x}" for x in cfg["levels"]) if not self.picked else t("level.picked", n=len(self.picked))
        self.app.start_module_session(self.module, cfg, n, f"{t('module.' + self.module)} · {lv}")
