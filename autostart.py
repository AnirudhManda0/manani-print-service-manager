"""Windows autostart helpers for PrintX."""

import os
import sys
from typing import Dict, Tuple

from branding import APP_NAME, AUTOSTART_REGISTRY_NAME, icon_path

try:  # pragma: no cover - Windows specific.
    import winreg
except ImportError:  # pragma: no cover - non-Windows runtime.
    winreg = None

try:  # pragma: no cover - Windows specific.
    from win32com.client import Dispatch
except ImportError:  # pragma: no cover - non-Windows runtime.
    Dispatch = None


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _autostart_parts() -> Tuple[str, str, str]:
    if getattr(sys, "frozen", False):
        target = sys.executable
        arguments = "--background"
        working_dir = os.path.dirname(sys.executable)
    else:
        main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        target = sys.executable
        arguments = f'"{main_path}" --background'
        working_dir = os.path.dirname(main_path)
    return target, arguments, working_dir


def _autostart_command() -> str:
    target, arguments, _working_dir = _autostart_parts()
    suffix = f" {arguments}".rstrip()
    return f'"{target}"{suffix}'


def _startup_shortcut_path() -> str:
    appdata = os.environ.get("APPDATA", "")
    startup_dir = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    return os.path.join(startup_dir, f"{APP_NAME}.lnk")


def is_supported() -> bool:
    return os.name == "nt" and winreg is not None


def _registry_enabled() -> bool:
    if not is_supported():
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, AUTOSTART_REGISTRY_NAME)
            return bool(str(value).strip())
    except OSError:
        return False


def _set_registry_enabled(enabled: bool) -> bool:
    if not is_supported():
        return False
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, AUTOSTART_REGISTRY_NAME, 0, winreg.REG_SZ, _autostart_command())
        else:
            try:
                winreg.DeleteValue(key, AUTOSTART_REGISTRY_NAME)
            except OSError:
                pass
    return _registry_enabled()


def _startup_shortcut_supported() -> bool:
    return is_supported() and Dispatch is not None


def _startup_shortcut_enabled() -> bool:
    return os.path.exists(_startup_shortcut_path())


def _set_startup_shortcut(enabled: bool) -> bool:
    shortcut_path = _startup_shortcut_path()
    if not enabled:
        try:
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
        except OSError:
            pass
        return _startup_shortcut_enabled()

    if not _startup_shortcut_supported():
        return False

    os.makedirs(os.path.dirname(shortcut_path), exist_ok=True)
    target, arguments, working_dir = _autostart_parts()
    shell = Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = target
    shortcut.Arguments = arguments
    shortcut.WorkingDirectory = working_dir
    shortcut.Description = "Start PrintX in background mode"
    if getattr(sys, "frozen", False):
        shortcut.IconLocation = target
    else:
        shortcut.IconLocation = icon_path() if os.path.exists(icon_path()) else target
    shortcut.Save()
    return _startup_shortcut_enabled()


def is_enabled() -> bool:
    return _registry_enabled() or _startup_shortcut_enabled()


def set_enabled(enabled: bool) -> bool:
    registry_state = _set_registry_enabled(enabled)
    shortcut_state = _set_startup_shortcut(enabled)
    if enabled:
        return registry_state or shortcut_state
    return (not _registry_enabled()) and (not _startup_shortcut_enabled())


def get_status() -> Dict[str, object]:
    registry_enabled = _registry_enabled()
    shortcut_enabled = _startup_shortcut_enabled()
    return {
        "supported": is_supported(),
        "enabled": registry_enabled or shortcut_enabled,
        "registry_enabled": registry_enabled,
        "startup_shortcut_enabled": shortcut_enabled,
        "startup_shortcut_supported": _startup_shortcut_supported(),
        "command": _autostart_command(),
        "shortcut_path": _startup_shortcut_path(),
    }
