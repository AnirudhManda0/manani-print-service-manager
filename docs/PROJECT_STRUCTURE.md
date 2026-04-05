# Project Structure

## Top Level

- `main.py`
  Runtime entrypoint for UI, API, tray behavior, and print monitor startup.
- `branding.py`
  Central app naming, logo, icon, executable, and database file constants.
- `autostart.py`
  Windows auto-start integration for both registry and Startup-folder shortcut.
- `runtime_config.py`
  Loads, validates, normalizes, and recreates `config/settings.json`.
- `network_discovery.py`
  UDP discovery between clients and the central server.
- `PrintX.spec`
  Windows 10+ PyInstaller build.
- `PrintX_Win7.spec`
  Legacy Windows 7 PyInstaller build definition.

## Client Layer

- `client/print_monitor.py`
  Polls all printers with the Windows Print Spooler API and sends transactions.
- `client/run_client.py`
  Background client monitor launcher.

## Server Layer

- `server/api.py`
  FastAPI service surface used by the desktop UI and monitor clients.
- `server/database.py`
  Thread-safe SQLite access, billing logic, reports, backups, and retention.
- `server/models.py`
  Pydantic request models for API validation.

## UI Layer

- `ui/main_window.py`
  Main operator shell, dashboard, tray behavior, and print log.
- `ui/dashboard.py`
  Compact KPI cards used by the dashboard.
- `ui/charts.py`
  Reusable revenue and contribution charts shared by reports.
- `ui/services_panel.py`
  Service catalog display and confirmation-based service recording.
- `ui/reports_panel.py`
  Period reporting UI with charts and service breakdowns.
- `ui/settings_panel.py`
  Runtime configuration editor.
- `ui/api_client.py`
  Synchronous client wrapper around FastAPI routes.
- `ui/theme.py`
  Shared stylesheet and theme definitions.
- `ui/resources.py`
  Resource path resolution for source and PyInstaller modes.
- `ui/qt.py`
  Shared Qt import compatibility layer.

## Data and Assets

- `config/settings.json`
  Operator-editable runtime config.
- `database/schema.sql`
  SQLite schema.
- `database/init_db.py`
  First-run DB initializer.
- `assets/logo.png`
  PrintX logo for UI and documentation.
- `assets/app_icon.ico`
  Embedded executable icon.

## Release and Operations

- `releases/windows10`
  Windows 10+ release payloads.
- `releases/windows7`
  Legacy Windows 7 release payloads.
- `logs/`
  Rotating app logs, including `logs/printx.log`.
- `backup/`
  Daily SQLite backups.

## Execution Flow

1. `main.py` loads and validates `settings.json`.
2. Runtime folders are created if missing.
3. API server starts for `single` or `server` mode.
4. Print monitor starts and enumerates printers.
5. New jobs are posted to FastAPI.
6. FastAPI writes validated transactions to SQLite.
7. UI refreshes dashboard KPI cards, print log, and reports from API responses.
8. Closing the window hides PrintX to the tray so monitoring can continue.

## Data Flow

`Windows Printer -> Spooler -> client/print_monitor.py -> server/api.py -> server/database.py -> SQLite -> UI`
