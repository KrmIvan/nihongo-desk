"""Tema visual: paleta inspirada en colores tradicionales japoneses.

朱 shu (bermellón) como acento, 藍 ai (índigo) secundario, 抹茶 matcha para
aciertos y 和紙 washi como fondo del tema claro.
"""
from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase

PALETTES = {
    "dark": {
        "bg": "#14151b", "surface": "#1c1e26", "surface2": "#252833", "surface3": "#2e3240",
        "border": "#2f3340", "text": "#ecebe8", "muted": "#9497a6", "faint": "#61657a",
        "accent": "#e2574c", "accent_hover": "#ec6a5f", "accent_soft": "rgba(226,87,76,0.16)",
        "indigo": "#7b93ff", "indigo_soft": "rgba(123,147,255,0.15)",
        "ok": "#5fb37a", "ok_soft": "rgba(95,179,122,0.16)", "bad": "#e5665b", "bad_soft": "rgba(229,102,91,0.16)",
        "warn": "#e9a23b",
    },
    "light": {
        "bg": "#f6f3ee", "surface": "#ffffff", "surface2": "#efebe4", "surface3": "#e5dfd5",
        "border": "#e0d9ce", "text": "#24232b", "muted": "#706c78", "faint": "#a39e95",
        "accent": "#d4473c", "accent_hover": "#c23c32", "accent_soft": "rgba(212,71,60,0.11)",
        "indigo": "#3a5ba0", "indigo_soft": "rgba(58,91,160,0.10)",
        "ok": "#3f8f5a", "ok_soft": "rgba(63,143,90,0.13)", "bad": "#c9483e", "bad_soft": "rgba(201,72,62,0.11)",
        "warn": "#b9771b",
    },
}

UI_CANDIDATES = ["Segoe UI", "Inter", "Noto Sans", "Cantarell", "Ubuntu", "DejaVu Sans"]
JP_CANDIDATES = ["Yu Gothic UI", "Yu Gothic", "Meiryo", "Noto Sans CJK JP", "Noto Sans JP", "IPAexGothic",
                 "TakaoPGothic", "VL PGothic", "MS Gothic"]

_fonts: dict[str, str] = {}


def _first_available(cands: list[str]) -> str:
    fams = set(QFontDatabase.families())
    return next((c for c in cands if c in fams), "")


def fonts() -> dict[str, str]:
    if not _fonts:
        _fonts["ui"] = _first_available(UI_CANDIDATES)
        _fonts["jp"] = _first_available(JP_CANDIDATES) or _fonts["ui"]
    return _fonts


def app_font() -> QFont:
    f = QFont()
    fams = [x for x in (fonts()["ui"], fonts()["jp"]) if x]
    if fams:
        f.setFamilies(fams)
    f.setPointSizeF(10)
    return f


def jp_font(px: int, weight: QFont.Weight = QFont.Weight.Medium) -> QFont:
    f = QFont()
    f.setFamilies([fonts()["jp"], fonts()["ui"]])
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


def jp_css(px: int, weight: int = 500, extra: str = "") -> str:
    """Estilo para texto japonés grande (la hoja global anula setFont, por eso va por QSS)."""
    return f"font-family: '{fonts()['jp']}'; font-size: {px}px; font-weight: {weight}; {extra}"


