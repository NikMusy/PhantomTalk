"""
PhantomTalk — cinematic animated installer.

A self-contained PyQt6 setup wizard in the ember / Claude aesthetic:
  * animated backdrop (glowing orb, rotating rings, rising ember sparks)
  * kinetic title, glowing progress bar, animated finish checkmark
  * REAL install: copies the bundled PhantomTalk.exe to a per-user location,
    creates Start-Menu / Desktop / Startup shortcuts, registers an entry in
    "Apps & features" with a working uninstaller.

Build into PhantomTalkSetup.exe with build_installer.py (it bundles
dist/PhantomTalk.exe, the icon and the fonts).

Modes:
  (no args)               → GUI install wizard
  --uninstall <dir>       → GUI uninstall (used by the registered UninstallString)
  --silent --dir <path>   → headless install (testing/CI)
"""
from __future__ import annotations

import math
import os
import random
import shutil
import subprocess
import sys
import winreg

APP_NAME = "PhantomTalk"
APP_VERSION = "0.4.0"
PUBLISHER = "PhantomTalk"
EXE_NAME = "PhantomTalk.exe"
UNINST_NAME = "PhantomTalk-uninstall.exe"
CREATE_NO_WINDOW = 0x08000000

# ----------------------------- palette ---------------------------------------
C = {
    "bg": "#0a0605", "card": "#15100e", "line": "#2a1d18",
    "text": "#f6ece6", "dim": "#b69d92",
    "ember": "#ff6a2c", "ember2": "#ff9a5a", "amber": "#ffd9a8",
    "crimson": "#d61f12",
}


# ----------------------------- resource resolution ---------------------------
def res_path(name: str) -> str:
    bases = []
    mp = getattr(sys, "_MEIPASS", None)
    if mp:
        bases += [mp, os.path.join(mp, "dist"), os.path.join(mp, "fonts")]
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    bases += [here, root, os.path.join(root, "dist"), os.path.join(root, "client"),
              os.path.join(root, "client", "fonts")]
    for b in bases:
        p = os.path.join(b, name)
        if os.path.exists(p):
            return p
    return os.path.join(mp or here, name)


def default_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Programs", APP_NAME)


# ============================================================================
# CORE INSTALL LOGIC (no Qt — usable headless)
# ============================================================================
def copy_with_progress(src, dst, cb=None):
    total = os.path.getsize(src)
    done = 0
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        while True:
            chunk = fi.read(1024 * 1024)
            if not chunk:
                break
            fo.write(chunk)
            done += len(chunk)
            if cb and total:
                cb(done / total)
    shutil.copymode(src, dst)


def make_shortcut(lnk_path, target, icon, workdir, args=""):
    ps = (
        "$ws=New-Object -ComObject WScript.Shell;"
        f"$s=$ws.CreateShortcut('{lnk_path}');"
        f"$s.TargetPath='{target}';"
        f"$s.Arguments='{args}';"
        f"$s.WorkingDirectory='{workdir}';"
        f"$s.IconLocation='{icon}';"
        "$s.Description='PhantomTalk — голос, который слышно';"
        "$s.Save()"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       creationflags=CREATE_NO_WINDOW, timeout=20)
    except Exception:
        pass


def _start_menu_dir():
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs")


def _desktop_dir():
    return os.path.join(os.path.expanduser("~"), "Desktop")


def _startup_dir():
    return os.path.join(os.environ.get("APPDATA", ""),
                        "Microsoft", "Windows", "Start Menu", "Programs", "Startup")


def register_uninstall(install_dir, uninst_exe, icon, size_kb):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\PhantomTalk"
    k = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
    def S(name, val): winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
    def D(name, val): winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, val)
    S("DisplayName", APP_NAME)
    S("DisplayVersion", APP_VERSION)
    S("Publisher", PUBLISHER)
    S("DisplayIcon", icon)
    S("InstallLocation", install_dir)
    S("UninstallString", f'"{uninst_exe}" --uninstall "{install_dir}"')
    S("QuietUninstallString", f'"{uninst_exe}" --uninstall "{install_dir}" --silent')
    S("URLInfoAbout", "https://github.com/NikMusy/PhantomTalk")
    D("NoModify", 1)
    D("NoRepair", 1)
    D("EstimatedSize", int(size_kb))
    winreg.CloseKey(k)


