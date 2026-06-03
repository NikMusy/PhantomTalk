"""PhantomTalk client entrypoint — single unified window."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

import opus_loader      # noqa: F401  (must load before opuslib import)
import theme
from ui import PhantomApp


def _icon_path() -> str:
    meipass = getattr(sys, "_MEIPASS", None)
    for base in (meipass, HERE):
        if not base:
            continue
        for name in ("phantomtalk.ico", "phantomtalk.png"):
            p = os.path.join(base, name)
            if os.path.isfile(p):
                return p
    return ""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PhantomTalk")

    # Taskbar icon grouping on Windows (so our icon shows, not python's).
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PhantomTalk.Voice.1")
    except Exception:
        pass

    ic = _icon_path()
    if ic:
        app.setWindowIcon(QIcon(ic))

    # Bundled Claude-style fonts (Playfair Display + Inter) before QSS.
    theme.load_fonts()
    app.setStyleSheet(theme.qss())

    win = PhantomApp()
    if ic:
        win.setWindowIcon(QIcon(ic))
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
