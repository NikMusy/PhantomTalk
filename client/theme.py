"""PhantomTalk — ember theme + bundled Claude-style fonts."""
from __future__ import annotations
import os
import sys
from PyQt6.QtGui import QFontDatabase, QFont

# ---------------------------- palette ----------------------------------
COLORS = {
    "bg":        "#0a0605",
    "bg_soft":   "#120a08",
    "card":      "#15100e",
    "card_alt":  "#1b1310",
    "line":      "#2a1d18",
    "text":      "#f6ece6",
    "dim":       "#b69d92",
    "ember":     "#ff6a2c",
    "ember_2":   "#ff9a5a",
    "amber":     "#ffd9a8",
    "crimson":   "#d61f12",
    "crimson_d": "#7a0f0a",
}


def _font_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    meipass = getattr(sys, "_MEIPASS", None)
    for c in (os.path.join(here, "fonts"),
              os.path.join(meipass, "fonts") if meipass else None,
              os.path.join(meipass, "client", "fonts") if meipass else None):
        if c and os.path.isdir(c):
            return c
    return os.path.join(here, "fonts")


SERIF_FAMILY = "Playfair Display"
SANS_FAMILY  = "Inter"

def load_fonts() -> tuple[str, str]:
    """Register bundled TTFs. Returns the actual family names that QFontDatabase resolved."""
    global SERIF_FAMILY, SANS_FAMILY
    d = _font_dir()
    serif_fam = sans_fam = None
    for fn in os.listdir(d) if os.path.isdir(d) else []:
        path = os.path.join(d, fn)
        if not fn.lower().endswith(".ttf"):
            continue
        fid = QFontDatabase.addApplicationFont(path)
        if fid < 0:
            continue
        fams = QFontDatabase.applicationFontFamilies(fid)
        if not fams:
            continue
        fam = fams[0]
        if "playfair" in fam.lower():
            serif_fam = fam
        elif "inter" in fam.lower():
            sans_fam = fam
    if serif_fam: SERIF_FAMILY = serif_fam
    if sans_fam:  SANS_FAMILY  = sans_fam
    return SERIF_FAMILY, SANS_FAMILY


def serif(size: int = 22, weight: int = QFont.Weight.Bold) -> QFont:
    f = QFont(SERIF_FAMILY, size); f.setWeight(weight); return f

def sans(size: int = 10, weight: int = QFont.Weight.Normal) -> QFont:
    f = QFont(SANS_FAMILY, size); f.setWeight(weight); return f


# ---------------------------- stylesheet --------------------------------
def qss() -> str:
    c = COLORS
    return f"""
* {{ font-family: '{SANS_FAMILY}', 'Segoe UI', sans-serif; color: {c['text']}; }}

QMainWindow, QDialog, QWidget {{ background: {c['bg']}; }}

QLabel.h1 {{ font-family: '{SERIF_FAMILY}'; font-size: 30pt; font-weight: 800; color: {c['text']}; }}
QLabel.h2 {{ font-family: '{SERIF_FAMILY}'; font-size: 18pt; font-weight: 700; color: {c['text']}; }}
QLabel.dim {{ color: {c['dim']}; }}
QLabel.kbd {{ color: {c['amber']}; font-family: 'JetBrains Mono','Consolas',monospace; font-size: 11pt; }}

QTreeWidget, QListWidget, QTextEdit, QLineEdit, QComboBox, QPlainTextEdit {{
    background: {c['card']}; color: {c['text']};
    border: 1px solid {c['line']}; border-radius: 8px; padding: 6px;
    selection-background-color: {c['ember']}; selection-color: #1a0d08;
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {c['ember']};
}}
QTreeWidget::item, QListWidget::item {{ padding: 4px; border-radius: 4px; }}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background: rgba(255,106,44,0.15); color: {c['amber']};
}}
QTreeWidget::item:hover, QListWidget::item:hover {{ background: rgba(255,106,44,0.07); }}

QPushButton {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {c['crimson']}, stop:1 {c['ember']});
    color: white; border: none; padding: 9px 18px; border-radius: 9px; font-weight: 600;
}}
QPushButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {c['ember']}, stop:1 {c['amber']}); }}
QPushButton:disabled {{ background: #2a2118; color: #6a5b50; }}
QPushButton[ghost="true"] {{
    background: rgba(255,255,255,0.04); color: {c['text']}; border: 1px solid {c['line']};
}}
QPushButton[ghost="true"]:hover {{ background: rgba(255,106,44,0.10); border-color: rgba(255,106,44,0.45); color: {c['amber']}; }}
QPushButton[danger="true"] {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #6b0c08, stop:1 {c['crimson']});
}}
QPushButton[danger="true"]:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {c['crimson']}, stop:1 #ff4d3f);
}}
QPushButton:checked {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #6b0c08, stop:1 {c['crimson']}); }}

QProgressBar {{
    background: {c['card_alt']}; border: 1px solid {c['line']}; border-radius: 4px;
    text-align: center; height: 9px; color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #22c55e, stop:0.6 {c['ember']}, stop:1 {c['crimson']});
    border-radius: 4px;
}}

QSlider::groove:horizontal {{ height:6px; background: {c['card_alt']}; border:1px solid {c['line']}; border-radius:3px; }}
QSlider::handle:horizontal {{ background: {c['ember']}; width:16px; margin:-6px 0; border-radius:8px; }}
QSlider::handle:horizontal:hover {{ background: {c['amber']}; }}

QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: transparent; padding: 9px 14px; color: {c['dim']}; font-weight: 500; }}
QTabBar::tab:selected {{ color: {c['amber']}; border-bottom: 2px solid {c['ember']}; }}
QTabWidget::pane {{ border: 1px solid {c['line']}; border-radius: 10px; top:-1px; }}

QStatusBar {{ background: #07050304; color: {c['dim']}; border-top: 1px solid {c['line']}; }}
QHeaderView::section {{ background: transparent; color: {c['dim']}; border: none; padding: 4px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {c['line']}; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {c['ember']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

QToolTip {{
    background: {c['card']}; color: {c['text']}; border: 1px solid {c['line']};
    padding: 6px 10px; border-radius: 6px;
}}
"""