def stylesheet(name: str) -> str:
    p = PALETTES[name]
    jp = fonts()["jp"]
    return f"""
* {{ outline: none; }}
QWidget {{ color: {p['text']}; font-size: 13px; }}
#Root {{ background: {p['bg']}; border: 1px solid {p['border']}; }}
QScrollArea, QScrollArea > QWidget > QWidget, QStackedWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ width: 8px; background: transparent; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['surface3']}; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}
QToolTip {{ background: {p['surface2']}; color: {p['text']}; border: 1px solid {p['border']}; padding: 4px 6px; border-radius: 6px; }}

/* ---------- barra de título ---------- */
#TitleBar {{ background: {p['bg']}; border-bottom: 1px solid {p['border']}; }}
#Logo {{ background: {p['accent']}; color: white; border-radius: 5px; font-family: '{jp}'; font-size: 14px; font-weight: 700; }}
#MascotStrip {{ background: {p['surface']}; border-bottom: 1px solid {p['border']}; }}
#AppName {{ font-weight: 600; font-size: 13px; color: {p['text']}; }}
QToolButton#TitleBtn {{ background: transparent; border: none; border-radius: 6px; color: {p['muted']};
    font-size: 13px; padding: 3px 7px; min-width: 18px; }}
QToolButton#TitleBtn:hover {{ background: {p['surface2']}; color: {p['text']}; }}
QToolButton#TitleBtn:checked {{ color: {p['accent']}; }}
QToolButton#LangBtn {{ background: {p['surface2']}; border: 1px solid {p['border']}; border-radius: 6px;
    color: {p['text']}; font-weight: 700; font-size: 11px; padding: 3px 8px; letter-spacing: 1px; }}
QToolButton#LangBtn:hover {{ border-color: {p['accent']}; color: {p['accent']}; }}

/* ---------- textos ---------- */
QLabel {{ background: transparent; }}
QLabel[role="h1"] {{ font-size: 20px; font-weight: 700; }}
QLabel[role="h2"] {{ font-size: 15px; font-weight: 600; }}
QLabel[role="section"] {{ font-size: 11px; font-weight: 700; color: {p['muted']}; letter-spacing: 1px; text-transform: uppercase; }}
QLabel[role="muted"] {{ color: {p['muted']}; }}
QLabel[role="faint"] {{ color: {p['faint']}; font-size: 11px; }}
QLabel[role="instruction"] {{ color: {p['muted']}; font-size: 13px; }}
QLabel[role="hint"] {{ color: {p['muted']}; font-size: 14px; }}
QLabel[role="furigana"] {{ color: {p['muted']}; font-family: '{jp}'; font-size: 15px; }}
QLabel[role="badge"] {{ background: {p['accent_soft']}; color: {p['accent']}; border-radius: 9px; padding: 2px 8px;
    font-size: 11px; font-weight: 700; }}
QLabel[role="demo"] {{ background: {p['indigo_soft']}; color: {p['indigo']}; border-radius: 9px; padding: 2px 8px;
    font-size: 10px; font-weight: 700; }}
QLabel[role="kpi"] {{ font-size: 22px; font-weight: 700; }}

/* ---------- tarjetas ---------- */
QFrame[card="true"] {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 14px; }}
QFrame[card="soft"] {{ background: {p['surface2']}; border: none; border-radius: 12px; }}
QPushButton#ModuleCard {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 14px; text-align: left; padding: 0; }}
QPushButton#ModuleCard:hover {{ border-color: {p['accent']}; background: {p['surface2']}; }}
QLabel#CardGlyph {{ font-family: '{jp}'; font-size: 26px; color: {p['accent']}; }}
QLabel#CardTitle {{ font-weight: 600; font-size: 14px; }}
QLabel#CardSub {{ color: {p['muted']}; font-size: 11px; }}
QPushButton#HeroCard {{ background: {p['accent']}; border: none; border-radius: 14px; text-align: left; }}
QPushButton#HeroCard:hover {{ background: {p['accent_hover']}; }}
QPushButton#HeroCard QLabel {{ color: white; }}
QPushButton#SubHero {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 14px; text-align: left; }}
QPushButton#SubHero:hover {{ border-color: {p['indigo']}; }}

/* ---------- botones ---------- */
QPushButton {{ background: {p['surface2']}; border: 1px solid {p['border']}; border-radius: 10px; padding: 8px 14px; }}
QPushButton:hover {{ border-color: {p['faint']}; }}
QPushButton:disabled {{ color: {p['faint']}; }}
QPushButton[kind="primary"] {{ background: {p['accent']}; border: none; color: white; font-weight: 600; padding: 10px 18px; }}
QPushButton[kind="primary"]:hover {{ background: {p['accent_hover']}; }}
QPushButton[kind="primary"]:disabled {{ background: {p['surface3']}; color: {p['faint']}; }}
QPushButton[kind="ghost"] {{ background: transparent; border: none; color: {p['muted']}; }}
QPushButton[kind="ghost"]:hover {{ color: {p['text']}; }}
QPushButton[kind="chip"] {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 9px; padding: 6px 10px; }}
QPushButton[kind="chip"]:hover {{ border-color: {p['faint']}; }}
QPushButton[kind="chip"]:checked {{ background: {p['accent_soft']}; border-color: {p['accent']}; color: {p['accent']}; font-weight: 600; }}
QPushButton[kind="seg"] {{ background: transparent; border: none; border-radius: 8px; padding: 7px 8px; color: {p['muted']}; }}
QPushButton[kind="seg"]:checked {{ background: {p['surface']}; color: {p['text']}; font-weight: 600; }}
QFrame#Segmented {{ background: {p['surface2']}; border-radius: 10px; }}
QPushButton[kind="bigchoice"] {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 14px; padding: 12px 6px; }}
QPushButton[kind="bigchoice"]:checked {{ border: 2px solid {p['accent']}; background: {p['accent_soft']}; }}
QPushButton[kind="level"] {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 12px; padding: 0; text-align: left; }}
QPushButton[kind="level"]:checked {{ border: 2px solid {p['accent']}; background: {p['accent_soft']}; }}
QPushButton[kind="level"]:disabled {{ background: {p['surface2']}; }}

/* ---------- respuestas ---------- */
QPushButton[kind="option"] {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 12px;
    padding: 12px 14px; text-align: left; font-size: 15px; }}
QPushButton[kind="option"]:hover {{ border-color: {p['indigo']}; background: {p['surface2']}; }}
QPushButton[kind="option"][jp="true"] {{ font-family: '{jp}'; font-size: 20px; }}
QPushButton[kind="option"][state="sel"] {{ border: 2px solid {p['indigo']}; background: {p['indigo_soft']}; }}
QPushButton[kind="option"][state="correct"] {{ border: 2px solid {p['ok']}; background: {p['ok_soft']}; color: {p['text']}; }}
QPushButton[kind="option"][state="wrong"] {{ border: 2px solid {p['bad']}; background: {p['bad_soft']}; }}
QPushButton[kind="option"][state="dim"] {{ color: {p['faint']}; }}
QPushButton[kind="token"] {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 10px;
    padding: 8px 12px; font-family: '{jp}'; font-size: 17px; }}
QPushButton[kind="token"]:hover {{ border-color: {p['indigo']}; }}
QPushButton[kind="token"][state="correct"] {{ border-color: {p['ok']}; background: {p['ok_soft']}; }}
QPushButton[kind="token"][state="wrong"] {{ border-color: {p['bad']}; background: {p['bad_soft']}; }}
QFrame#OrderSlot {{ background: {p['surface2']}; border: 1px dashed {p['faint']}; border-radius: 12px; }}
QLineEdit {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 12px; padding: 10px 12px;
    font-size: 18px; selection-background-color: {p['accent']}; }}
QLineEdit:focus {{ border: 2px solid {p['indigo']}; }}
QLineEdit[state="correct"] {{ border: 2px solid {p['ok']}; background: {p['ok_soft']}; }}
QLineEdit[state="wrong"] {{ border: 2px solid {p['bad']}; background: {p['bad_soft']}; }}
QLineEdit#Search {{ font-size: 13px; padding: 7px 10px; border-radius: 9px; }}
QLabel#OptKey {{ color: {p['faint']}; font-size: 11px; font-weight: 700; }}

QLabel#Toast {{ background: {p['surface3']}; color: {p['text']}; border: 1px solid {p['border']}; border-radius: 12px;
    padding: 12px 14px; font-size: 13px; }}
QFrame#PromptCard {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 18px; }}
QFrame#Feedback[ok="true"] {{ background: {p['ok_soft']}; border: 1px solid {p['ok']}; border-radius: 14px; }}
QFrame#Feedback[ok="false"] {{ background: {p['bad_soft']}; border: 1px solid {p['bad']}; border-radius: 14px; }}
QLabel#FbTitle[ok="true"] {{ color: {p['ok']}; font-weight: 700; font-size: 14px; }}
QLabel#FbTitle[ok="false"] {{ color: {p['bad']}; font-weight: 700; font-size: 14px; }}
QLabel#FbAnswer {{ font-family: '{jp}'; font-size: 17px; font-weight: 600; }}
QLabel#DetailKey {{ color: {p['muted']}; font-size: 11px; }}
QLabel#DetailVal {{ font-family: '{jp}'; font-size: 13px; }}

QProgressBar {{ background: {p['surface2']}; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
QProgressBar::chunk {{ background: {p['accent']}; border-radius: 3px; }}
QProgressBar[tone="indigo"]::chunk {{ background: {p['indigo']}; }}
QProgressBar[tone="ok"]::chunk {{ background: {p['ok']}; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 34px; height: 18px; border-radius: 9px; background: {p['surface3']}; }}
QCheckBox::indicator:checked {{ background: {p['accent']}; }}
QSpinBox, QComboBox, QKeySequenceEdit QLineEdit {{ background: {p['surface']}; border: 1px solid {p['border']};
    border-radius: 8px; padding: 5px 8px; font-size: 13px; }}
QComboBox QAbstractItemView {{ background: {p['surface']}; border: 1px solid {p['border']}; selection-background-color: {p['accent_soft']}; }}
QSlider::groove:horizontal {{ height: 4px; background: {p['surface3']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {p['accent']}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}
QListWidget {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: 10px; font-family: '{jp}'; }}
QListWidget::item {{ padding: 5px; }}
QDialog, QMessageBox {{ background: {p['bg']}; }}
"""


_current = ["dark"]


def set_current(name: str) -> None:
    _current[0] = name if name in PALETTES else "dark"


def current() -> str:
    return _current[0]


def palette(name: str | None = None) -> dict[str, str]:
    return PALETTES[name or _current[0]]
