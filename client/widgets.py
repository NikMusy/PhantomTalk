"""Reusable styled widgets for the PhantomTalk app (ember / Claude-style)."""
from __future__ import annotations

import hashlib
from PyQt6.QtCore import Qt, QSize, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPixmap, QRadialGradient,
)
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from theme import COLORS, SANS_FAMILY, SERIF_FAMILY


# ----------------------------- avatar / icons --------------------------------

def warm_color(name: str) -> QColor:
    h = int(hashlib.md5((name or "?").encode("utf-8")).hexdigest(), 16)
    hue = (h % 60 + 350) % 360                 # 350..49 → warm reds/oranges/ambers
    sat = 110 + (h >> 8) % 90
    return QColor.fromHsl(hue, min(220, sat), 135)


def avatar_pixmap(name: str, size: int = 36) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    col = warm_color(name)
    g = QLinearGradient(0, 0, 0, size)
    g.setColorAt(0.0, col.lighter(135))
    g.setColorAt(1.0, col.darker(125))
    p.setBrush(QBrush(g))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(0, 0, size - 1, size - 1)
    initials = (name.strip()[:1] if name.strip() else "?").upper()
    f = QFont(SERIF_FAMILY, max(8, int(size * 0.40)))
    f.setWeight(QFont.Weight.Black)
    p.setFont(f)
    p.setPen(QColor("#1a0d08"))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, initials)
    p.end()
    return pm


def orb_pixmap(size: int = 18) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    g = QRadialGradient(size * 0.5, size * 0.42, size * 0.55)
    g.setColorAt(0.0, QColor("#ffffff"))
    g.setColorAt(0.25, QColor(COLORS["amber"]))
    g.setColorAt(0.6, QColor(COLORS["ember"]))
    g.setColorAt(1.0, QColor(COLORS["crimson"]))
    p.setBrush(QBrush(g))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(0, 0, size - 1, size - 1)
    p.end()
    return pm


# ----------------------------- member / dm rows ------------------------------

class MemberRow(QWidget):
    def __init__(self, nick: str, status: str = "", muted=False, deafened=False, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(10)
        av = QLabel()
        av.setPixmap(avatar_pixmap(nick, 34))
        av.setFixedSize(34, 34)
        col = QVBoxLayout()
        col.setSpacing(0)
        name = QLabel(nick)
        name.setObjectName("userNick")
        sub = QLabel(status or "в сети")
        sub.setObjectName("userStatus")
        col.addWidget(name)
        col.addWidget(sub)
        lay.addWidget(av)
        lay.addLayout(col, 1)
        badge = ""
        if muted:
            badge += "🔇 "
        if deafened:
            badge += "🚫"
        if badge:
            b = QLabel(badge.strip())
            b.setStyleSheet(f"color: {COLORS['dim']};")
            lay.addWidget(b)


# ----------------------------- window chrome ---------------------------------

class WinButton(QPushButton):
    def __init__(self, glyph: str, object_name: str = "winBtn", parent=None):
        super().__init__(glyph, parent)
        self.setObjectName(object_name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


class TitleBar(QWidget):
    """Frameless-window title bar: drag to move (native), min/max/close."""
    def __init__(self, win: QWidget, parent=None):
        super().__init__(parent)
        self._win = win
        self.setObjectName("TitleBar")
        self.setFixedHeight(40)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 8, 0)
        lay.setSpacing(8)

        dot = QLabel()
        dot.setPixmap(orb_pixmap(18))
        dot.setFixedSize(18, 18)
        wm = QLabel("PhantomTalk")
        wm.setObjectName("wordmark")
        lay.addWidget(dot)
        lay.addWidget(wm)
        lay.addStretch()

        self.min_b = WinButton("—")
        self.max_b = WinButton("□")
        self.close_b = WinButton("✕", "winBtn")
        self.close_b.setObjectName("winClose")
        for b in (self.min_b, self.max_b, self.close_b):
            lay.addWidget(b)
        self.min_b.clicked.connect(self._win.showMinimized)
        self.max_b.clicked.connect(self._toggle_max)
        self.close_b.clicked.connect(self._win.close)

    def _toggle_max(self):
        if self._win.isMaximized():
            self._win.showNormal()
        else:
            self._win.showMaximized()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            h = self._win.windowHandle()
            if h is not None:
                h.startSystemMove()

    def mouseDoubleClickEvent(self, e):
        self._toggle_max()


class ServerPill(QPushButton):
    def __init__(self, text: str, object_name: str = "serverPill", parent=None):
        super().__init__(text, parent)
        self.setObjectName(object_name)
        self.setCheckable(True)
        self.setFixedSize(52, 52)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


class IconButton(QPushButton):
    def __init__(self, glyph: str, tip: str = "", checkable=False, parent=None):
        super().__init__(glyph, parent)
        self.setObjectName("iconBtn")
        self.setCheckable(checkable)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if tip:
            self.setToolTip(tip)
