"""Personalización de la mascota: personaje, personalidad, expresiones, fondo,
tamaño, posición, ventana y reacciones. Todo se aplica al momento."""
from __future__ import annotations

from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QColor, QRegularExpressionValidator
from PySide6.QtWidgets import QColorDialog, QGridLayout, QLineEdit, QPushButton, QSlider, QSpinBox, QWidget

from ...core.i18n import language, t
from ...mascot.character import EXPRESSIONS
from ...mascot.config import PRESET_COLORS
from ...mascot.personality import PERSONALITY_IDS
from ..widgets import ChipGroup, Segmented, Toggle, button, card, hbox, label, vbox
from .common import page, section

CORNERS = ["top_left", "top_right", "bottom_left", "bottom_right"]


class MascotScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.mc = mc = app.mascot
        cfg = mc.cfg
        body = QWidget()
        lay = vbox(body, (16, 6, 16, 16), 10)

        def toggle(parent_lay, text: str, key: str):
            tg = Toggle(text, bool(cfg[key]))
            tg.toggled.connect(lambda v: (cfg.set(key, v), mc.apply()))
            parent_lay.addWidget(tg)
            return tg

        chars = mc.characters()
        if not chars:
            lay.addWidget(label(t("mascot.none"), "muted", wrap=True))
            page(self, t("mascot.title"), body)
            return

        # ---- modo
        mode = Segmented([(k, t(f"mascot.mode.{k}")) for k in ("floating", "integrated", "off")], cfg["mode"])
        mode.changed.connect(lambda v: (cfg.update(mode=v, visible=True), mc.apply()))
        lay.addWidget(label(t("mascot.mode")))
        lay.addWidget(mode)

        # ---- vista previa + expresiones
        pv = card()
        pl = vbox(pv, (12, 10, 12, 12), 8)
        self.preview = mc.make_preview(220)
        prow = hbox(spacing=0)
        prow.addStretch()
        prow.addWidget(self.preview)
        prow.addStretch()
        pl.addLayout(prow)
        pl.addWidget(label(t("mascot.preview"), "faint"))
        grid = QGridLayout()
        grid.setSpacing(6)
        avail = mc.char.available() if mc.char else []
        for i, e in enumerate([e for e in EXPRESSIONS if e in avail]):
            b = button(t(f"expr.{e}"), "chip", lambda _=False, e=e: mc.preview(e))
            grid.addWidget(b, i // 3, i % 3)
        pl.addLayout(grid)
        lay.addWidget(pv)

        # ---- personaje y personalidad
        lay.addWidget(section(t("mascot.character")))
        cc = card()
        cl = vbox(cc, (14, 12, 14, 12), 10)
        lang = language()
        who = Segmented([(cid, f"{c.name(lang)}  {c.names.get('ja', '')}") for cid, c in chars.items()],
                        mc.char.id if mc.char else None)
        who.changed.connect(self._set_character)
        cl.addWidget(who)
        cl.addWidget(label(t("mascot.personality")))
        pid = mc.pers.id
        pers = ChipGroup([(p, t(f"pers.{p}")) for p in PERSONALITY_IDS], [pid], multi=False, columns=2)
        pers.changed.connect(lambda: pers.selected() and mc.set_personality(pers.selected()[0]))
        cl.addWidget(pers)
        lay.addWidget(cc)

        # ---- apariencia
        lay.addWidget(section(t("mascot.appearance")))
        ap = card()
        al = vbox(ap, (14, 12, 14, 12), 10)
        al.addWidget(label(t("mascot.bg")))
        bg = Segmented([("transparent", t("mascot.bg.transparent")), ("solid", t("mascot.bg.solid"))], cfg["bg_mode"])
        bg.changed.connect(lambda v: (cfg.set("bg_mode", v), mc.apply()))
        al.addWidget(bg)
        self.bg = bg
        sw = QGridLayout()
        sw.setSpacing(6)
        for i, (name, hexv) in enumerate(PRESET_COLORS):
            b = QPushButton()
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(f"{t('color.' + name)} · {hexv}")
            b.setFixedHeight(26)
            b.setStyleSheet(f"QPushButton {{ background: {hexv}; border: 1px solid rgba(128,128,128,0.45);"
                            f" border-radius: 8px; }} QPushButton:hover {{ border: 2px solid {mc.char.accent}; }}")
            b.clicked.connect(lambda _=False, h=hexv: self._set_color(h))
            sw.addWidget(b, i // 4, i % 4)
        al.addLayout(sw)
        crow = hbox(spacing=8)
        self.hex = QLineEdit(cfg["bg_color"])
        self.hex.setValidator(QRegularExpressionValidator(QRegularExpression(r"#?[0-9A-Fa-f]{6}")))
        self.hex.setMaximumWidth(110)
        self.hex.editingFinished.connect(lambda: self._set_color(self.hex.text()))
        crow.addWidget(self.hex)
        crow.addWidget(button(t("mascot.bg.pick"), None, self._pick_color))
        crow.addStretch()
        al.addLayout(crow)
        al.addWidget(label(t("mascot.bg.help"), "faint", wrap=True))

        al.addWidget(label(t("mascot.size")))
        size = QSlider(Qt.Orientation.Horizontal)
        size.setRange(140, 520)
        size.setSingleStep(10)
        size.setValue(int(cfg["size"]))
        size.sliderReleased.connect(lambda: mc.set_size(size.value()))
        size.valueChanged.connect(lambda v: None if size.isSliderDown() else mc.set_size(v))
        al.addWidget(size)

        al.addWidget(label(t("mascot.position")))
        corner = ChipGroup([(c, t(f"corner.{c}")) for c in CORNERS],
                           [cfg["corner"]] if cfg["corner"] in CORNERS else [], multi=False, columns=2)
        corner.changed.connect(lambda: corner.selected() and (cfg.update(corner=corner.selected()[0], pos=None),
                                                              mc.apply()))
        al.addWidget(corner)
        al.addWidget(label(t("mascot.position.help"), "faint", wrap=True))
        lay.addWidget(ap)

        # ---- ventana flotante
        lay.addWidget(section(t("mascot.window")))
        wc = card()
        wl = vbox(wc, (14, 12, 14, 12), 10)
        toggle(wl, t("mascot.show"), "visible")
        toggle(wl, t("mascot.on_top"), "on_top")
        toggle(wl, t("mascot.follow_app"), "follow_app")
        toggle(wl, t("mascot.hide_in_game"), "hide_in_game")
        toggle(wl, t("mascot.click_through"), "click_through")
        lay.addWidget(wc)

        # ---- animación
        lay.addWidget(section(t("mascot.motion")))
        mo = card()
        ml = vbox(mo, (14, 12, 14, 12), 10)
        toggle(ml, t("mascot.animations"), "animations")
        toggle(ml, t("mascot.idle_moves"), "idle_moves")
        toggle(ml, t("mascot.blink"), "blink")
        lay.addWidget(mo)

        # ---- reacciones
        lay.addWidget(section(t("mascot.reactions")))
        rc = card()
        rl = vbox(rc, (14, 12, 14, 12), 10)
        for key in ("react_correct", "react_wrong", "celebrations", "greetings", "messages", "translation", "sleep"):
            toggle(rl, t(f"mascot.{key}"), key)
        srow = hbox(spacing=10)
        srow.addWidget(label(t("mascot.sleep_minutes"), wrap=True), 1)
        sp = QSpinBox()
        sp.setRange(1, 60)
        sp.setValue(int(cfg["sleep_minutes"]))
        sp.valueChanged.connect(lambda v: cfg.set("sleep_minutes", v))
        srow.addWidget(sp)
        rl.addLayout(srow)
        lay.addWidget(rc)

        lay.addWidget(button(t("mascot.reset"), None, self._reset))
        lay.addWidget(label(t("mascot.credits"), "faint", wrap=True))
        lay.addStretch()
        page(self, t("mascot.title"), body)

    # ------------------------------------------------------------------
    def _set_character(self, cid: str):
        self.mc.set_character(cid)
        self.app.open_module("mascot")   # reconstruye (expresiones disponibles, colores)

    def _set_color(self, value: str):
        value = value if value.startswith("#") else "#" + value
        if not QColor.isValidColorName(value):
            return
        self.hex.setText(value)
        self.mc.cfg.update(bg_color=value, bg_mode="solid")
        self.bg.buttons["solid"].setChecked(True)
        self.mc.apply()

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self.mc.cfg["bg_color"]), self, t("mascot.bg.pick"))
        if c.isValid():
            self._set_color(c.name())

    def _reset(self):
        self.mc.cfg.reset_appearance()
        self.mc.load_character()
        self.mc.apply()
        self.app.open_module("mascot")
        self.app.toast(t("mascot.reset.done"))
