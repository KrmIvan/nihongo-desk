"""Sesión de preguntas: pregunta → respuesta → corrección → siguiente.

Teclado: 1–6 eligen opción · Enter comprueba / pasa a la siguiente · Esc sale.
"""
from __future__ import annotations

import random
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QMessageBox, QProgressBar, QPushButton, QWidget

from ...content.romaji import kana_to_romaji
from ...core.i18n import t
from ...exercises.model import Question
from ...exercises.session import Session
from .. import theme
from ..widgets import (KanaLineEdit, button, clear_layout, fade_in, hbox, label, repolish, scroll, shake, vbox)


def _prompt_px(q: Question) -> int:
    n = len(q.prompt)
    if not q.prompt_jp:
        return 26 if n < 20 else 19
    if n <= 2:
        return 76
    if n <= 4:
        return 52
    if n <= 8:
        return 38
    return 22 if n <= 22 else 18


class MatchArea(QWidget):
    """Relacionar parejas: kanji (izquierda) ↔ significado (derecha)."""
    done = Signal(dict)  # clave -> acertado a la primera

    def __init__(self, pairs: list[tuple[str, str, str]]):
        super().__init__()
        self.pairs = {key: (left, right) for left, right, key in pairs}
        self.mistakes = {key: 0 for key in self.pairs}
        self.matched: set[str] = set()
        self.sel: str | None = None
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        keys = list(self.pairs)
        right = keys[:]
        random.shuffle(right)
        self.left_btns: dict[str, QPushButton] = {}
        self.right_btns: dict[str, QPushButton] = {}
        for i, key in enumerate(keys):
            lb = button(self.pairs[key][0], "option")
            lb.setProperty("jp", True)
            lb.setCheckable(True)
            lb.clicked.connect(lambda _=False, k=key: self._pick_left(k))
            self.left_btns[key] = lb
            grid.addWidget(lb, i, 0)
        for i, key in enumerate(right):
            rb = button(self.pairs[key][1], "option")
            rb.clicked.connect(lambda _=False, k=key: self._pick_right(k))
            self.right_btns[key] = rb
            grid.addWidget(rb, i, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 3)

    def _set(self, b: QPushButton, state: str):
        b.setProperty("state", state)
        repolish(b)

    def _pick_left(self, key: str):
        for k, b in self.left_btns.items():
            if k not in self.matched:
                b.setChecked(k == key)
                self._set(b, "")
        self.sel = key
        self._set(self.left_btns[key], "sel")

    def _pick_right(self, key: str):
        if self.sel is None or key in self.matched:
            return
        lb, rb = self.left_btns[self.sel], self.right_btns[key]
        if key == self.sel:
            self.matched.add(key)
            for b in (lb, rb):
                self._set(b, "correct")
                b.setEnabled(False)
            self.sel = None
            if len(self.matched) == len(self.pairs):
                self.done.emit({k: v == 0 for k, v in self.mistakes.items()})
        else:
            self.mistakes[self.sel] += 1
            for b in (lb, rb):
                self._set(b, "wrong")
            shake(rb)
            sel = self.sel
            QTimer.singleShot(450, lambda: [self._set(b, "") for b in (self.left_btns[sel], rb)
                                            if b.property("state") == "wrong"])


class OrderArea(QWidget):
    """Ordenar piezas: se pulsa una pieza para moverla a la frase y viceversa."""
    changed = Signal()

    def __init__(self, tokens: list[str]):
        super().__init__()
        self.bank = list(tokens)
        self.answer: list[str] = []
        lay = vbox(self, spacing=10)
        self.slot = QFrame()
        self.slot.setObjectName("OrderSlot")
        self.slot.setMinimumHeight(58)
        self.slot_lay = hbox(self.slot, (8, 8, 8, 8), 6)
        lay.addWidget(self.slot)
        self.bank_w = QWidget()
        self.bank_lay = hbox(self.bank_w, spacing=6)
        lay.addWidget(self.bank_w)
        self.locked = False
        self._render()

    def _render(self):
        clear_layout(self.slot_lay)
        clear_layout(self.bank_lay)
        for i, tok in enumerate(self.answer):
            b = button(tok, "token", lambda _=False, i=i: self._remove(i))
            b.setEnabled(not self.locked)
            self.slot_lay.addWidget(b)
        self.slot_lay.addStretch()
        for i, tok in enumerate(self.bank):
            b = button(tok, "token", lambda _=False, i=i: self._add(i))
            b.setEnabled(not self.locked)
            self.bank_lay.addWidget(b)
        self.bank_lay.addStretch()
        self.changed.emit()

    def _add(self, i: int):
        self.answer.append(self.bank.pop(i))
        self._render()

    def _remove(self, i: int):
        self.bank.append(self.answer.pop(i))
        self._render()

    def complete(self) -> bool:
        return not self.bank

    def mark(self, ok: bool):
        self.locked = True
        self._render()
        for i in range(self.slot_lay.count()):
            w = self.slot_lay.itemAt(i).widget()
            if w:
                w.setProperty("state", "correct" if ok else "wrong")
                repolish(w)


