"""Central PrintX branding and asset helpers."""

import os

from ui.resources import ui_resource_path


APP_NAME = "PrintX"
APP_SUBTITLE = "Print and Service Manager"
APP_FULL_NAME = APP_NAME
APP_API_TITLE = f"{APP_NAME} API"
MAIN_EXECUTABLE_NAME = "PrintX"
LEGACY_EXECUTABLE_NAME = "PrintX_Win7"
AUTOSTART_REGISTRY_NAME = APP_NAME
DEFAULT_DATABASE_NAME = "printx.db"
DEFAULT_ARCHIVE_DATABASE_NAME = "printx_archive.db"
DEFAULT_BACKUP_PREFIX = "printx"
OFFICIAL_LOGO_SOURCE = r"C:\Users\Manda Anirudh\Documents\manani-print-manager\releases\windows10\TheRealPrintxLogo.png"


def asset_path(filename: str) -> str:
    return ui_resource_path(os.path.join("assets", filename))


def logo_path() -> str:
    if os.path.exists(OFFICIAL_LOGO_SOURCE):
        return OFFICIAL_LOGO_SOURCE
    return asset_path("logo.png")


def icon_path() -> str:
    return asset_path("app_icon.ico")
