"""Componentes reutilizables de la interfaz."""
from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRect, QSequentialAnimationGroup, QSize, Qt,
                            Signal)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QFrame, QGraphicsOpacityEffect, QGridLayout,
                               QHBoxLayout, QLabel, QLayout, QLineEdit, QPushButton, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from ..content import romaji
from . import theme


def label(text: str = "", role: str | None = None, wrap: bool = False, jp_px: int | None = None) -> QLabel:
    lb = QLabel(text)
    if role:
        lb.setProperty("role", role)
    if wrap:
        lb.setWordWrap(True)
    if jp_px:
        lb.setStyleSheet(theme.jp_css(jp_px))
    return lb


def button(text: str, kind: str | None = None, on_click=None) -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if kind:
        b.setProperty("kind", kind)
    if on_click:
        b.clicked.connect(on_click)
    return b


def card(kind: str = "true") -> QFrame:
    f = QFrame()
    f.setProperty("card", kind)
    return f


def repolish(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def vbox(parent: QWidget | None = None, margins=(0, 0, 0, 0), spacing: int = 8) -> QVBoxLayout:
    lay = QVBoxLayout(parent) if parent else QVBoxLayout()
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return lay


def hbox(parent: QWidget | None = None, margins=(0, 0, 0, 0), spacing: int = 8) -> QHBoxLayout:
    lay = QHBoxLayout(parent) if parent else QHBoxLayout()
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return lay


def scroll(content: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.Shape.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sa.setWidget(content)
    return sa


def clear_layout(lay: QLayout) -> None:
    while lay.count():
        item = lay.takeAt(0)
        if item.widget():
            w = item.widget()
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def fade_in(w: QWidget, ms: int = 220) -> None:
    eff = QGraphicsOpacityEffect(w)
    w.setGraphicsEffect(eff)
    anim = QPropertyAnimation(eff, b"opacity", w)
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.finished.connect(lambda: w.setGraphicsEffect(None))
    anim.start()


def shake(w: QWidget) -> None:
    start = w.pos()
    group = QSequentialAnimationGroup(w)
    for dx in (8, -7, 5, -3, 0):
        a = QPropertyAnimation(w, b"pos")
        a.setDuration(45)
        a.setEndValue(start + QPoint(dx, 0))
        group.addAnimation(a)
    group.start()


class Toggle(QAbstractButton):
    """Interruptor redondeado con texto a la derecha."""

    def __init__(self, text: str = "", checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setText(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        sp = self.sizePolicy()
        sp.setHeightForWidth(True)
        sp.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
        self.setSizePolicy(sp)

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        return QSize(44 + fm.horizontalAdvance(self.text()) + 4, max(22, fm.height() + 6))

    def minimumSizeHint(self) -> QSize:
        return QSize(100, 22)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        r = self.fontMetrics().boundingRect(QRect(0, 0, max(40, w - 48), 1000), Qt.TextFlag.TextWordWrap, self.text())
        return max(22, r.height() + 6)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme.palette()
        h = 18
        y = (self.height() - h) // 2
        track = QRect(0, y, 34, h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(pal["accent"] if self.isChecked() else pal["surface3"]))
        if not self.isEnabled():
            p.setOpacity(0.4)
        p.drawRoundedRect(track, h / 2, h / 2)
        p.setBrush(QColor("white"))
        knob_x = 34 - h + 2 if self.isChecked() else 2
        p.drawEllipse(QRect(knob_x, y + 2, h - 4, h - 4))
        p.setPen(QColor(pal["text"]))
        p.drawText(QRect(44, 0, self.width() - 44, self.height()),
                   int(Qt.AlignmentFlag.AlignVCenter) | int(Qt.TextFlag.TextWordWrap), self.text())


class Segmented(QFrame):
    """Selector segmentado (una opción)."""
    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], value: str | None = None):
        super().__init__()
        self.setObjectName("Segmented")
        lay = hbox(self, (3, 3, 3, 3), 2)
        self.group = QButtonGroup(self)
        self.buttons: dict[str, QPushButton] = {}
        for key, text in options:
            b = button(text, "seg")
            b.setCheckable(True)
            b.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            b.setMinimumWidth(40)
            self.group.addButton(b)
            self.buttons[key] = b
            lay.addWidget(b)
            b.clicked.connect(lambda _=False, k=key: self.changed.emit(k))
        if value in self.buttons:
            self.buttons[value].setChecked(True)

    def value(self) -> str | None:
        return next((k for k, b in self.buttons.items() if b.isChecked()), None)


class ChipGroup(QWidget):
    """Rejilla de chips seleccionables (uno o varios)."""
    changed = Signal()

    def __init__(self, options: list[tuple[str, str]], selected: list[str], multi: bool = True, columns: int = 3,
                 jp: bool = False):
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(6)
        self.group = QButtonGroup(self)
        self.group.setExclusive(not multi)
        self.buttons: dict[str, QPushButton] = {}
        for i, (key, text) in enumerate(options):
            b = button(text, "chip")
            b.setCheckable(True)
            b.setChecked(key in selected)
            b.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            b.setMinimumWidth(50)
            b.setToolTip(text)
            if jp:
                b.setStyleSheet(theme.jp_css(14, 400))
            self.group.addButton(b)
            self.buttons[key] = b
            self.grid.addWidget(b, i // columns, i % columns)
            b.toggled.connect(lambda _=False: self.changed.emit())

    def selected(self) -> list[str]:
        return [k for k, b in self.buttons.items() if b.isChecked()]

    def set_all(self, on: bool) -> None:
        for b in self.buttons.values():
            b.blockSignals(True)
            b.setChecked(on)
            b.blockSignals(False)
        self.changed.emit()


class KanaLineEdit(QLineEdit):
    """Campo de texto que convierte romaji → hiragana mientras se escribe.

    Mantiene el texto "en bruto" para que, p. ej., `kanna` produzca かんな.
    Si el usuario usa un IME japonés, el kana confirmado pasa tal cual.
    """

    def __init__(self, kana_mode: bool):
        super().__init__()
        self.kana_mode = kana_mode
        self.raw = ""

    def keyPressEvent(self, e):
        if not self.kana_mode or e.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            return super().keyPressEvent(e)
        if e.key() == Qt.Key.Key_Backspace:
            self.raw = self.raw[:-1]
        elif e.text() and e.text().isprintable() and e.key() not in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.raw += e.text()
        else:
            return super().keyPressEvent(e)
        self.setText(romaji.convert_live(self.raw))

    def inputMethodEvent(self, e):
        if self.kana_mode and e.commitString():
            self.raw += e.commitString()
            self.setText(romaji.convert_live(self.raw))
            e.accept()
            return
        super().inputMethodEvent(e)

    def answer(self) -> str:
        return self.raw if self.kana_mode else self.text()


class BarChart(QWidget):
    """Barras simples (últimos días): (etiqueta, total, aciertos)."""

    def __init__(self, data: list[tuple[str, int, int]]):
        super().__init__()
        self.data, self.pal = data, theme.palette()
        self.setMinimumHeight(120)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = len(self.data)
        if not n:
            return
        w, h = self.width(), self.height() - 20
        top = max(1, max(d[1] for d in self.data))
        slot = w / n
        bw = min(26, slot * 0.6)
        for i, (lab, total, ok) in enumerate(self.data):
            x = i * slot + (slot - bw) / 2
            th = (total / top) * (h - 16)
            oh = (ok / top) * (h - 16)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(self.pal["surface3"]))
            p.drawRoundedRect(int(x), int(h - th), int(bw), int(max(th, 3)), 4, 4)
            if ok:
                p.setBrush(QColor(self.pal["accent"]))
                p.drawRoundedRect(int(x), int(h - oh), int(bw), int(oh), 4, 4)
            p.setPen(QColor(self.pal["muted"]))
            f = p.font()
            f.setPixelSize(10)
            p.setFont(f)
            p.drawText(QRect(int(i * slot), h + 4, int(slot), 16), Qt.AlignmentFlag.AlignCenter, lab)
            if total:
                p.drawText(QRect(int(i * slot), int(h - th - 15), int(slot), 14), Qt.AlignmentFlag.AlignCenter,
                           str(total))


class FlowGrid(QWidget):
    """Rejilla que ajusta el número de columnas al ancho disponible."""

    def __init__(self, min_col_width: int = 150, spacing: int = 10):
        super().__init__()
        self.min_w = min_col_width
        self.items: list[QWidget] = []
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(spacing)
        self._cols = 0

    def add(self, w: QWidget) -> None:
        self.items.append(w)
        self._relayout(force=True)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._relayout()

    def _relayout(self, force: bool = False):
        cols = max(1, min(4, self.width() // self.min_w)) if self.width() > 0 else 2
        if cols == self._cols and not force:
            return
        self._cols = cols
        for w in self.items:
            self.grid.removeWidget(w)
        for i, w in enumerate(self.items):
            self.grid.addWidget(w, i // cols, i % cols)
        for c in range(4):
            self.grid.setColumnStretch(c, 1 if c < cols else 0)