def do_install(target, opts, progress=None):
    """opts: dict(desktop, startmenu, startup). progress(pct:int, text:str)."""
    def P(p, t):
        if progress:
            progress(p, t)

    P(3, "Подготовка…")
    os.makedirs(target, exist_ok=True)

    src_exe = res_path(EXE_NAME)
    if not os.path.isfile(src_exe):
        raise FileNotFoundError(f"не найден {EXE_NAME} в сборке")
    dst_exe = os.path.join(target, EXE_NAME)
    P(8, "Копирование PhantomTalk…")
    copy_with_progress(src_exe, dst_exe, lambda f: P(8 + int(60 * f), "Копирование PhantomTalk…"))

    P(72, "Иконка и ресурсы…")
    icon_src = res_path("phantomtalk.ico")
    icon_dst = os.path.join(target, "phantomtalk.ico")
    if os.path.isfile(icon_src):
        shutil.copy2(icon_src, icon_dst)
    else:
        icon_dst = dst_exe

    # copy the setup itself as the uninstaller (frozen only)
    uninst_exe = os.path.join(target, UNINST_NAME)
    if getattr(sys, "frozen", False):
        try:
            shutil.copy2(sys.executable, uninst_exe)
        except Exception:
            uninst_exe = dst_exe
    else:
        uninst_exe = dst_exe

    P(80, "Создание ярлыков…")
    sm = _start_menu_dir()
    if opts.get("startmenu", True) and os.path.isdir(sm):
        make_shortcut(os.path.join(sm, f"{APP_NAME}.lnk"), dst_exe, icon_dst, target)
    if opts.get("desktop", True):
        d = _desktop_dir()
        if os.path.isdir(d):
            make_shortcut(os.path.join(d, f"{APP_NAME}.lnk"), dst_exe, icon_dst, target)
    if opts.get("startup", False):
        su = _startup_dir()
        if os.path.isdir(su):
            make_shortcut(os.path.join(su, f"{APP_NAME}.lnk"), dst_exe, icon_dst, target)

    P(90, "Регистрация в системе…")
    try:
        size_kb = os.path.getsize(dst_exe) / 1024
        register_uninstall(target, uninst_exe, icon_dst, size_kb)
    except Exception:
        pass

    P(100, "Готово")
    return dst_exe


def do_uninstall(target):
    # shortcuts
    for d in (_start_menu_dir(), _desktop_dir(), _startup_dir()):
        lnk = os.path.join(d, f"{APP_NAME}.lnk")
        try:
            if os.path.isfile(lnk):
                os.remove(lnk)
        except Exception:
            pass
    # registry
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Uninstall\PhantomTalk")
    except Exception:
        pass
    # schedule folder deletion (we may be running from inside it)
    try:
        bat = os.path.join(os.environ.get("TEMP", target), "pt_uninstall.bat")
        with open(bat, "w", encoding="cp866", errors="ignore") as f:
            f.write("@echo off\r\n")
            f.write("ping 127.0.0.1 -n 3 >nul\r\n")
            f.write(f'rmdir /s /q "{target}"\r\n')
            f.write('del "%~f0"\r\n')
        subprocess.Popen(["cmd", "/c", bat], creationflags=CREATE_NO_WINDOW,
                         close_fds=True)
    except Exception:
        pass


