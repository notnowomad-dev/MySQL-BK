import sys
import os
import subprocess

# Ensure the project root is on sys.path regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _vcredist_installed() -> bool:
    # PyQt6 requires the 2019/2022 runtime — MSVCP140_1.dll is the distinguishing file
    root = os.environ.get("SystemRoot", r"C:\Windows")
    sys32 = os.path.join(root, "System32")
    return all(
        os.path.exists(os.path.join(sys32, dll))
        for dll in ("MSVCP140.dll", "MSVCP140_1.dll", "VCRUNTIME140_1.dll")
    )


def _missing_dlls() -> list:
    """Return names of Qt-critical DLLs that cannot be loaded."""
    import ctypes
    missing = []
    for name in (
        "MSVCP140.dll", "MSVCP140_1.dll",
        "VCRUNTIME140.dll", "VCRUNTIME140_1.dll",
        "d3d11.dll", "dxgi.dll",
    ):
        try:
            ctypes.WinDLL(name)
        except OSError:
            missing.append(name)
    return missing


def _write_startup_log(exc: Exception) -> str:
    """Write a full diagnostic log and return the file path."""
    import ctypes
    import traceback
    import platform
    import datetime
    import importlib.util

    # Write next to the exe; fall back to %TEMP%
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    log_path = os.path.join(base, "startup_error.log")
    try:
        open(log_path, "w").close()
    except Exception:
        import tempfile
        log_path = os.path.join(tempfile.gettempdir(), "mysql_backup_startup_error.log")

    out = []
    out.append("MySQL Backup Scheduler — Startup Error Log")
    out.append(f"Generated : {datetime.datetime.now()}")
    out.append("")
    out.append("=== System ===")
    out.append(f"Python     : {sys.version}")
    out.append(f"Arch       : {'64-bit' if sys.maxsize > 2**32 else '32-bit'}")
    out.append(f"Platform   : {platform.platform()}")
    out.append(f"Win version: {platform.version()}")
    try:
        out.append(f"Edition    : {platform.win32_edition()}")
    except Exception:
        pass
    out.append("")
    out.append("=== Exception ===")
    out.append(traceback.format_exc())
    out.append("")
    out.append("=== Common DLL check ===")
    for name in (
        "MSVCP140.dll", "MSVCP140_1.dll",
        "VCRUNTIME140.dll", "VCRUNTIME140_1.dll",
        "d3d11.dll", "dxgi.dll", "opengl32.dll",
    ):
        try:
            ctypes.WinDLL(name)
            out.append(f"  OK      {name}")
        except OSError as e:
            out.append(f"  MISSING {name} — {e}")
    out.append("")
    out.append("=== PyQt6 Qt6/bin DLL check ===")
    try:
        spec = importlib.util.find_spec("PyQt5") or importlib.util.find_spec("PyQt6")
        if spec and spec.origin:
            pkg_dir = os.path.dirname(spec.origin)
            qt_bin = next(
                (os.path.join(pkg_dir, d, "bin") for d in ("Qt5", "Qt6", "Qt")
                 if os.path.isdir(os.path.join(pkg_dir, d, "bin"))),
                None,
            )
            out.append(f"Path: {qt_bin}")
            if qt_bin and os.path.isdir(qt_bin):
                for fname in sorted(os.listdir(qt_bin)):
                    if fname.lower().endswith(".dll"):
                        try:
                            ctypes.WinDLL(os.path.join(qt_bin, fname))
                            out.append(f"  OK      {fname}")
                        except OSError as e:
                            out.append(f"  FAIL    {fname} — {e}")
            else:
                out.append("  Qt6/bin directory not found")
        else:
            out.append("  PyQt6 package not found in sys.path")
    except Exception as e:
        out.append(f"  Error enumerating PyQt6: {e}")

    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))

    return log_path


def _ensure_vcredist():
    """Install the bundled VC++ Redistributable silently if it is missing."""
    if sys.platform != "win32" or _vcredist_installed():
        return

    # PyInstaller bundle: sys._MEIPASS; source run: next to main.py
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    installer = os.path.join(base, "vc_redist.x64.exe")
    if not os.path.exists(installer):
        return  # Not bundled — ImportError below will show a helpful message

    import ctypes
    ctypes.windll.user32.MessageBoxW(
        0,
        "The Microsoft Visual C++ Redistributable is required but not installed.\n\n"
        "It will be installed now. A UAC prompt may appear — click Yes to continue.",
        "MySQL Backup Scheduler — Setup",
        0x40,  # MB_ICONINFORMATION
    )

    result = subprocess.run(
        [installer, "/install", "/quiet", "/norestart"],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    rc = result.returncode
    if rc == 0:
        # Installed cleanly — DLLs are live in this session, continue
        ctypes.windll.user32.MessageBoxW(
            0,
            "Visual C++ Redistributable installed successfully.\n"
            "The application will now start.",
            "MySQL Backup Scheduler — Setup",
            0x40,
        )
    elif rc == 3010:
        # Installed but Windows requires a restart before DLLs are usable
        ctypes.windll.user32.MessageBoxW(
            0,
            "Visual C++ Redistributable installed successfully.\n\n"
            "A restart is required before the application can run.\n"
            "Please restart your computer, then launch the app again.",
            "MySQL Backup Scheduler — Restart Required",
            0x30,  # MB_ICONWARNING
        )
        sys.exit(0)
    elif rc == 1223:
        # User cancelled the UAC prompt
        ctypes.windll.user32.MessageBoxW(
            0,
            "Installation was cancelled.\n\n"
            "The application cannot start without the Visual C++ Redistributable.\n"
            "Run the app again and click Yes when the UAC prompt appears.",
            "MySQL Backup Scheduler — Setup Cancelled",
            0x30,
        )
        sys.exit(0)
    else:
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Installation failed (exit code {rc}).\n\n"
            "Please install manually:\n"
            "https://aka.ms/vs/17/release/vc_redist.x64.exe",
            "MySQL Backup Scheduler — Setup Failed",
            0x10,  # MB_ICONERROR
        )
        sys.exit(1)


_ensure_vcredist()

# Software OpenGL avoids missing d3d11/dxgi on Server editions and headless machines
os.environ.setdefault("QT_OPENGL", "software")

try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QFont
    from PyQt5.QtNetwork import QLocalServer, QLocalSocket
except ImportError as _err:
    import ctypes
    import platform
    _log = _write_startup_log(_err)
    _is_server = "server" in platform.version().lower() or "server" in platform.release().lower()
    _server_note = (
        "\n\nNOTE: Windows Server 2016 is not officially supported by Qt 6 / PyQt6.\n"
        "Qt 6 requires Windows 10 build 1809 or later (Server 2019+).\n"
        "Consider upgrading to Windows Server 2019/2022."
        if _is_server else ""
    )
    ctypes.windll.user32.MessageBoxW(
        0,
        (
            f"Failed to load PyQt6:\n{_err}\n\n"
            f"A diagnostic log has been written to:\n{_log}\n\n"
            "Common fix: install Microsoft Visual C++ 2015-2022 Redistributable (x64)\n"
            "and reboot, then run the app again."
            f"{_server_note}"
        ),
        "MySQL Backup Scheduler — Startup Error",
        0x10,
    )
    sys.exit(1)

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
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

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