class SessionScreen(QWidget):
    def __init__(self, app, session: Session):
        super().__init__()
        self.app, self.session = app, session
        self.q: Question | None = None
        self.answered = False
        self.t0 = time.monotonic()
        self.option_btns: list[QPushButton] = []

        outer = vbox(self, (0, 0, 0, 0), 0)
        # cabecera: módulo · contador · tiempo · salir
        head = hbox(margins=(16, 10, 12, 4), spacing=8)
        head.addWidget(label(session.title, "muted"), 1)
        self.counter = label("", "faint")
        head.addWidget(self.counter)
        exit_btn = button("✕", "ghost", self.ask_exit)
        exit_btn.setToolTip(t("session.exit"))
        head.addWidget(exit_btn)
        outer.addLayout(head)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        pw = QWidget()
        hbox(pw, (16, 0, 16, 6)).addWidget(self.progress)
        outer.addWidget(pw)

        self.body = QWidget()
        self.body_lay = vbox(self.body, (16, 8, 16, 8), 12)
        self.scroll_area = scroll(self.body)
        outer.addWidget(self.scroll_area, 1)

        foot = QWidget()
        fl = hbox(foot, (16, 8, 16, 14), 8)
        self.skip_btn = button(t("skip"), "ghost", self.skip)
        fl.addWidget(self.skip_btn)
        fl.addStretch()
        self.main_btn = button(t("check"), "primary", self.main_action)
        fl.addWidget(self.main_btn)
        outer.addWidget(foot)

        self.clock = QTimer(self)
        self.clock.timeout.connect(self._tick)
        if session.time_limit:
            self.clock.start(1000)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.show_question()

    # ------------------------------------------------------------------
    def _tick(self):
        left = max(0, int((self.session.time_limit or 0) - self.session.seconds - (time.monotonic() - self.t0)))
        self.counter.setText(f"⏱ {left // 60}:{left % 60:02d} · {self.session.correct}✓")

    def _update_header(self):
        s = self.session
        if s.time_limit:
            used = s.seconds + (time.monotonic() - self.t0)
            self.progress.setRange(0, int(s.time_limit))
            self.progress.setValue(int(min(used, s.time_limit)))
            self._tick()
        else:
            self.progress.setRange(0, len(s.specs))
            self.progress.setValue(s.index)
            self.counter.setText(f"{min(s.index + 1, len(s.specs))}/{len(s.specs)}")

    def show_question(self):
        self.q = self.session.next_question(self.app.engine)
        if self.q is None:
            self.app.finish_session(self.session)
            return
        q = self.q
        self.answered = False
        self.t0 = time.monotonic()
        self.option_btns = []
        self.text_input = None
        self.match = None
        self.order = None
        clear_layout(self.body_lay)
        self._update_header()

        self.body_lay.addWidget(label(q.instruction, "instruction"))

        # tarjeta de la pregunta
        self.prompt_card = None
        if q.prompt:
            self.prompt_card = QFrame()
            self.prompt_card.setObjectName("PromptCard")
            pl = vbox(self.prompt_card, (16, 14, 16, 16), 4)
            fur = self.app.db.get("furigana")
            self.furigana = label(q.reading, "furigana")
            self.furigana.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.furigana.setVisible(bool(q.reading) and fur == "always" and not q.reading_is_answer)
            pl.addWidget(self.furigana)
            p = label(q.prompt, wrap=True)
            p.setAlignment(Qt.AlignmentFlag.AlignCenter)
            p.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            if q.prompt_jp:
                p.setStyleSheet(theme.jp_css(_prompt_px(q)))
            else:
                p.setStyleSheet(f"font-size: {_prompt_px(q)}px; font-weight: 600;")
            pl.addWidget(p)
            if q.hint:
                h = label(q.hint, "hint", wrap=True)
                h.setAlignment(Qt.AlignmentFlag.AlignCenter)
                pl.addWidget(h)
            self.prompt_card.setMinimumHeight(130 if len(q.prompt) <= 4 else 90)
            self.body_lay.addWidget(self.prompt_card)

        # zona de respuesta
        if q.kind == "choice":
            grid = QGridLayout()
            grid.setSpacing(8)
            cols = 2 if all(len(o) <= 10 for o in q.options) and len(q.options) >= 4 else 1
            for i, opt in enumerate(q.options):
                b = button(opt, "option", lambda _=False, i=i: self.choose(i))
                b.setProperty("jp", q.options_jp)
                b.setText(f"{opt}")
                b.setToolTip(str(i + 1))
                b.setMinimumHeight(48)
                self.option_btns.append(b)
                grid.addWidget(b, i // cols, i % cols)
            self.body_lay.addLayout(grid)
            self.main_btn.setVisible(False)
        elif q.kind == "text":
            self.text_input = KanaLineEdit(q.input_mode == "kana")
            self.text_input.setPlaceholderText(t("fb.ja_hint") if q.input_mode == "kana" else "romaji…")
            if q.input_mode == "kana":
                self.text_input.setStyleSheet(theme.jp_css(20, 500, "padding: 10px 12px;"))
            self.text_input.returnPressed.connect(self.main_action)
            self.body_lay.addWidget(self.text_input)
            self.main_btn.setVisible(True)
            QTimer.singleShot(0, self.text_input.setFocus)
        elif q.kind == "match":
            self.match = MatchArea(q.pairs)
            self.match.done.connect(self._match_done)
            self.body_lay.addWidget(self.match)
            self.main_btn.setVisible(False)
        elif q.kind == "order":
            if q.hint:
                h = label(q.hint, "h2", wrap=True)
                h.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.body_lay.addWidget(h)
            self.order = OrderArea(q.tokens)
            self.order.changed.connect(lambda: self.main_btn.setEnabled(self.order.complete()))
            self.body_lay.addWidget(self.order)
            self.main_btn.setVisible(True)
            self.main_btn.setEnabled(False)

        self.main_btn.setText(t("check") + "  ⏎")
        if q.kind != "order":
            self.main_btn.setEnabled(True)
        self.skip_btn.setVisible(q.kind != "match")
        self.feedback_holder = vbox(spacing=0)
        self.body_lay.addLayout(self.feedback_holder)
        self.body_lay.addStretch()
        fade_in(self.body, 160)
        if q.kind != "text":
            self.setFocus()

    # ------------------------------------------------------------------
    def choose(self, i: int):
        if self.answered or self.q is None or self.q.kind != "choice":
            return
        ok = self.q.check(i)
        for j, b in enumerate(self.option_btns):
            state = "correct" if j == self.q.answer_index else ("wrong" if j == i else "dim")
            b.setProperty("state", state)
            repolish(b)
        self.evaluate(ok)

    def main_action(self):
        if self.answered:
            self.show_question()
            return
        q = self.q
        if q is None:
            return
        if q.kind == "text":
            ans = self.text_input.answer().strip()
            if not ans:
                return
            ok = q.check(ans)
            self.text_input.setReadOnly(True)
            self.text_input.setProperty("state", "correct" if ok else "wrong")
            repolish(self.text_input)
            self.evaluate(ok)
        elif q.kind == "order" and self.order.complete():
            ok = q.check(self.order.answer)
            self.order.mark(ok)
            self.evaluate(ok)

    def skip(self):
        if self.answered or self.q is None:
            return
        if self.q.kind == "choice":
            for j, b in enumerate(self.option_btns):
                b.setProperty("state", "correct" if j == self.q.answer_index else "dim")
                repolish(b)
        elif self.text_input is not None:
            self.text_input.setReadOnly(True)
        elif self.order is not None:
            self.order.mark(False)
        self.evaluate(False)

    def _match_done(self, results: dict):
        ms = int((time.monotonic() - self.t0) * 1000 / max(1, len(results)))
        for key, ok in results.items():
            self.app.db.record("kanji", key, self.q.level, "match", ok, ms)
        mistakes = sum(self.match.mistakes.values())
        self.evaluate(mistakes == 0, recorded=True, title=t("fb.matched", n=mistakes))

    def evaluate(self, ok: bool, recorded: bool = False, title: str | None = None):
        q = self.q
        self.answered = True
        elapsed = time.monotonic() - self.t0
        if not recorded:
            self.session.record(self.app.engine, q, ok, int(elapsed * 1000))
        self.session.advance(q, ok, elapsed)
        self.app.save_session(self.session)
        self.app.play("ok" if ok else "bad")
        self.app.notify_mascot("answer", ok=ok)
        if not ok and self.prompt_card is not None:
            shake(self.prompt_card)
        if self.prompt_card is not None and q.reading and (self.app.db.get("furigana") != "never" or q.reading_is_answer):
            self.furigana.setVisible(True)
        self._show_feedback(ok, title)
        self.skip_btn.setVisible(False)
        self.main_btn.setVisible(True)
        self.main_btn.setEnabled(True)
        self.main_btn.setText(t("next") + "  ⏎")
        self.main_btn.setFocus()
        self._update_header()

    def _show_feedback(self, ok: bool, title: str | None):
        q = self.q
        fb = QFrame()
        fb.setObjectName("Feedback")
        fb.setProperty("ok", ok)
        lay = vbox(fb, (14, 12, 14, 12), 6)
        tl = label(title or (("✓  " + t("fb.correct")) if ok else ("✗  " + t("fb.wrong"))))
        tl.setObjectName("FbTitle")
        tl.setProperty("ok", ok)
        lay.addWidget(tl)
        if q.correct_display and q.kind != "match":
            ans = label(q.correct_display, wrap=True)
            ans.setObjectName("FbAnswer")
            lay.addWidget(ans)
        if q.explanation:
            lay.addWidget(label(q.explanation, wrap=True))
        details = list(q.details)
        if q.module == "vocab" and q.reading and self.app.db.get("romaji") == "after":
            details.insert(1, (t("detail.romaji"), kana_to_romaji(q.reading)))
        if details:
            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(4)
            for r, (k, v) in enumerate(details):
                kl = label(k)
                kl.setObjectName("DetailKey")
                vl = label(v, wrap=True)
                vl.setObjectName("DetailVal")
                vl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                grid.addWidget(kl, r, 0, Qt.AlignmentFlag.AlignTop)
                grid.addWidget(vl, r, 1)
            grid.setColumnStretch(1, 1)
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background: rgba(128,128,128,0.25);")
            lay.addWidget(sep)
            lay.addLayout(grid)
        self.feedback_holder.addWidget(fb)
        fade_in(fb, 220)
        QTimer.singleShot(30, lambda: self.scroll_area.ensureWidgetVisible(fb, 0, 8))

    # ------------------------------------------------------------------
    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Escape:
            self.ask_exit()
        elif Qt.Key.Key_1 <= k <= Qt.Key.Key_6 and self.option_btns and not self.answered:
            i = k - Qt.Key.Key_1
            if i < len(self.option_btns):
                self.choose(i)
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if self.answered or (self.q and self.q.kind == "order"):
                self.main_action()
        else:
            super().keyPressEvent(e)

    def ask_exit(self):
        if self.session.answered == 0:
            self.app.discard_session()
            self.app.go_home()
            return
        r = QMessageBox.question(self, t("session.exit"), t("session.exit.q"))
        if r == QMessageBox.StandardButton.Yes:
            self.app.go_home()

    def retranslate(self):
        """Al cambiar de idioma se reconstruye la pregunta actual si aún no se ha respondido."""
        if not self.answered:
            self.show_question()


class SummaryScreen(QWidget):
    def __init__(self, app, session: Session):
        super().__init__()
        self.app = app
        body = QWidget()
        lay = vbox(body, (20, 24, 20, 16), 12)
        n, c = session.answered, session.correct
        pct = round(100 * c / n) if n else 0
        title = label(t("summary.perfect") if n and c == n else t("summary.title"), "h1")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)
        big = label(f"{pct}%")
        big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        big.setStyleSheet(f"font-size: 56px; font-weight: 800; color: {theme.palette()['accent' if pct < 80 else 'ok']};")
        lay.addWidget(big)
        sub = label(t("summary.score", c=c, n=n) + "  ·  " +
                    t("summary.time", m=int(session.seconds // 60), s=int(session.seconds % 60)), "muted")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(sub)
        if session.missed:
            lay.addWidget(label(t("summary.missed"), "section"))
            box = QFrame()
            box.setProperty("card", "true")
            bl = vbox(box, (12, 10, 12, 10), 6)
            for prompt, answer in session.missed[:12]:
                row = hbox(spacing=10)
                p = label(prompt, jp_px=20)
                p.setMinimumWidth(48)
                row.addWidget(p)
                a = label(answer, "muted", wrap=True, jp_px=13)
                row.addWidget(a, 1)
                bl.addLayout(row)
            lay.addWidget(box)
        lay.addStretch()
        outer = vbox(self, spacing=0)
        outer.addWidget(scroll(body), 1)
        foot = QWidget()
        fl = hbox(foot, (16, 8, 16, 14), 8)
        fl.addWidget(button(t("summary.home"), None, app.go_home))
        fl.addStretch()
        again = button(t("summary.again") + "  ⏎", "primary", lambda: app.again(session))
        again.setDefault(True)
        fl.addWidget(again)
        outer.addWidget(foot)
        self.again_btn = again

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.again_btn.click()
        elif e.key() == Qt.Key.Key_Escape:
            self.app.go_home()
        else:
            super().keyPressEvent(e)
