"""
Cinematic in-app welcome screen — same vibe as the landing's 60s intro.

Plays scene-by-scene with kinetic typography (letters drop in by column with
3D flip), then fades out and reveals the login dialog.
"""
from __future__ import annotations

import math
import random
from PyQt6.QtCore import (
    QEasingCurve, QEvent, QPoint, QPointF, QPropertyAnimation, QRectF, QSize,
    Qt, QTimer, pyqtSignal, pyqtProperty,
)
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QFont, QLinearGradient, QPainter,
    QPainterPath, QPaintEvent, QPen, QRadialGradient, QTransform,
)
from PyQt6.QtWidgets import QFrame, QGraphicsOpacityEffect, QLabel, QPushButton, QWidget

from theme import COLORS, SANS_FAMILY, SERIF_FAMILY


# ----------------------------- letter widget ---------------------------------

class _Letter(QLabel):
    """Single letter that drops in from above with rotation + blur via opacity."""
    def __init__(self, ch: str, serif: bool, size: int, glow: bool, parent=None):
        super().__init__(ch, parent)
        f = QFont(SERIF_FAMILY if serif else SANS_FAMILY, size)
        f.setWeight(QFont.Weight.Black if serif else QFont.Weight.DemiBold)
        self.setFont(f)
        if glow:
            self.setStyleSheet(f"color: {COLORS['amber']}; background: transparent;")
        else:
            self.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._eff = QGraphicsOpacityEffect(self); self._eff.setOpacity(0.0)
        self.setGraphicsEffect(self._eff)
        self._y_offset = -80   # pixels (animated)

    def get_yoff(self) -> int: return self._y_offset
    def set_yoff(self, v: int):
        self._y_offset = v
        self.update()
        if self.parent(): self.parent().update()
    yoff = pyqtProperty(int, get_yoff, set_yoff)

    def get_opa(self) -> float: return self._eff.opacity()
    def set_opa(self, v: float): self._eff.setOpacity(max(0.0, min(1.0, v)))
    opa = pyqtProperty(float, get_opa, set_opa)


