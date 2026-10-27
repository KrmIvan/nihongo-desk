"""Progreso: racha, aciertos, tiempo, actividad semanal, niveles y puntos débiles."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QProgressBar, QWidget

from ...content import kana as kana_data
from ...core.i18n import language, t
from ..widgets import BarChart, button, card, hbox, label, vbox
from .common import page, section

DAY_ABBR = {"es": "LMXJVSD", "en": "MTWTFSS"}


class StatsScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        db, repo = app.db, app.repo
        body = QWidget()
        lay = vbox(body, (16, 6, 16, 16), 12)
        tot = db.totals()
        acc = round(100 * tot["correct"] / tot["answers"]) if tot["answers"] else 0

        # KPIs
        kpis = QGridLayout()
        kpis.setSpacing(8)
        tiles = [(t("stats.streak"), t("stats.days", n=db.streak())), (t("stats.accuracy"), f"{acc}%"),
                 (t("stats.time"), f"{tot['minutes']:.0f} min"), (t("stats.answers"), str(tot["answers"]))]
        for i, (name, value) in enumerate(tiles):
            c = card()
            cl = vbox(c, (12, 10, 12, 10), 2)
            cl.addWidget(label(name, "faint"))
            cl.addWidget(label(value, "kpi"))
            kpis.addWidget(c, i // 2, i % 2)
        lay.addLayout(kpis)

        # pendientes
        due = db.due_count(["kana", "kanji", "vocab", "grammar"])
        dc = card()
        dl = hbox(dc, (14, 10, 10, 10), 8)
        txt = vbox(spacing=2)
        txt.addWidget(label(t("stats.due"), "h2", wrap=True))
        txt.addWidget(label("  ·  ".join(f"{t('module.' + m)} {n}" for m, n in due.items()), "muted", wrap=True))
        dl.addLayout(txt, 1)
        rb = button(t("home.review_now"), "primary", app.start_review)
        rb.setEnabled(sum(due.values()) > 0)
        dl.addWidget(rb)
        lay.addWidget(dc)

        # semana
        lay.addWidget(section(t("stats.week")))
        days = db.daily_counts(7)
        abbr = DAY_ABBR[language()]
        chart = BarChart([(abbr[d.weekday()], n, ok) for d, n, ok in days])
        wc = card()
        vbox(wc, (12, 10, 12, 8)).addWidget(chart)
        lay.addWidget(wc)

        # progreso por módulo y nivel
        lay.addWidget(section(t("stats.by_level")))
        totals = {
            "kana": {0: len(kana_data.ALL_KANA)},
            "kanji": repo.kanji_count(),
            "vocab": repo.vocab_count(),
            "grammar": repo.grammar_count(),
        }
        pc = card()
        pl = QGridLayout(pc)
        pl.setContentsMargins(14, 12, 14, 12)
        pl.setHorizontalSpacing(10)
        pl.setVerticalSpacing(6)
        r = 0
        for module, levels in totals.items():
            prog = db.level_progress(module)
            pl.addWidget(label(t(f"module.{module}"), "h2"), r, 0, 1, 3)
            r += 1
            for lvl in sorted(levels, reverse=True):
                total = levels[lvl]
                if not total:
                    continue
                seen = prog.get(lvl, {}).get("seen", 0)
                learned = prog.get(lvl, {}).get("learned", 0)
                pl.addWidget(label("ア/あ" if module == "kana" else f"N{lvl}", "muted"), r, 0)
                bar = QProgressBar()
                bar.setTextVisible(False)
                bar.setRange(0, total)
                bar.setValue(learned)
                bar.setProperty("tone", "ok")
                pl.addWidget(bar, r, 1)
                pl.addWidget(label(t("stats.learned_of", l=learned, t=total, s=seen), "faint", wrap=True), r, 2)
                r += 1
        pl.setColumnStretch(1, 1)
        lay.addWidget(pc)

        # puntos débiles
        lay.addWidget(section(t("stats.weakest")))
        weak = db.weakest(limit=8)
        wk = card()
        wl = vbox(wk, (14, 10, 14, 10), 6)
        if not weak:
            wl.addWidget(label(t("stats.nothing"), "muted"))
        for row in weak:
            line = hbox(spacing=10)
            line.addWidget(label(self._display(app, row["module"], row["item_key"]), jp_px=18), 1)
            line.addWidget(label(t(f"module.{row['module']}"), "faint"))
            line.addWidget(label(f"{row['wrong']}✗ / {row['correct']}✓", "muted"))
            wl.addLayout(line)
        lay.addWidget(wk)
        lay.addStretch()
        page(self, t("stats.title"), body)

    @staticmethod
    def _display(app, module: str, key: str) -> str:
        if module == "kana":
            return key.split(":", 1)[1]
        if module == "vocab":
            w = app.repo.word(key)
            return f"{w.word}【{w.reading}】" if w else key
        if module == "grammar":
            g = app.repo.grammar_item(key)
            return g.sentence or "".join(g.tokens) if g else key
        return key