# ============================================================================
# GUI
# ============================================================================
def run_gui(uninstall_dir=None):
    from PyQt6.QtCore import (QEasingCurve, QPointF, QPropertyAnimation, QRectF,
                              Qt, QThread, QTimer, pyqtProperty, pyqtSignal)
    from PyQt6.QtGui import (QBrush, QColor, QConicalGradient, QFont,
                             QFontDatabase, QIcon, QLinearGradient, QPainter,
                             QPainterPath, QPen, QRadialGradient)
    from PyQt6.QtWidgets import (QApplication, QCheckBox, QFileDialog,
                                 QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                                 QLineEdit, QMainWindow, QMessageBox,
                                 QPushButton, QStackedWidget, QVBoxLayout,
                                 QWidget)

    SERIF = "Playfair Display"
    SANS = "Inter"

    def load_fonts():
        nonlocal SERIF, SANS
        for fn in ("PlayfairDisplay-Bold.ttf", "Inter-Regular.ttf"):
            p = res_path(fn)
            if os.path.isfile(p):
                fid = QFontDatabase.addApplicationFont(p)
                fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
                if fams:
                    if "Playfair" in fams[0]:
                        SERIF = fams[0]
                    elif "Inter" in fams[0]:
                        SANS = fams[0]

    # ---------- worker ----------
    class Worker(QThread):
        progress = pyqtSignal(int, str)
        done = pyqtSignal(bool, str, str)

        def __init__(self, target, opts):
            super().__init__()
            self.target = target
            self.opts = opts

        def run(self):
            try:
                exe = do_install(self.target, self.opts,
                                 progress=lambda p, t: self.progress.emit(p, t))
                self.done.emit(True, "", exe)
            except Exception as e:
                self.done.emit(False, str(e), "")

    # ---------- glowing progress bar ----------
    class GlowBar(QWidget):
        def __init__(self):
            super().__init__()
            self._v = 0.0
            self._sh = 0.0
            self.setFixedHeight(14)
            t = QTimer(self); t.timeout.connect(self._tick); t.start(33); self._t = t

        def _tick(self):
            self._sh = (self._sh + 0.02) % 1.0
            self.update()

        def get_v(self): return self._v
        def set_v(self, v): self._v = max(0.0, min(100.0, v)); self.update()
        value = pyqtProperty(float, get_v, set_v)

        def paintEvent(self, e):
            p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
            w, h = self.width(), self.height()
            p.setBrush(QColor(40, 30, 26)); p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
            fw = int(w * self._v / 100.0)
            if fw > h:
                g = QLinearGradient(0, 0, fw, 0)
                g.setColorAt(0.0, QColor(C["crimson"]))
                g.setColorAt(0.6, QColor(C["ember"]))
                g.setColorAt(1.0, QColor(C["amber"]))
                p.setBrush(QBrush(g))
                p.drawRoundedRect(0, 0, fw, h, h / 2, h / 2)
                # shimmer
                sx = int(fw * self._sh)
                sg = QLinearGradient(sx - 30, 0, sx + 30, 0)
                sg.setColorAt(0.0, QColor(255, 255, 255, 0))
                sg.setColorAt(0.5, QColor(255, 255, 255, 90))
                sg.setColorAt(1.0, QColor(255, 255, 255, 0))
                p.setBrush(QBrush(sg))
                p.drawRoundedRect(0, 0, fw, h, h / 2, h / 2)

    # ---------- animated checkmark ----------
    class Check(QWidget):
        def __init__(self):
            super().__init__()
            self._p = 0.0
            self.setFixedSize(120, 120)

        def get_p(self): return self._p
        def set_p(self, v): self._p = v; self.update()
        prog = pyqtProperty(float, get_p, set_p)

        def play(self):
            a = QPropertyAnimation(self, b"prog", self)
            a.setDuration(900); a.setStartValue(0.0); a.setEndValue(1.0)
            a.setEasingCurve(QEasingCurve.Type.OutCubic); a.start(); self._a = a

        def paintEvent(self, e):
            p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
            w = self.width(); cx = cy = w / 2
            ring = min(1.0, self._p * 1.4)
            pen = QPen(QColor(C["ember"]), 6); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoPen if False else Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(8, 8, w - 16, w - 16), 90 * 16, -int(360 * 16 * ring))
            # glow fill
            gg = QRadialGradient(QPointF(cx, cy), w / 2)
            gg.setColorAt(0.0, QColor(255, 106, 44, int(60 * self._p)))
            gg.setColorAt(1.0, QColor(255, 106, 44, 0))
            p.setBrush(QBrush(gg)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(8, 8, w - 16, w - 16))
            # check stroke
            cp = max(0.0, (self._p - 0.4) / 0.6)
            if cp > 0:
                pts = [QPointF(w * 0.34, w * 0.52), QPointF(w * 0.45, w * 0.64), QPointF(w * 0.68, w * 0.38)]
                pen2 = QPen(QColor(C["amber"]), 8)
                pen2.setCapStyle(Qt.PenCapStyle.RoundCap); pen2.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(pen2)
                path = QPainterPath(pts[0])
                if cp <= 0.5:
                    t = cp / 0.5
                    path.lineTo(pts[0] + (pts[1] - pts[0]) * t)
                else:
                    path.lineTo(pts[1])
                    t = (cp - 0.5) / 0.5
                    path.lineTo(pts[1] + (pts[2] - pts[1]) * t)
                p.drawPath(path)

    # ---------- backdrop (orb, rings, sparks) ----------
    class Backdrop(QWidget):
        def __init__(self):
            super().__init__()
            self._pulse = 0.0; self._rot = 0.0
            self._sparks = [self._mk(True) for _ in range(46)]
            t = QTimer(self); t.timeout.connect(self._tick); t.start(33); self._t = t

        def _mk(self, seed):
            return dict(x=random.uniform(0, max(1, self.width())),
                        y=random.uniform(0, self.height()) if seed else self.height() + 10,
                        r=random.uniform(0.6, 2.4), vy=random.uniform(0.3, 1.0),
                        vx=random.uniform(-0.2, 0.2), life=random.random())

        def _tick(self):
            self._pulse = (self._pulse + 0.04) % (2 * math.pi)
            self._rot = (self._rot + 0.35) % 360
            for s in self._sparks:
                s["y"] -= s["vy"]; s["x"] += s["vx"]; s["life"] += 0.02
                if s["y"] < -10:
                    s.update(self._mk(False)); s["x"] = random.uniform(0, self.width())
            self.update()

        def paintEvent(self, e):
            p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
            w, h = self.width(), self.height(); cx = w / 2
            p.fillRect(self.rect(), QColor(C["bg"]))
            g = QRadialGradient(QPointF(cx, h), max(w, h))
            g.setColorAt(0.0, QColor(214, 31, 18, 90)); g.setColorAt(0.5, QColor(214, 31, 18, 24)); g.setColorAt(1.0, QColor(10, 6, 5, 0))
            p.fillRect(self.rect(), QBrush(g))
            oy = 92
            for k, (rad, alpha, d) in enumerate([(70, 60, 1), (130, 38, -1), (200, 24, 1)]):
                grad = QConicalGradient(QPointF(cx, oy), self._rot * d)
                grad.setColorAt(0.0, QColor(255, 106, 44, 0)); grad.setColorAt(0.4, QColor(255, 106, 44, alpha))
                grad.setColorAt(0.6, QColor(255, 154, 90, alpha)); grad.setColorAt(1.0, QColor(255, 106, 44, 0))
                p.setPen(QPen(QBrush(grad), 2)); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, oy), rad, rad)
            pulse = 0.7 + 0.3 * (0.5 + 0.5 * math.sin(self._pulse))
            r = 22 + 6 * pulse
            og = QRadialGradient(QPointF(cx, oy), r * 6)
            og.setColorAt(0.0, QColor(255, 255, 255, 255)); og.setColorAt(0.12, QColor(255, 217, 168, 220))
            og.setColorAt(0.32, QColor(255, 106, 44, 170)); og.setColorAt(0.6, QColor(214, 31, 18, 70)); og.setColorAt(1.0, QColor(214, 31, 18, 0))
            p.setBrush(QBrush(og)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx, oy), r * 6, r * 6)
            p.setBrush(QColor(255, 222, 184)); p.drawEllipse(QPointF(cx, oy), r, r)
            # sparks
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            for s in self._sparks:
                fl = 0.5 + 0.5 * math.sin(s["life"] * 6.28)
                rr = s["r"] * (0.8 + 0.5 * fl)
                sg = QRadialGradient(QPointF(s["x"], s["y"]), rr * 4)
                sg.setColorAt(0.0, QColor(255, 150, 70, int(200 * fl))); sg.setColorAt(1.0, QColor(255, 120, 40, 0))
                p.setBrush(QBrush(sg)); p.drawEllipse(QPointF(s["x"], s["y"]), rr * 4, rr * 4)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    # ---------- main window ----------
    class Setup(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("PhantomTalk Setup")
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
            self.setFixedSize(780, 560)
            ic = res_path("phantomtalk.ico")
            if os.path.isfile(ic):
                self.setWindowIcon(QIcon(ic))
            self.backdrop = Backdrop()
            self.setCentralWidget(self.backdrop)
            root = QVBoxLayout(self.backdrop); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

            # title bar
            tb = QWidget(); tb.setFixedHeight(40)
            tl = QHBoxLayout(tb); tl.setContentsMargins(16, 0, 8, 0)
            t = QLabel("PhantomTalk Setup"); t.setFont(self._f(SERIF, 11, True)); t.setStyleSheet(f"color:{C['amber']};")
            tl.addWidget(t); tl.addStretch()
            cb = QPushButton("✕"); cb.setFixedSize(34, 26); cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setStyleSheet(f"QPushButton{{background:transparent;border:none;color:{C['dim']};border-radius:6px;}}"
                             f"QPushButton:hover{{background:{C['crimson']};color:white;}}")
            cb.clicked.connect(self.close)
            self._tb = tb
            tl.addWidget(cb)
            root.addWidget(tb)

            self.stack = QStackedWidget(); root.addWidget(self.stack, 1)
            self._uninstall_dir = uninstall_dir
            if uninstall_dir:
                self.stack.addWidget(self._page_uninstall())
            else:
                self.stack.addWidget(self._page_welcome())
                self.stack.addWidget(self._page_progress())
                self.stack.addWidget(self._page_done())
            self.stack.setCurrentIndex(0)
            self._fade(self.stack.currentWidget())
            self._center()

            # test hook: auto-run install (for screenshots/CI)
            if not uninstall_dir and os.environ.get("PT_AUTOSTART_INSTALL"):
                d = os.environ.get("PT_DIR")
                if d:
                    self.path_edit.setText(d)
                from PyQt6.QtCore import QTimer as _QT
                _QT.singleShot(1400, self._start_install)

        # helpers
        def _f(self, fam, sz, bold=False):
            f = QFont(fam, sz)
            if bold:
                f.setWeight(QFont.Weight.Black)
            return f

        def _center(self):
            scr = QApplication.primaryScreen().geometry()
            self.move((scr.width() - self.width()) // 2, (scr.height() - self.height()) // 2)

        def _fade(self, w, ms=420):
            eff = QGraphicsOpacityEffect(w); w.setGraphicsEffect(eff)
            a = QPropertyAnimation(eff, b"opacity", w)
            a.setDuration(ms); a.setStartValue(0.0); a.setEndValue(1.0)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            a.finished.connect(lambda: w.setGraphicsEffect(None)); a.start()
            self._anim = a

        def mousePressEvent(self, e):
            if e.button() == Qt.MouseButton.LeftButton and e.position().y() < 40:
                h = self.windowHandle()
                if h:
                    h.startSystemMove()

        def _btn(self, text, primary=True):
            b = QPushButton(text); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(46); b.setFont(self._f(SANS, 11, False))
            if primary:
                b.setStyleSheet(
                    f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {C['crimson']},stop:1 {C['ember']});"
                    f"color:white;border:none;border-radius:13px;padding:0 26px;font-weight:600;}}"
                    f"QPushButton:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {C['ember']},stop:1 {C['amber']});}}")
            else:
                b.setStyleSheet(
                    f"QPushButton{{background:rgba(255,255,255,0.05);color:{C['text']};border:1px solid {C['line']};"
                    f"border-radius:13px;padding:0 26px;}}"
                    f"QPushButton:hover{{background:rgba(255,106,44,0.12);border-color:{C['ember']};color:{C['amber']};}}")
            return b

        # ----- pages -----
        def _page_welcome(self):
            pg = QWidget(); v = QVBoxLayout(pg); v.setContentsMargins(70, 70, 70, 36); v.setSpacing(6)
            v.addSpacing(70)
            title = QLabel("PhantomTalk"); title.setFont(self._f(SERIF, 40, True))
            title.setStyleSheet(f"color:{C['amber']};"); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tag = QLabel("ГОЛОС · КОТОРЫЙ · СЛЫШНО"); tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tag.setStyleSheet(f"color:{C['dim']};letter-spacing:4px;font-size:9pt;font-weight:600;")
            blurb = QLabel("Голосовой мессенджер с собственными серверами.\nOpus 510 кбит/с stereo · красивее Discord.")
            blurb.setAlignment(Qt.AlignmentFlag.AlignCenter); blurb.setStyleSheet(f"color:{C['text']};font-size:10pt;")
            v.addWidget(title); v.addWidget(tag); v.addSpacing(10); v.addWidget(blurb)
            v.addStretch()

            # path
            pl = QHBoxLayout()
            self.path_edit = QLineEdit(default_dir())
            self.path_edit.setMinimumHeight(40)
            self.path_edit.setStyleSheet(
                f"QLineEdit{{background:{C['card']};border:1px solid {C['line']};border-radius:10px;"
                f"padding:8px 12px;color:{C['text']};}}QLineEdit:focus{{border-color:{C['ember']};}}")
            browse = self._btn("Обзор", primary=False); browse.setMinimumHeight(40)
            browse.clicked.connect(self._browse)
            pl.addWidget(self.path_edit, 1); pl.addWidget(browse)
            v.addLayout(pl)

            # options
            ol = QHBoxLayout()
            self.cb_desktop = self._check("Ярлык на рабочем столе", True)
            self.cb_menu = self._check("В меню «Пуск»", True)
            self.cb_startup = self._check("Запуск при старте Windows", False)
            ol.addWidget(self.cb_desktop); ol.addWidget(self.cb_menu); ol.addWidget(self.cb_startup); ol.addStretch()
            v.addLayout(ol)
            v.addSpacing(10)

            row = QHBoxLayout(); row.addStretch()
            go = self._btn("Установить  →")
            go.clicked.connect(self._start_install)
            row.addWidget(go)
            v.addLayout(row)
            return pg

        def _check(self, text, on):
            c = QCheckBox(text); c.setChecked(on); c.setCursor(Qt.CursorShape.PointingHandCursor)
            c.setStyleSheet(
                f"QCheckBox{{color:{C['dim']};font-size:9pt;spacing:7px;}}"
                f"QCheckBox::indicator{{width:16px;height:16px;border:1px solid {C['line']};border-radius:5px;background:{C['card']};}}"
                f"QCheckBox::indicator:checked{{background:{C['ember']};border-color:{C['ember']};}}")
            return c

        def _page_progress(self):
            pg = QWidget(); v = QVBoxLayout(pg); v.setContentsMargins(70, 70, 70, 60); v.setSpacing(14)
            v.addSpacing(150)
            h = QLabel("Устанавливаем PhantomTalk"); h.setFont(self._f(SERIF, 24, True))
            h.setStyleSheet(f"color:{C['text']};"); h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(h)
            self.step_label = QLabel("Подготовка…"); self.step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.step_label.setStyleSheet(f"color:{C['dim']};font-size:10pt;")
            v.addWidget(self.step_label)
            v.addSpacing(8)
            self.bar = GlowBar(); v.addWidget(self.bar)
            self.pct_label = QLabel("0%"); self.pct_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.pct_label.setStyleSheet(f"color:{C['amber']};font-family:'{SANS}';font-size:9pt;")
            v.addWidget(self.pct_label)
            v.addStretch()
            return pg

        def _page_done(self):
            pg = QWidget(); v = QVBoxLayout(pg); v.setContentsMargins(70, 50, 70, 40); v.setSpacing(8)
            v.addSpacing(40)
            self.check = Check(); cw = QHBoxLayout(); cw.addStretch(); cw.addWidget(self.check); cw.addStretch()
            v.addLayout(cw)
            h = QLabel("Установлено!"); h.setFont(self._f(SERIF, 30, True))
            h.setStyleSheet(f"color:{C['amber']};"); h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(h)
            sub = QLabel("PhantomTalk готов. Заходи и слушай по-настоящему.")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter); sub.setStyleSheet(f"color:{C['dim']};font-size:10pt;")
            v.addWidget(sub)
            v.addStretch()
            self.cb_launch = self._check("Запустить PhantomTalk сейчас", True)
            lw = QHBoxLayout(); lw.addStretch(); lw.addWidget(self.cb_launch); lw.addStretch()
            v.addLayout(lw)
            row = QHBoxLayout(); row.addStretch()
            fin = self._btn("Готово")
            fin.clicked.connect(self._finish)
            row.addWidget(fin); v.addLayout(row)
            return pg

        def _page_uninstall(self):
            pg = QWidget(); v = QVBoxLayout(pg); v.setContentsMargins(70, 80, 70, 50); v.setSpacing(10)
            v.addSpacing(120)
            h = QLabel("Удалить PhantomTalk?"); h.setFont(self._f(SERIF, 28, True))
            h.setStyleSheet(f"color:{C['text']};"); h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(h)
            sub = QLabel("Будут удалены приложение, ярлыки и запись в системе.")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter); sub.setStyleSheet(f"color:{C['dim']};font-size:10pt;")
            v.addWidget(sub); v.addStretch()
            row = QHBoxLayout(); row.addStretch()
            no = self._btn("Отмена", primary=False); no.clicked.connect(self.close)
            yes = self._btn("Удалить")
            yes.clicked.connect(self._do_uninstall_gui)
            row.addWidget(no); row.addWidget(yes); v.addLayout(row)
            return pg

        # ----- actions -----
        def _browse(self):
            d = QFileDialog.getExistingDirectory(self, "Куда установить", self.path_edit.text())
            if d:
                self.path_edit.setText(os.path.join(d, APP_NAME) if not d.endswith(APP_NAME) else d)

        def _start_install(self):
            target = self.path_edit.text().strip() or default_dir()
            self._target = target
            opts = dict(desktop=self.cb_desktop.isChecked(),
                        startmenu=self.cb_menu.isChecked(),
                        startup=self.cb_startup.isChecked())
            self.stack.setCurrentIndex(1); self._fade(self.stack.widget(1))
            self._disp = 0.0
            self._worker = Worker(target, opts)
            self._worker.progress.connect(self._on_prog)
            self._worker.done.connect(self._on_done)
            self._worker.start()
            self._smooth = QTimer(self); self._smooth.timeout.connect(self._tick_bar); self._smooth.start(20)
            self._target_pct = 0

        def _on_prog(self, pct, text):
            self._target_pct = pct
            self.step_label.setText(text)

        def _tick_bar(self):
            self._disp += (self._target_pct - self._disp) * 0.18
            self.bar.set_v(self._disp)
            self.pct_label.setText(f"{int(self._disp)}%")
            if self._disp >= 99.4 and self._target_pct >= 100:
                self.bar.set_v(100); self.pct_label.setText("100%")
                self._smooth.stop()

        def _on_done(self, ok, err, exe):
            if not ok:
                QMessageBox.critical(self, "Ошибка установки", err or "неизвестно")
                self.stack.setCurrentIndex(0); return
            self._installed_exe = exe
            QTimer.singleShot(500, self._go_done)

        def _go_done(self):
            self.stack.setCurrentIndex(2); self._fade(self.stack.widget(2))
            self.check.play()

        def _finish(self):
            if getattr(self, "cb_launch", None) and self.cb_launch.isChecked():
                exe = getattr(self, "_installed_exe", None)
                if exe and os.path.isfile(exe):
                    try:
                        subprocess.Popen([exe], cwd=os.path.dirname(exe))
                    except Exception:
                        pass
            self.close()

        def _do_uninstall_gui(self):
            do_uninstall(self._uninstall_dir)
            QMessageBox.information(self, "PhantomTalk", "PhantomTalk удалён.")
            self.close()

    app = QApplication(sys.argv)
    app.setApplicationName("PhantomTalk Setup")
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PhantomTalk.Setup.1")
    except Exception:
        pass
    load_fonts()
    ic = res_path("phantomtalk.ico")
    if os.path.isfile(ic):
        app.setWindowIcon(QIcon(ic))
    win = Setup(); win.show()
    return app.exec()


# ============================================================================
# ENTRY
# ============================================================================
def main():
    args = sys.argv[1:]
    if "--uninstall" in args:
        i = args.index("--uninstall")
        target = args[i + 1] if i + 1 < len(args) else default_dir()
        if "--silent" in args:
            do_uninstall(target); return 0
        return run_gui(uninstall_dir=target)
    if "--silent" in args:
        target = default_dir()
        if "--dir" in args:
            target = args[args.index("--dir") + 1]
        print(f"[silent] installing to {target}")
        do_install(target, dict(desktop=True, startmenu=True, startup=False),
                   progress=lambda p, t: print(f"  {p:3d}%  {t}"))
        print("[silent] done")
        return 0
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
