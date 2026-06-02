"""PhantomTalk client entrypoint."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from PyQt6.QtWidgets import QApplication

import opus_loader      # noqa: F401  (must load before opuslib import)
import theme
from welcome import Welcome
from ui import LoginDialog, MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PhantomTalk")

    # Load bundled Claude-style fonts (Playfair Display + Inter) before applying QSS.
    theme.load_fonts()
    app.setStyleSheet(theme.qss())

    win_ref = {}            # keep refs alive

    def open_login():
        login = LoginDialog()
        if not login.exec():
            app.quit(); return
        m = MainWindow(
            base_url=login.server_url.text().strip(),
            server_id=login.selected_server_id,
            nickname=login.nick.text().strip() or "Phantom",
        )
        win_ref["m"] = m
        m.show()

    # First-launch welcome (skippable). Then proceed to login.
    show_welcome = os.environ.get("PT_NO_WELCOME") != "1"
    if show_welcome:
        w = Welcome()
        win_ref["w"] = w
        w.showMaximized()
        w.finished.connect(open_login)
    else:
        open_login()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
