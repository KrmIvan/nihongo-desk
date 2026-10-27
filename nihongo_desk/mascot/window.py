"""Ventana flotante de la mascota: sin bordes, sin foco, arrastrable y opcionalmente
transparente o «atravesable» por los clics."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from ..ui.widgets import vbox
from .animator import MascotView

MARGIN = 12


class MascotWindow(QWidget):
    clicked = Signal()
    double_clicked = Signal()
    moved = Signal(QPoint)
    menu_requested = Signal(QPoint)
    resize_requested = Signal(int)      # +1 / -1

    def __init__(self, transparent: bool, on_top: bool, click_through: bool):
        super().__init__(None)
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                 | Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.NoDropShadowWindowHint)
        if on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if click_through:
            flags |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.setWindowTitle("Nihongo Desk · mascot")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, transparent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, transparent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.view = MascotView("full", self)
        self.view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        vbox(self).addWidget(self.view)
        self._press: QPoint | None = None
        self._origin = QPoint()
        self._dragging = False

    def sync_size(self):
        """Ajusta la ventana al tamaño de la vista manteniendo los pies en su sitio."""
        old = self.geometry()
        self.adjustSize()
        self.setFixedSize(self.view.size())
        if old.isValid() and self.isVisible():
            self.move(old.center().x() - self.width() // 2, old.bottom() - self.height() + 1)

    # ---- posición
    def place(self, corner: str, pos: list | None):
        scr = QGuiApplication.primaryScreen().availableGeometry()
        w, h = self.width(), self.height()
        if corner == "custom" and pos:
            rect = QRect(pos[0], pos[1], w, h)
            if any(s.availableGeometry().intersects(rect) for s in QGuiApplication.screens()):
                self.move(pos[0], pos[1])
                return
            corner = "bottom_right"
        x = scr.left() + MARGIN if "left" in corner else scr.right() - w - MARGIN
        y = scr.top() + MARGIN if "top" in corner else scr.bottom() - h - MARGIN + 1
        self.move(x, y)

    # ---- ratón: arrastrar, clic, menú, rueda
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press = e.globalPosition().toPoint()
            self._origin = self.pos()
            self._dragging = False
        elif e.button() == Qt.MouseButton.RightButton:
            self.menu_requested.emit(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self._press is None:
            return
        delta = e.globalPosition().toPoint() - self._press
        if not self._dragging and delta.manhattanLength() > 4:
            self._dragging = True
        if self._dragging:
            self.move(self._origin + delta)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or self._press is None:
            return
        if self._dragging:
            self.moved.emit(self.pos())
        else:
            self.clicked.emit()
        self._press = None
        self._dragging = False

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.resize_requested.emit(1 if e.angleDelta().y() > 0 else -1)