class _Line(QWidget):
    """Row of _Letter widgets laid out left-to-right with column-staggered drop animation."""
    finished = pyqtSignal()

    def __init__(self, text: str, *, serif=True, size=42, glow=False, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._letters: list[_Letter] = []
        self._gaps: list[int] = []          # x position of each letter relative to row
        self._anims: list[QPropertyAnimation] = []
        self.text = text
        self.serif = serif
        self.size_pt = size
        self.glow = glow
        self._build()

    def _build(self):
        # Build letter widgets and pre-compute layout
        x = 0
        for ch in self.text:
            if ch == " ":
                x += int(self.size_pt * 0.55)
                continue
            lab = _Letter(ch, self.serif, self.size_pt, self.glow, self)
            lab.adjustSize()
            self._letters.append(lab)
            self._gaps.append(x)
            x += lab.width() + 1
        self._total_w = x
        self._row_h = max((lab.height() for lab in self._letters), default=self.size_pt)
        self.setMinimumSize(self._total_w, self._row_h + 60)

    def sizeHint(self) -> QSize: return QSize(self._total_w, self._row_h + 60)

    def resizeEvent(self, e):
        # center letters horizontally in this widget
        base_x = max(0, (self.width() - self._total_w) // 2)
        base_y = 30
        for lab, gap in zip(self._letters, self._gaps):
            lab.move(base_x + gap, base_y + lab.yoff)

    def play(self):
        base_x = max(0, (self.width() - self._total_w) // 2)
        base_y = 30
        for i, (lab, gap) in enumerate(zip(self._letters, self._gaps)):
            lab.move(base_x + gap, base_y - 100)
            lab.set_yoff(-100)
            lab.set_opa(0.0)
            delay = int(60 + i * 38)
            # opacity in
            a_op = QPropertyAnimation(lab, b"opa", self)
            a_op.setDuration(560); a_op.setStartValue(0.0); a_op.setEndValue(1.0)
            a_op.setEasingCurve(QEasingCurve.Type.OutCubic)
            # y drop with slight overshoot
            a_y = QPropertyAnimation(lab, b"yoff", self)
            a_y.setDuration(720); a_y.setStartValue(-100); a_y.setKeyValueAt(0.7, 10); a_y.setEndValue(0)
            a_y.setEasingCurve(QEasingCurve.Type.OutBack)
            # reposition during animation
            def make_upd(lb=lab, g=gap):
                return lambda: lb.move(max(0,(self.width()-self._total_w)//2) + g, 30 + lb.yoff)
            a_y.valueChanged.connect(make_upd())
            QTimer.singleShot(delay, a_op.start)
            QTimer.singleShot(delay, a_y.start)
            self._anims.extend([a_op, a_y])
        total = 60 + len(self._letters) * 38 + 720
        QTimer.singleShot(total, self.finished.emit)

    def fade_out(self):
        for lab in self._letters:
            a = QPropertyAnimation(lab, b"opa", self)
            a.setDuration(420); a.setStartValue(lab.opa); a.setEndValue(0.0)
            a.setEasingCurve(QEasingCurve.Type.InCubic); a.start()
            self._anims.append(a)


# ----------------------------- big number ------------------------------------

class _BigNumber(QLabel):
    """Animated count-up from 0 to a target value, huge serif with glow."""
    def __init__(self, target: int, size_pt: int = 220, parent=None):
        super().__init__("0", parent)
        f = QFont(SERIF_FAMILY, size_pt); f.setWeight(QFont.Weight.Black)
        self.setFont(f)
        self.setStyleSheet(f"color: {COLORS['ember']}; background: transparent;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._eff = QGraphicsOpacityEffect(self); self._eff.setOpacity(0.0); self.setGraphicsEffect(self._eff)
        self.target = target
        self._val = 0
        self._anims = []

    def get_val(self) -> int: return self._val
    def set_val(self, v: int): self._val = int(v); self.setText(str(self._val))
    val = pyqtProperty(int, get_val, set_val)
    def get_opa(self) -> float: return self._eff.opacity()
    def set_opa(self, v: float): self._eff.setOpacity(v)
    opa = pyqtProperty(float, get_opa, set_opa)

    def play(self):
        a = QPropertyAnimation(self, b"opa", self)
        a.setDuration(520); a.setStartValue(0.0); a.setEndValue(1.0); a.setEasingCurve(QEasingCurve.Type.OutCubic); a.start()
        b = QPropertyAnimation(self, b"val", self)
        b.setDuration(1500); b.setStartValue(0); b.setEndValue(self.target); b.setEasingCurve(QEasingCurve.Type.OutCubic); b.start()
        self._anims.extend([a, b])

    def fade_out(self):
        a = QPropertyAnimation(self, b"opa", self); a.setDuration(380); a.setStartValue(self.opa); a.setEndValue(0.0); a.start(); self._anims.append(a)


# ----------------------------- flag flyby ------------------------------------

class _FlagFlyby(QWidget):
    """Russian tricolor flag that sweeps across the screen with a glow trail."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._x = -1.0
        self._wave = 0.0

    def get_x(self) -> float: return self._x
    def set_x(self, v: float): self._x = v; self.update()
    xrel = pyqtProperty(float, get_x, set_x)

    def play(self):
        a = QPropertyAnimation(self, b"xrel", self)
        a.setDuration(2600); a.setStartValue(-0.5); a.setEndValue(1.5); a.setEasingCurve(QEasingCurve.Type.InOutCubic); a.start()
        self._anim = a
        # subtle wave animation
        self._timer = QTimer(self); self._timer.timeout.connect(self._tick); self._timer.start(33)
    def _tick(self): self._wave += 0.18; self.update()

    def paintEvent(self, e: QPaintEvent):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W = self.width(); H = self.height()
        flag_w = int(W * 0.50); flag_h = int(flag_w * 0.55)
        cx = int(self._x * (W + flag_w)) - flag_w // 2
        cy = (H - flag_h) // 2

        # motion blur trail behind it
        for k in range(8, 0, -1):
            alpha = 14 * k
            ox = -k * 22
            self._draw_flag(p, cx + ox, cy, flag_w, flag_h, alpha=alpha)
        self._draw_flag(p, cx, cy, flag_w, flag_h, alpha=255)

    def _draw_flag(self, p: QPainter, x: int, y: int, w: int, h: int, alpha: int):
        # waving polygon: divide flag horizontally into strips, each with vertical sine offset
        bands = [
            (QColor(255, 255, 255, alpha), 0),
            (QColor(0, 57, 166, alpha),    1),
            (QColor(213, 43, 30,  alpha),   2),
        ]
        band_h = h / 3
        segs = 24
        for color, band in bands:
            path = QPainterPath()
            for i in range(segs + 1):
                t = i / segs
                px = x + t * w
                py_top = y + band * band_h + math.sin(self._wave + t * 4) * 6 * (0.4 + 0.6 * t)
                if i == 0: path.moveTo(px, py_top)
                else:      path.lineTo(px, py_top)
            for i in range(segs, -1, -1):
                t = i / segs
                px = x + t * w
                py_bot = y + (band + 1) * band_h + math.sin(self._wave + t * 4 + 0.4) * 6 * (0.4 + 0.6 * t)
                path.lineTo(px, py_bot)
            path.closeSubpath()
            p.fillPath(path, color)
        # glow outline
        glow = QPen(QColor(255, 180, 120, min(150, alpha))); glow.setWidth(2)
        # (skip stroke for trail copies to keep noise low)
        if alpha == 255:
            p.setPen(QPen(QColor(255, 220, 180, 120), 2))
            p.drawRect(x, y, w, h)


# ----------------------------- chip ------------------------------------------

class _Chip(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        f = QFont(SANS_FAMILY, 14); f.setWeight(QFont.Weight.DemiBold); self.setFont(f)
        self.setStyleSheet(
            f"color: {COLORS['amber']};"
            f"background: rgba(21,16,14,0.85);"
            f"border: 1px solid rgba(255,106,44,0.45);"
            f"border-radius: 18px;"
            f"padding: 10px 22px;"
        )
        self._eff = QGraphicsOpacityEffect(self); self._eff.setOpacity(0.0); self.setGraphicsEffect(self._eff)
        self._anims = []

    def get_opa(self) -> float: return self._eff.opacity()
    def set_opa(self, v: float): self._eff.setOpacity(v)
    opa = pyqtProperty(float, get_opa, set_opa)

    def play(self, delay: int):
        a = QPropertyAnimation(self, b"opa", self); a.setDuration(520); a.setStartValue(0.0); a.setEndValue(1.0); a.setEasingCurve(QEasingCurve.Type.OutBack)
        QTimer.singleShot(delay, a.start); self._anims.append(a)

    def fade_out(self):
        a = QPropertyAnimation(self, b"opa", self); a.setDuration(360); a.setStartValue(self.opa); a.setEndValue(0.0); a.start(); self._anims.append(a)


# ----------------------------- main welcome window ---------------------------

class Welcome(QWidget):
    """
    Full-screen-feel welcome. Emits `finished` when the user can move on.
    """
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PhantomTalk")
        self.resize(1280, 760)
        self.setMinimumSize(900, 560)
        self.setStyleSheet(f"background: {COLORS['bg']};")

        # ambient
        self._orb_pulse = 0.0
        self._ring_rot = 0.0
        self._flare_t = -1.0
        self._timer = QTimer(self); self._timer.timeout.connect(self._tick); self._timer.start(33)

        # skip button (top-right)
        self.skip = QPushButton("Пропустить ▸", self)
        self.skip.setProperty("ghost", True)
        self.skip.setStyleSheet(
            f"color: {COLORS['dim']}; background: rgba(10,6,5,0.5); border: 1px solid {COLORS['line']};"
            f"border-radius: 999px; padding: 7px 14px; font-size: 11pt;"
        )
        self.skip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip.clicked.connect(self._finish)
        self.skip.adjustSize()

        # progress bar (bottom)
        self.bar = QFrame(self); self.bar.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {COLORS['ember']}, stop:1 {COLORS['amber']});"
            "border-radius:1px;"
        )
        self.bar.setFixedHeight(3)
        self._bar_anim = QPropertyAnimation(self.bar, b"geometry", self)

        # active scene widgets, replaced each scene
        self._scene_widgets: list[QWidget] = []
        self._scene_idx = 0
        self._done = False

        # scenes definition (durations in ms; sum ~60s)
        self.scenes = [
            (8000,  self._scene_logo),         # 1 cold open
            (8500,  self._scene_problem),      # 2 the problem
            (8000,  self._scene_turn),         # 3 the turn
            (10000, self._scene_number),       # 4 510
            (8500,  self._scene_what),         # 5 what you get
            (7500,  self._scene_russia),       # 6 RU flag flyby
            (7500,  self._scene_tech),         # 7 tech chips
            (7000,  self._scene_finale),       # 8 finale
        ]
        self._total_ms = sum(d for d, _ in self.scenes)
        self._start_t = None
        QTimer.singleShot(150, self._run_next)

    # -------- ambient painter --------
    def _tick(self):
        self._orb_pulse = (self._orb_pulse + 0.04) % (math.pi * 2)
        self._ring_rot  = (self._ring_rot + 0.4) % 360
        if self._flare_t >= 0:
            self._flare_t = min(1.0, self._flare_t + 0.025)
            if self._flare_t >= 1.0: self._flare_t = -1.0
        self.update()

    def paintEvent(self, e: QPaintEvent):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height(); cx, cy = W/2, H/2

        # background gradient: black with red bottom glow
        g = QRadialGradient(QPointF(cx, H*1.0), max(W, H))
        g.setColorAt(0.0, QColor(214, 31, 18, 110))
        g.setColorAt(0.45, QColor(214, 31, 18, 30))
        g.setColorAt(1.0, QColor(10, 6, 5, 0))
        p.fillRect(self.rect(), QColor(COLORS["bg"]))
        p.fillRect(self.rect(), QBrush(g))

        # concentric conic rings, faint
        for k, (r, alpha, dir_) in enumerate([(180, 70, 1), (300, 45, -1), (440, 28, 1), (580, 18, -1)]):
            grad = QConicalGradient(QPointF(cx, cy), self._ring_rot * dir_)
            grad.setColorAt(0.0, QColor(255, 106, 44, 0))
            grad.setColorAt(0.35, QColor(255, 106, 44, alpha))
            grad.setColorAt(0.5, QColor(214, 31, 18, alpha // 2))
            grad.setColorAt(0.65, QColor(255, 154, 90, alpha))
            grad.setColorAt(1.0, QColor(255, 106, 44, 0))
            pen = QPen(QBrush(grad), 2)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r, r)

        # central orb
        pulse = 0.7 + 0.3 * (0.5 + 0.5 * math.sin(self._orb_pulse))
        orb_r = 34 + 8 * pulse
        og = QRadialGradient(QPointF(cx, cy * 0.42), orb_r * 6)
        og.setColorAt(0.0, QColor(255, 255, 255, 255))
        og.setColorAt(0.10, QColor(255, 217, 168, 220))
        og.setColorAt(0.25, QColor(255, 106, 44, 180))
        og.setColorAt(0.55, QColor(214, 31, 18, 80))
        og.setColorAt(1.0,  QColor(214, 31, 18, 0))
        p.setBrush(QBrush(og)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy * 0.42), orb_r * 6, orb_r * 6)
        # solid core
        p.setBrush(QColor(255, 220, 180)); p.drawEllipse(QPointF(cx, cy * 0.42), orb_r, orb_r)

        # lens-flare sweep on scene transitions
        if self._flare_t >= 0:
            t = self._flare_t
            x = -W * 0.4 + (W * 1.4) * t
            lg = QLinearGradient(QPointF(x, 0), QPointF(x + W * 0.25, 0))
            lg.setColorAt(0.0, QColor(255, 220, 180, 0))
            lg.setColorAt(0.5, QColor(255, 240, 214, 180))
            lg.setColorAt(1.0, QColor(255, 220, 180, 0))
            p.fillRect(QRectF(x, 0, W * 0.25, H), QBrush(lg))

    # -------- layout helpers --------
    def resizeEvent(self, e):
        self.skip.move(self.width() - self.skip.width() - 24, 22)
        self._layout_scene()
        self._layout_bar()

    def _layout_bar(self):
        progress_w = int(self.width() * (self._elapsed() / max(1, self._total_ms)))
        self.bar.setGeometry(0, self.height() - 3, progress_w, 3)

    def _elapsed(self) -> int:
        if self._start_t is None: return 0
        from time import monotonic
        return int((monotonic() - self._start_t) * 1000)

    def _layout_scene(self):
        # stack scene widgets vertically, centered
        if not self._scene_widgets: return
        total_h = sum(w.sizeHint().height() for w in self._scene_widgets) + (len(self._scene_widgets) - 1) * 16
        cy = self.height() // 2
        y = cy - total_h // 2
        for w in self._scene_widgets:
            sh = w.sizeHint(); w.setGeometry((self.width() - sh.width()) // 2 if sh.width() < self.width() else 0,
                                              y,
                                              sh.width() if sh.width() < self.width() else self.width(),
                                              sh.height())
            y += sh.height() + 16

    # -------- scene runner --------
    def _run_next(self):
        if self._done: return
        if self._scene_idx >= len(self.scenes):
            self._finish(); return
        if self._start_t is None:
            from time import monotonic
            self._start_t = monotonic()
            # progress bar driver
            self._bar_timer = QTimer(self); self._bar_timer.timeout.connect(self._layout_bar); self._bar_timer.start(40)
        # cleanup previous
        for w in self._scene_widgets:
            try:
                if hasattr(w, "fade_out"): w.fade_out()
            except Exception: pass
            QTimer.singleShot(420, w.deleteLater)
        self._scene_widgets = []
        # fire flare
        self._flare_t = 0.0
        # build new
        dur, builder = self.scenes[self._scene_idx]; self._scene_idx += 1
        QTimer.singleShot(220, lambda: self._launch_scene(builder, dur))

    def _launch_scene(self, builder, dur):
        builder()
        self._layout_scene()
        for w in self._scene_widgets:
            if hasattr(w, "play"): w.play()
        QTimer.singleShot(dur, self._run_next)

    def _add_line(self, text: str, *, serif=True, size=42, glow=False):
        line = _Line(text, serif=serif, size=size, glow=glow, parent=self)
        line.show()
        self._scene_widgets.append(line)
        return line

    # -------- scenes --------
    def _scene_logo(self):
        self._add_line("PhantomTalk", serif=True, size=72, glow=True)
        self._add_line("ГОЛОС · КОТОРЫЙ · СЛЫШНО", serif=False, size=14)

    def _scene_problem(self):
        self._add_line("Твой голос", serif=True, size=54)
        self._add_line("в Discord", serif=True, size=54)
        self._add_line("сжат до хрипа", serif=True, size=46, glow=False)
        self._add_line("64 кбит/с · моно", serif=False, size=14)

    def _scene_turn(self):
        self._add_line("Хватит.", serif=True, size=80)
        self._add_line("Слушай по-настоящему", serif=True, size=46, glow=True)

    def _scene_number(self):
        big = _BigNumber(510, size_pt=180, parent=self); big.show(); self._scene_widgets.append(big)
        self._add_line("кбит/с · stereo", serif=True, size=34, glow=True)
        self._add_line("× 5 К ГОЛОСУ DISCORD", serif=False, size=14)

    def _scene_what(self):
        self._add_line("Свои серверы", serif=True, size=52)
        self._add_line("Свои каналы", serif=True, size=52)
        self._add_line("Только твой звук", serif=True, size=48, glow=True)

    def _scene_russia(self):
        # flag is full-width
        flag = _FlagFlyby(self); flag.show()
        flag.setGeometry(0, 0, self.width(), self.height())
        flag.lower()  # behind any text we draw
        self._scene_widgets.append(flag)
        # text on top — actually want it on top, so add after and don't lower
        flag.raise_()  # keep behind orb but in front of bg ambient
        title = self._add_line("Работает в РФ", serif=True, size=64, glow=True)
        sub   = self._add_line("без VPN · без блокировок · твоя инфраструктура", serif=False, size=14)
        # bring text above flag
        title.raise_(); sub.raise_(); self.skip.raise_()

    def _scene_tech(self):
        # render chips as a row container
        row = QWidget(self); row.show()
        from PyQt6.QtWidgets import QHBoxLayout
        lay = QHBoxLayout(row); lay.setSpacing(14); lay.setContentsMargins(0, 0, 0, 0)
        chips = []
        for i, txt in enumerate(["Opus", "UDP-relay", "0 пересжатий", "self-hosted", "Demo-screen"]):
            ch = _Chip(txt, row); lay.addWidget(ch); chips.append(ch)
        row.adjustSize()
        row.sizeHint = lambda: row.size()
        # play wired through container
        class _Container(QWidget): pass
        row.play = lambda: [ch.play(120 + i * 180) for i, ch in enumerate(chips)]
        row.fade_out = lambda: [ch.fade_out() for ch in chips]
        self._scene_widgets.append(row)

    def _scene_finale(self):
        self._add_line("PhantomTalk", serif=True, size=84, glow=True)
        self._add_line("ГОЛОС · КОТОРЫЙ · СЛЫШНО", serif=False, size=14)

    # -------- end --------
    def _finish(self):
        if self._done: return
        self._done = True
        # fade everything out then emit
        for w in self._scene_widgets:
            try: w.fade_out() if hasattr(w, "fade_out") else None
            except Exception: pass
        eff = QGraphicsOpacityEffect(self); eff.setOpacity(1.0); self.setGraphicsEffect(eff)
        a = QPropertyAnimation(eff, b"opacity", self); a.setDuration(550); a.setStartValue(1.0); a.setEndValue(0.0); a.setEasingCurve(QEasingCurve.Type.InCubic)
        a.finished.connect(self._emit_finished); a.start()
        self._fade_anim = a

    def _emit_finished(self):
        try: self._timer.stop()
        except Exception: pass
        self.finished.emit()
        self.hide()
        self.deleteLater()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Space, Qt.Key.Key_Return):
            self._finish()
        else:
            super().keyPressEvent(e)

    def mousePressEvent(self, e):
        # click anywhere except buttons skips
        if e.button() == Qt.MouseButton.LeftButton:
            self._finish()
