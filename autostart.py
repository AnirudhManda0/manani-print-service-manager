"""Windows autostart helpers for PrintX."""

import os
import sys
from typing import Dict

from branding import AUTOSTART_REGISTRY_NAME

try:  # pragma: no cover - Windows specific.
    import winreg
except ImportError:  # pragma: no cover - non-Windows runtime.
    winreg = None


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _autostart_command() -> str:
    if getattr(sys, "frozen", False):
        base = f'"{sys.executable}"'
    else:
        main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        base = f'"{sys.executable}" "{main_path}"'
    return f"{base} --background"


def is_supported() -> bool:
    return os.name == "nt" and winreg is not None


def is_enabled() -> bool:
    if not is_supported():
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, AUTOSTART_REGISTRY_NAME)
            return bool(str(value).strip())
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    if not is_supported():
        return False
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, AUTOSTART_REGISTRY_NAME, 0, winreg.REG_SZ, _autostart_command())
        else:
            try:
                winreg.DeleteValue(key, AUTOSTART_REGISTRY_NAME)
            except OSError:
                pass
    return is_enabled()


def get_status() -> Dict[str, object]:
    return {
        "supported": is_supported(),
        "enabled": is_enabled(),
        "command": _autostart_command(),
    }
