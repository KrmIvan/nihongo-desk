"""Pantalla principal: empezar rápido, continuar, repasar y acceso a los módulos."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QWidget

from ...core.i18n import t
from ..widgets import FlowGrid, hbox, label, scroll, vbox

MODULES = [
    ("kana", "あ"), ("kanji", "漢"), ("vocab", "語"), ("grammar", "文"),
    ("review", "復"), ("stats", "統"), ("mascot", "友"), ("settings", "設"),
]
REVIEWABLE = ("kana", "kanji", "vocab", "grammar")


class ModuleCard(QPushButton):
    def __init__(self, glyph: str, title: str, sub: str, badge: str = ""):
        super().__init__()
        self.setObjectName("ModuleCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(104)
        lay = vbox(self, (14, 12, 14, 12), 2)
        top = hbox(spacing=4)
        g = label(glyph)
        g.setObjectName("CardGlyph")
        top.addWidget(g)
        top.addStretch()
        if badge:
            top.addWidget(label(badge, "badge"), alignment=Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)
        lay.addStretch()
        tl = label(title)
        tl.setObjectName("CardTitle")
        sl = label(sub)
        sl.setObjectName("CardSub")
        lay.addWidget(tl)
        lay.addWidget(sl)
        for w in (g, tl, sl):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


class HomeScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        db = app.db
        modules = db.get("review_modules")
        due = db.due_count(list(REVIEWABLE))
        due_total = sum(n for m, n in due.items() if m in modules)
        tot = db.totals()

        body = QWidget()
        lay = vbox(body, (16, 14, 16, 16), 12)

        # saludo + racha
        head = hbox(spacing=6)
        greet = vbox(spacing=2)
        greet.addWidget(label(t("home.greeting"), "h2", wrap=True))
        greet.addWidget(label(t("home.today", n=tot["today_answers"], m=round(tot["today_minutes"])), "muted"))
        head.addLayout(greet, 1)
        streak = db.streak()
        if streak:
            head.addWidget(label(t("home.streak", n=streak), "badge"), alignment=Qt.AlignmentFlag.AlignTop)
        lay.addLayout(head)

        # acción principal: sesión rápida
        hero = QPushButton()
        hero.setObjectName("HeroCard")
        hero.setCursor(Qt.CursorShape.PointingHandCursor)
        hero.setMinimumHeight(78)
        hl = hbox(hero, (16, 12, 16, 12), 10)
        txt = vbox(spacing=2)
        a = label(t("home.quick", m=db.get("quick_minutes")), "h2")
        b = label(t("home.quick.sub"))
        txt.addWidget(a)
        txt.addWidget(b)
        hl.addLayout(txt, 1)
        arrow = label("▶")
        arrow.setStyleSheet("font-size: 18px;")
        hl.addWidget(arrow)
        for w in (a, b, arrow):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        hero.clicked.connect(app.start_quick)
        lay.addWidget(hero)

        # continuar / repasar
        row = hbox(spacing=10)
        last = db.get("last_session")
        if last and last["index"] < len(last["specs"]):
            row.addWidget(self._sub_hero(t("home.continue"), t("home.continue.sub", module=last["title"],
                                                                 done=last["index"], total=len(last["specs"])),
                                         app.continue_session))
        row.addWidget(self._sub_hero(t("home.review_now"), t("home.due", n=due_total), app.start_review))
        lay.addLayout(row)

        # módulos
        grid = FlowGrid(min_col_width=150)
        for key, glyph in MODULES:
            badge = ""
            if key in REVIEWABLE and due.get(key):
                badge = str(due[key])
            elif key == "review" and due_total:
                badge = str(due_total)
            c = ModuleCard(glyph, t(f"module.{key}"), t(f"module.{key}.sub"), badge)
            c.clicked.connect(lambda _=False, k=key: app.open_module(k))
            grid.add(c)
        lay.addWidget(grid)
        lay.addStretch()

        vbox(self).addWidget(scroll(body))

    def _sub_hero(self, title: str, sub: str, cb) -> QPushButton:
        b = QPushButton()
        b.setObjectName("SubHero")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setMinimumHeight(60)
        lay = vbox(b, (14, 10, 14, 10), 2)
        a, c = label(title, "h2"), label(sub, "muted")
        lay.addWidget(a)
        lay.addWidget(c)
        for w in (a, c):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        b.clicked.connect(cb)
        return b
