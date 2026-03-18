#!/usr/bin/env python3
"""
cloud-forge GUI
rclone remote management + rclone-sftp server management

Entry point — imports all modules and starts the application.

Module layout:
  theme.py        DARK palette + STYLESHEET
  workers.py      CmdWorker, OutputBox, BaseRunner
  dialogs.py      AddRemoteDialog, RenameDialog, StartServerDialog, PROVIDERS
  tab_remote.py   RemoteTab
  tab_server.py   ServerTab
  tab_config.py   ConfigTab
  window.py       MainWindow
  cloud_forge.py  main() + single-instance guard  ← this file
"""

import sys
import traceback

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QSettings
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtGui import QFont, QColor, QPalette

from theme import DARK, STYLESHEET
from window import MainWindow

_INSTANCE_KEY = "cloud-forge-single-instance"


def main():
    def _excepthook(exc_type, exc_value, exc_tb):
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print(f"[UNHANDLED ERROR]\n{msg}", file=sys.stderr)
        QMessageBox.critical(
            None, "Unexpected Error",
            f"{exc_type.__name__}: {exc_value}\n\nSee terminal for full traceback."
        )

    sys.excepthook = _excepthook

    app = QApplication(sys.argv)
    app.setApplicationName("cloud-forge")
    app.setStyle("Fusion")
    app.setFont(QFont("JetBrains Mono", 16))

    # ── Single-instance guard ────────────────────────────────────────
    socket = QLocalSocket()
    socket.connectToServer(_INSTANCE_KEY)
    if socket.waitForConnected(300):
        # Another instance running — raise it and exit
        socket.write(b"raise\n")
        socket.flush()
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        sys.exit(0)
    socket.deleteLater()

    local_server = QLocalServer()
    QLocalServer.removeServer(_INSTANCE_KEY)
    local_server.listen(_INSTANCE_KEY)

    # ── Dark palette ─────────────────────────────────────────────────
    palette = QPalette()
    palette.setColor(QPalette.Window,          QColor(DARK['bg']))
    palette.setColor(QPalette.WindowText,      QColor(DARK['text']))
    palette.setColor(QPalette.Base,            QColor(DARK['bg']))
    palette.setColor(QPalette.AlternateBase,   QColor(DARK['panel']))
    palette.setColor(QPalette.Text,            QColor(DARK['text']))
    palette.setColor(QPalette.Button,          QColor(DARK['btn']))
    palette.setColor(QPalette.ButtonText,      QColor(DARK['text']))
    palette.setColor(QPalette.Highlight,       QColor(DARK['accent']))
    palette.setColor(QPalette.HighlightedText, QColor(DARK['bg']))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)

    win = MainWindow()
    win.show()

    def _on_new_connection():
        """Second instance tried to start — bring this window to front."""
        conn = local_server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(200)
            conn.deleteLater()
        win.show()
        win.raise_()
        win.activateWindow()

    local_server.newConnection.connect(_on_new_connection)

    ret = app.exec_()
    local_server.close()
    QLocalServer.removeServer(_INSTANCE_KEY)
    sys.exit(ret)


if __name__ == "__main__":
    main()
