import sys
import os

# Ensure the project root is on sys.path regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtNetwork import QLocalServer, QLocalSocket  # type: ignore[import-untyped]

from storage.database import Database
from core.scheduler import BackupScheduler
from ui.main_window import MainWindow

_INSTANCE_KEY = "MySQLBackupScheduler_SingleInstance_v1"


def _signal_existing_instance() -> bool:
    """Try to reach a running instance. Returns True if one was found."""
    sock = QLocalSocket()
    sock.connectToServer(_INSTANCE_KEY)
    if sock.waitForConnected(1000):
        sock.write(b"SHOW")
        sock.flush()
        sock.waitForBytesWritten(1000)
        sock.disconnectFromServer()
        return True
    return False


def _start_instance_server(window: "MainWindow") -> QLocalServer:
    """Create the local server that listens for signals from future instances."""
    QLocalServer.removeServer(_INSTANCE_KEY)   # clean up any leftover from a crash
    server = QLocalServer()
    server.listen(_INSTANCE_KEY)

    def _on_connection():
        client = server.nextPendingConnection()
        if client:
            # Read all pending data and restore window
            client.readyRead.connect(lambda: _on_data(client))

    def _on_data(client):
        client.readAll()          # consume the bytes
        window._restore_window()
        client.disconnectFromServer()

    server.newConnection.connect(_on_connection)
    return server                 # caller must keep a reference


def main():
    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("MySQL Backup Scheduler")
    app.setOrganizationName("MySQLBackup")
    app.setQuitOnLastWindowClosed(False)

    font = app.font()
    font.setPointSize(font.pointSize() + 2)
    app.setFont(font)

    # ── Single-instance check ──────────────────────────────────────────────────
    if _signal_existing_instance():
        # Another copy is already running — it will restore itself; we exit.
        return 0

    # ── First instance: start normally ────────────────────────────────────────
    try:
        db = Database()
        db.initialize()
    except Exception as exc:
        QMessageBox.critical(None, "Startup error", f"Failed to open database:\n{exc}")
        return 1

    scheduler = BackupScheduler(db)
    try:
        scheduler.start()
    except Exception as exc:
        QMessageBox.critical(None, "Startup error", f"Failed to start scheduler:\n{exc}")
        return 1

    window = MainWindow(db, scheduler)
    window.show()

    # Attach server to app so it stays alive for the full lifetime of the process
    app._instance_server = _start_instance_server(window)  # type: ignore[attr-defined]

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
