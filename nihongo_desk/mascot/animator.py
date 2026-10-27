"""Vista animada de la mascota: expresiones, parpadeo, flotación, reacciones,
efectos y bocadillo. Se usa en la ventana flotante (``framing="full"``) y
dentro del panel principal (``framing="bust"``, busto + bocadillo al lado).

Las ilustraciones nunca se deforman: solo se desplazan, se inclinan unos
grados alrededor de los pies o cambian de fotograma con un fundido corto.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..ui import theme
from .character import Character
from .personality import Personality, Reaction, get as get_personality

FPS = 30
FADE_S = 0.18
BLINK_S = 0.12
TALK_S = 0.15
CONFETTI = ["#f2668b", "#ffd166", "#06d6a0", "#4cc9f0", "#b388eb", "#ff9f1c"]


@dataclass
class Particle:
    kind: str
    x: float
    y: float
    vx: float
    vy: float
    born: float
    life: float
    size: float
    rot: float = 0.0
    vr: float = 0.0
    color: str = "#ffd166"
    text: str = ""


class MascotView(QWidget):
    def __init__(self, framing: str = "full", parent: QWidget | None = None):
        super().__init__(parent)
        self.framing = framing
        self.char: Character | None = None
        self.pers: Personality = get_personality("calm")
        self.char_h = 280
        self.bg_mode = "transparent"
        self.bg_color = QColor("#2b2f3a")
        self.flags = {"animations": True, "blink": True, "idle_moves": True}
        self.rng = random.Random()

        self.mood = "neutral"                 # expresión de fondo
        self.expr = "neutral"                 # expresión visible
        self.reaction: Reaction | None = None
        self.reaction_t0 = 0.0
        self.prev_pm: QPixmap | None = None
        self.fade_t0 = 0.0
        self.t0 = time.monotonic()
        self.next_blink = self.t0 + 2.0
        self.blink_until = 0.0
        self.double_blink = False
        self.particles: list[Particle] = []
        self.bubble: tuple[str, str] | None = None
        self.bubble_t0 = 0.0
        self.bubble_until = 0.0
        self.zz_next = 0.0
        self._press = None

        self.timer = QTimer(self)
        self.timer.setInterval(1000 // FPS)
        self.timer.timeout.connect(self.update)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._resize()

    # ================================================================ configuración
    def set_character(self, char: Character | None):
        if char is self.char:
            return
        self._snapshot()
        self.char = char
        self.particles.clear()
        self.bubble = None
        self._resize()
        self.update()

    def set_personality(self, pers: Personality):
        self.pers = pers

    def set_height(self, h: int):
        self.char_h = max(80, int(h))
        self._resize()
        self.update()

    def set_background(self, mode: str, color: str):
        self.bg_mode = mode
        self.bg_color = QColor(color)
        self.update()

    def set_flags(self, **flags):
        self.flags.update(flags)
        if not self.flags["animations"]:
            self.particles.clear()

    # ================================================================ geometría
    def char_size(self) -> QSize:
        if not self.char:
            return QSize(int(self.char_h * 0.45), self.char_h)
        pm = self.char.frame("neutral", height=self.char_h)
        return pm.size()

    def margins(self) -> tuple[int, int, int]:
        """(arriba, lados, abajo) que se reservan para bocadillo, efectos y saltos."""
        h = self.char_h
        return int(max(70, h * 0.30)), int(max(34, h * 0.20)), int(10 + h * 0.03)

    def _resize(self):
        if self.framing == "bust":
            self.setMinimumWidth(160)
            self.setFixedHeight(max(64, int(self.char_h)))
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            return
        cs = self.char_size()
        top, side, bottom = self.margins()
        self.setFixedSize(cs.width() + 2 * side, cs.height() + top + bottom)

    def sizeHint(self) -> QSize:
        return self.size()

    # ================================================================ estado
    def set_mood(self, expr: str):
        if expr != self.mood:
            self.mood = expr
            if self.reaction is None:
                self._set_expr(expr)

    def play(self, r: Reaction):
        self.reaction = r
        self.reaction_t0 = time.monotonic()
        self._set_expr(r.expr)
        if r.effect and self.flags["animations"]:
            self._spawn(r.effect)

    def preview(self, expr: str):
        motion = {"very_happy": "hop", "celebrating": "bounce", "surprised": "hop", "sad": "droop",
                  "thinking": "tilt", "confused": "tilt", "greeting": "hop", "encouraging": "hop",
                  "happy": "nod", "shy": "wiggle"}.get(expr, "none")
        effect = {"celebrating": "confetti", "very_happy": "sparkles", "confused": "question",
                  "surprised": "exclaim", "thinking": "dots", "shy": "hearts", "sleeping": "zz"}.get(expr, "")
        self.play(Reaction(expr, motion, effect, 2600))

    def say(self, ja: str, translation: str = "", ms: int = 3600):
        self.bubble = (ja, translation)
        self.bubble_t0 = time.monotonic()
        self.bubble_until = self.bubble_t0 + ms / 1000
        self.update()

    def _set_expr(self, expr: str):
        if expr != self.expr:
            self._snapshot()
            self.expr = expr

    def _snapshot(self):
        """Guarda el fotograma actual para el fundido hacia el siguiente."""
        if self.char and self.isVisible():
            self.prev_pm = self.char.frame(self.expr, height=self._frame_h())
            self.fade_t0 = time.monotonic()

    # ================================================================ tiempo
    def showEvent(self, e):
        super().showEvent(e)
        self.timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()   # oculta no consume CPU

    def _advance(self, now: float):
        r = self.reaction
        if r and now - self.reaction_t0 > r.ms / 1000:
            if r.then:
                self.play(r.then)
            else:
                self.reaction = None
                self._set_expr(self.mood)
        if self.bubble and now > self.bubble_until:
            self.bubble = None
        if self.flags["blink"] and now >= self.next_blink and self.expr != "sleeping":
            self.blink_until = now + BLINK_S
            lo, hi = self.pers.blink
            if not self.double_blink and self.rng.random() < 0.15:
                self.double_blink = True
                self.next_blink = now + BLINK_S + 0.16
            else:
                self.double_blink = False
                self.next_blink = now + self.rng.uniform(lo, hi)
        if self.expr == "sleeping" and self.flags["animations"] and now >= self.zz_next:
            self._spawn("zz")
            self.zz_next = now + 1.4
        self.particles = [p for p in self.particles if now - p.born < p.life]

    # ================================================================ movimiento
    def _motion(self, now: float) -> tuple[float, float, float]:
        """(dx, dy, ángulo) en px/grados; respeta «animaciones» y la energía de la personalidad."""
        if not self.flags["animations"]:
            return 0.0, 0.0, 0.0
        s = self.char_h / 280
        t = now - self.t0
        sleeping = self.expr == "sleeping"
        period = self.pers.float_period * (1.6 if sleeping else 1.0)
        dy = -self.pers.float_amp * s * (0.5 + 0.5 * math.sin(2 * math.pi * t / period))
        dx, ang = 0.0, 0.0
        if self.flags["idle_moves"] and self.reaction is None and not sleeping:
            ang += 0.6 * math.sin(2 * math.pi * t / (period * 2.7))      # vaivén muy sutil
        r = self.reaction
        if r:
            rt = now - self.reaction_t0
            dur = r.ms / 1000
            e = self.pers.energy * s
            env = min(1.0, rt / 0.25) * min(1.0, max(0.0, (dur - rt) / 0.3))  # entrada y salida suaves
            if r.motion == "hop" and rt < 0.42:
                dy -= 20 * e * math.sin(math.pi * rt / 0.42)
            elif r.motion == "bounce" and rt < 1.3:
                k = int(rt / 0.43)
                dy -= 22 * e * (0.75 ** k) * abs(math.sin(math.pi * rt / 0.43))
            elif r.motion == "nod" and rt < 0.8:
                dy += 4.5 * s * abs(math.sin(2 * math.pi * rt / 0.8))
            elif r.motion == "tilt":
                ang -= 4.0 * env
            elif r.motion == "droop":
                dy += 6 * s * env
                ang += 1.2 * env
            elif r.motion == "wiggle" and rt < 0.7:
                ang += 3.2 * math.sin(2 * math.pi * rt * 4.5) * (1 - rt / 0.7)
            elif r.motion == "sway":
                ang += 2.4 * math.sin(2 * math.pi * rt / 1.2) * env
        return dx, dy, ang

    # ================================================================ efectos
    def _spawn(self, kind: str):
        now = time.monotonic()
        rnd = self.rng.uniform
        add = self.particles.append
        if kind == "sparkles":
            for i in range(7):
                a = -math.pi * (0.1 + 0.8 * i / 6)
                add(Particle("star", 0.5 + 0.42 * math.cos(a), 0.16 + 0.22 * math.sin(a), 0, 0,
                             now + i * 0.06, rnd(0.7, 1.0), rnd(7, 12)))
        elif kind == "hearts":
            for i in range(4):
                add(Particle("heart", rnd(0.25, 0.75), rnd(0.05, 0.2), rnd(-0.02, 0.02), -0.12,
                             now + i * 0.18, 1.4, rnd(8, 12), color=self.rng.choice(["#ff6b8b", "#ff8fab"])))
        elif kind == "notes":
            for i in range(3):
                add(Particle("text", rnd(0.65, 0.95), rnd(0.05, 0.2), 0.05, -0.11, now + i * 0.22, 1.3,
                             rnd(14, 18), color="#8e7cc3", text=self.rng.choice("♪♫")))
        elif kind == "confetti":
            for _ in range(34):
                add(Particle("confetti", rnd(-0.1, 1.1), rnd(-0.35, -0.05), rnd(-0.05, 0.05), rnd(0.35, 0.6),
                             now + rnd(0, 0.5), 2.4, rnd(4, 7), rnd(0, 360), rnd(-300, 300),
                             self.rng.choice(CONFETTI)))
        elif kind in ("question", "exclaim"):
            add(Particle("pop", 0.86, 0.04, 0, 0, now, 1.2, 26, color="#f6a623" if kind == "exclaim" else "#5b8def",
                         text="!" if kind == "exclaim" else "?"))
        elif kind == "dots":
            add(Particle("think", 0.86, 0.02, 0, 0, now, 1.6, 14))
        elif kind == "zz":
            add(Particle("text", 0.7, 0.08, 0.06, -0.08, now, 2.2, 15, color="#7aa2d6", text="z"))

    def _draw_particles(self, p: QPainter, box: QRectF, now: float):
        for pt in self.particles:
            age = now - pt.born
            if age < 0:
                continue
            k = age / pt.life
            x = box.left() + (pt.x + pt.vx * age) * box.width()
            y = box.top() + (pt.y + pt.vy * age) * box.height()
            fade = min(1.0, (1 - k) * 3)
            sz = pt.size * (box.height() / 280 if self.framing == "full" else box.height() / 120)
            p.save()
            p.setOpacity(max(0.0, fade))
            p.translate(x, y)
            if pt.kind == "star":
                sc = math.sin(math.pi * min(1.0, k * 1.2))
                self._star(p, sz * sc, QColor("#ffd166"))
            elif pt.kind == "heart":
                self._heart(p, sz, QColor(pt.color))
            elif pt.kind == "confetti":
                p.rotate(pt.rot + pt.vr * age)
                p.fillRect(QRectF(-sz / 2, -sz / 4, sz, sz / 2), QColor(pt.color))
            elif pt.kind in ("text", "pop"):
                sc = 1.0 if pt.kind == "text" else min(1.0, 0.4 + age * 5)
                f = QFont(theme.jp_font(int(sz * sc), QFont.Weight.Bold))
                p.setFont(f)
                p.setPen(QPen(QColor(255, 255, 255, 220), 3))
                path = QPainterPath()
                path.addText(QPointF(-sz / 3, sz / 3), f, pt.text)
                p.strokePath(path, QPen(QColor(255, 255, 255, 230), 3))
                p.fillPath(path, QColor(pt.color))
            elif pt.kind == "think":
                p.setPen(QPen(QColor(120, 120, 140, 200), 1.2))
                p.setBrush(QColor(255, 255, 255, 235))
                p.drawEllipse(QRectF(-sz * 1.6, -sz * 0.8, sz * 3.2, sz * 1.6))
                p.drawEllipse(QRectF(-sz * 1.4, sz * 0.9, sz * 0.5, sz * 0.5))
                n = 1 + int(age / 0.3) % 3
                p.setBrush(QColor(110, 110, 130))
                p.setPen(Qt.PenStyle.NoPen)
                for i in range(n):
                    p.drawEllipse(QPointF(-sz * 0.8 + i * sz * 0.8, 0), sz * 0.16, sz * 0.16)
            p.restore()

    @staticmethod
    def _star(p: QPainter, r: float, color: QColor):
        if r <= 0.5:
            return
        path = QPainterPath()
        for j in range(8):
            a = math.pi / 4 * j - math.pi / 2
            rr = r if j % 2 == 0 else r * 0.3
            pt = QPointF(rr * math.cos(a), rr * math.sin(a))
            path.moveTo(pt) if j == 0 else path.lineTo(pt)
        path.closeSubpath()
        p.setPen(QPen(QColor(214, 150, 40), 1))
        p.setBrush(color)
        p.drawPath(path)

    @staticmethod
    def _heart(p: QPainter, s: float, color: QColor):
        path = QPainterPath()
        path.moveTo(0, s * 0.35)
        path.cubicTo(-s, -s * 0.3, -s * 0.45, -s, 0, -s * 0.45)
        path.cubicTo(s * 0.45, -s, s, -s * 0.3, 0, s * 0.35)
        p.setPen(QPen(QColor(255, 255, 255, 200), 1.2))
        p.setBrush(color)
        p.drawPath(path)

    # ================================================================ pintura
    def _frame_h(self) -> int:
        if self.framing == "bust" and self.char:
            return int((self.char_h - 8) / self.char.bust[3])
        return self.char_h

    def _current_pm(self, now: float) -> QPixmap:
        variant = ""
        if self.flags["blink"] and now < self.blink_until:
            variant = "blink"
        elif self.bubble and now - self.bubble_t0 < 1.5 and int((now - self.bubble_t0) / TALK_S) % 2 == 0:
            variant = "talk"
        return self.char.frame(self.expr, variant, self._frame_h())

    def paintEvent(self, _):
        now = time.monotonic()
        self._advance(now)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self.bg_mode == "solid":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self.bg_color)
            p.drawRoundedRect(QRectF(self.rect()), 16, 16)
        if not self.char:
            p.end()
            return
        if self.framing == "bust":
            self._paint_bust(p, now)
        else:
            self._paint_full(p, now)
        p.end()

    def _draw_char(self, p: QPainter, pm: QPixmap, target: QRectF, source: QRectF, now: float,
                   pivot: QPointF, ang: float):
        p.save()
        if ang:
            p.translate(pivot)
            p.rotate(ang)
            p.translate(-pivot)
        fade = min(1.0, (now - self.fade_t0) / FADE_S) if self.prev_pm is not None else 1.0
        if fade < 1.0 and self.prev_pm is not None:
            p.setOpacity(1 - fade)
            p.drawPixmap(target, self.prev_pm, source)
            p.setOpacity(fade)
        elif self.prev_pm is not None:
            self.prev_pm = None
        p.drawPixmap(target, pm, source)
        p.restore()

    def _paint_full(self, p: QPainter, now: float):
        pm = self._current_pm(now)
        top, side, bottom = self.margins()
        dx, dy, ang = self._motion(now)
        x = (self.width() - pm.width()) / 2 + dx
        y = self.height() - bottom - pm.height() + dy
        target = QRectF(x, y, pm.width(), pm.height())
        feet = QPointF(x + pm.width() / 2, y + pm.height())
        self._draw_char(p, pm, target, QRectF(pm.rect()), now, feet, ang)
        head = QRectF(x, y, pm.width(), pm.height() * 0.32)
        self._draw_particles(p, QRectF(x - side * 0.5, y, pm.width() + side, pm.height()), now)
        if self.bubble:
            self._bubble_full(p, head, now)

    def _paint_bust(self, p: QPainter, now: float):
        h = self.height() - 8
        pm = self._current_pm(now)
        src = self.char.bust_rect(pm)
        tw = src.width() * h / src.height()
        dx, dy, ang = self._motion(now)
        target = QRectF(8 + dx * 0.3, 4 + dy * 0.35, tw, h)
        pivot = QPointF(target.center().x(), target.bottom())
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(4, 2, tw + 8, h + 4), 14, 14)
        p.setClipPath(clip)
        if self.prev_pm is not None and self.prev_pm.height() != pm.height():
            self.prev_pm = None
        self._draw_char(p, pm, target, src, now, pivot, ang * 0.5)
        p.restore()
        self._draw_particles(p, QRectF(8, 4, tw, h * 1.6), now)
        if self.bubble:
            self._bubble_side(p, QRectF(tw + 20, 6, self.width() - tw - 28, h - 4), now)

    # ================================================================ bocadillo
    def _bubble_texts(self, scale: float):
        ja, tr = self.bubble
        f1 = QFont(theme.jp_font(int(15 * scale), QFont.Weight.Bold))
        f2 = QFont(theme.jp_font(max(9, int(11 * scale))))
        return ja, tr, f1, f2

    def _bubble_full(self, p: QPainter, head: QRectF, now: float):
        s = max(0.8, min(1.4, self.char_h / 280))
        ja, tr, f1, f2 = self._bubble_texts(s)
        m1, m2 = QFontMetricsF(f1), QFontMetricsF(f2)
        w = max(m1.horizontalAdvance(ja), m2.horizontalAdvance(tr) if tr else 0) + 24 * s
        w = min(w, self.width() - 12)
        h = m1.height() + (m2.height() + 2 if tr else 0) + 14 * s
        cx = head.center().x()
        rect = QRectF(max(6, min(self.width() - 6 - w, cx - w / 2)), max(4, head.top() - h - 4), w, h)
        pop = min(1.0, (now - self.bubble_t0) / 0.15)
        p.save()
        p.setOpacity(pop * min(1.0, (self.bubble_until - now) / 0.3))
        path = QPainterPath()
        path.addRoundedRect(rect, 12 * s, 12 * s)
        tail = QPainterPath()
        tx = min(max(cx, rect.left() + 18), rect.right() - 18)
        tail.moveTo(tx - 7 * s, rect.bottom() - 1)
        tail.lineTo(tx + 1, rect.bottom() + 9 * s)
        tail.lineTo(tx + 7 * s, rect.bottom() - 1)
        path = path.united(tail)
        p.setPen(QPen(QColor(0, 0, 0, 40), 1.2))
        p.setBrush(QColor(255, 255, 255, 245))
        p.drawPath(path)
        self._bubble_text(p, rect, ja, tr, f1, f2)
        p.restore()

    def _bubble_side(self, p: QPainter, area: QRectF, now: float):
        if area.width() < 60:
            return
        ja, tr, f1, f2 = self._bubble_texts(1.0)
        m1, m2 = QFontMetricsF(f1), QFontMetricsF(f2)
        w = min(area.width(), max(m1.horizontalAdvance(ja), m2.horizontalAdvance(tr) if tr else 0) + 24)
        h = m1.height() + (m2.height() + 2 if tr else 0) + 14
        rect = QRectF(area.left(), area.center().y() - h / 2, w, h)
        p.save()
        p.setOpacity(min(1.0, (now - self.bubble_t0) / 0.15) * min(1.0, (self.bubble_until - now) / 0.3))
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        tail = QPainterPath()
        tail.moveTo(rect.left() + 1, rect.center().y() - 6)
        tail.lineTo(rect.left() - 8, rect.center().y() + 2)
        tail.lineTo(rect.left() + 1, rect.center().y() + 6)
        p.setPen(QPen(QColor(0, 0, 0, 40), 1.2))
        p.setBrush(QColor(255, 255, 255, 245))
        p.drawPath(path.united(tail))
        self._bubble_text(p, rect, ja, tr, f1, f2)
        p.restore()

    @staticmethod
    def _bubble_text(p: QPainter, rect: QRectF, ja: str, tr: str, f1: QFont, f2: QFont):
        m1 = QFontMetricsF(f1)
        inner = rect.adjusted(10, 6, -10, -6)
        p.setPen(QColor("#2d2a32"))
        p.setFont(f1)
        p.drawText(QRectF(inner.left(), inner.top(), inner.width(), m1.height()),
                   Qt.AlignmentFlag.AlignCenter, m1.elidedText(ja, Qt.TextElideMode.ElideRight, inner.width()))
        if tr:
            p.setFont(f2)
            p.setPen(QColor("#6b6575"))
            m2 = QFontMetricsF(f2)
            p.drawText(QRectF(inner.left(), inner.top() + m1.height() + 2, inner.width(), m2.height()),
                       Qt.AlignmentFlag.AlignCenter, m2.elidedText(tr, Qt.TextElideMode.ElideRight, inner.width()))
