"""PhantomTalk client entrypoint — single unified window."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from PyQt6.QtWidgets import QApplication

import opus_loader      # noqa: F401  (must load before opuslib import)
import theme
from ui import PhantomApp


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PhantomTalk")

    # Bundled Claude-style fonts (Playfair Display + Inter) before QSS.
    theme.load_fonts()
    app.setStyleSheet(theme.qss())

    win = PhantomApp()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
