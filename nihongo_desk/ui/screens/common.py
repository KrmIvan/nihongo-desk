"""Piezas compartidas por las pantallas de configuración de ejercicio."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QPushButton, QWidget

from ...core.i18n import t
from ..widgets import Segmented, button, hbox, label, scroll, vbox


def section(title: str) -> QWidget:
    return label(title, "section")


def page(owner: QWidget, title: str, body: QWidget, footer: QWidget | None = None, subtitle: str = "") -> None:
    """Cabecera (título) + contenido desplazable + pie fijo con la acción principal."""
    outer = vbox(owner, (0, 0, 0, 0), 0)
    head = hbox(margins=(16, 12, 16, 4), spacing=8)
    head.addWidget(label(title, "h1"))
    head.addStretch()
    if subtitle:
        head.addWidget(label(subtitle, "faint"))
    outer.addLayout(head)
    outer.addWidget(scroll(body), 1)
    if footer:
        bar = QFrame()
        bl = hbox(bar, (16, 10, 16, 14), 8)
        bl.addWidget(footer)
        outer.addWidget(bar)


def start_footer(info: str, on_start) -> tuple[QWidget, QPushButton, QWidget]:
    w = QWidget()
    lay = hbox(w, spacing=10)
    info_lb = label(info, "muted")
    lay.addWidget(info_lb, 1)
    b = button(t("start") + "  ⏎", "primary", on_start)
    b.setDefault(True)
    lay.addWidget(b)
    return w, b, info_lb


def questions_selector(value: int) -> Segmented:
    return Segmented([(str(n), str(n)) for n in (10, 15, 20, 30)], str(value if value in (10, 15, 20, 30) else 15))
