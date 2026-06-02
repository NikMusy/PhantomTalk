"""PhantomTalk client entrypoint."""
import os
import sys

# Make `import opus_loader / audio / net / ui` work when frozen by PyInstaller
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

import opus_loader  # noqa: F401   (loads libopus before anything else)
from ui import LoginDialog, MainWindow, DARK_QSS


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PhantomTalk")
    app.setStyleSheet(DARK_QSS)

    login = LoginDialog()
    if not login.exec():
        return 0

    win = MainWindow(
        base_url=login.server_url.text().strip(),
        server_id=login.selected_server_id,
        nickname=login.nick.text().strip() or "Phantom",
    )
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
