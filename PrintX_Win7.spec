# -*- mode: python ; coding: utf-8 -*-

import importlib.util
from pathlib import Path

project_root = Path(SPECPATH)

datas = [
    ("database/schema.sql", "database"),
    ("config/settings.json", "config"),
    ("assets/logo.png", "assets"),
    ("assets/app_icon.ico", "assets"),
    ("ui/icons/*.svg", "ui/icons"),
    ("version.txt", "."),
]

hiddenimports = [
    "pythoncom",
    "pywintypes",
    "win32api",
    "win32com",
    "win32com.client",
    "win32print",
    "win32con",
    "win32file",
    "win32timezone",
]

if importlib.util.find_spec("PySide2") is not None:
    hiddenimports.extend(["PySide2.QtCore", "PySide2.QtGui", "PySide2.QtWidgets"])

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["PySide6", "shiboken6"],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PrintX_Win7",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon="assets/app_icon.ico",
)
