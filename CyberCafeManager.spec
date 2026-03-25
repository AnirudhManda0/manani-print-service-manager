# -*- mode: python ; coding: utf-8 -*-

import importlib.util
from pathlib import Path

project_root = Path(SPECPATH)

datas = [
    ("database/schema.sql", "database"),
    ("config/settings.json", "config"),
    ("ui/icons/*.svg", "ui/icons"),
    ("version.txt", "."),
]

hiddenimports = [
    "pythoncom",
    "pywintypes",
    "win32api",
    "win32print",
    "win32con",
    "win32file",
    "win32timezone",
]

if importlib.util.find_spec("PySide2") is not None:
    hiddenimports.extend(["PySide2.QtCore", "PySide2.QtGui", "PySide2.QtWidgets"])
if importlib.util.find_spec("PySide6") is not None:
    hiddenimports.extend(["PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"])

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CyberCafeManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
