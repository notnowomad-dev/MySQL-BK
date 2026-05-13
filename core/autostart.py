import os
import sys

try:
    import winreg
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

_APP_NAME = "MySQLBackupScheduler"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _launch_command() -> str:
    if getattr(sys, "frozen", False):
        # Running as PyInstaller .exe
        return f'"{sys.executable}"'
    # Running from source — use pythonw so no console window appears on login
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        exe = exe[:-10] + "pythonw.exe"
    script = os.path.abspath(sys.argv[0])
    return f'"{exe}" "{script}"'


def set_autostart(enabled: bool) -> tuple[bool, str]:
    if not _AVAILABLE:
        return False, "Windows registry not available."
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _launch_command())
            else:
                try:
                    winreg.DeleteValue(key, _APP_NAME)
                except FileNotFoundError:
                    pass
        return True, ""
    except Exception as e:
        return False, str(e)


def get_autostart() -> bool:
    if not _AVAILABLE:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
    except FileNotFoundError:
        return False
