# Developer Guide - ManAni Print & Service Manager

This document explains internal architecture, module responsibilities, and extension points for the ManAni Print & Service Manager codebase.

## 1. System Design

The app is a local-first desktop system:

`Print Monitor -> FastAPI -> SQLite -> PySide6 UI`

Components:

- `client`: Windows spooler monitoring and job submission
- `server`: API + database operations
- `ui`: operator desktop interface
- `database`: schema and initialization scripts
- `config`: runtime app configuration

## 2. Entry Point

## `main.py`

Purpose:

- Loads runtime config and bundled resources
- Starts API server in thread (single/server mode)
- Starts print monitor where required
- Launches PySide6 main window
- Configures centralized logging (`logs/application.log`)

Key functions:

- `configure_logging()`: console + rotating file logging
- `ensure_runtime_files()`: ensures `config/settings.json` and `database/schema.sql` exist
- `run_single_mode(config)`: API + monitor + UI
- `run_server_mode(config, with_ui)`: centralized server mode
- `run_client_mode(config, server_url)`: client monitor-only mode

## 3. Client Monitoring

## `client/print_monitor.py`

Purpose:

- Polls Windows spooler for all local/connected printers
- Detects queued jobs and deduplicates seen jobs
- Extracts metadata and posts to API

Windows APIs used:

- `win32print.EnumPrinters`
- `win32print.EnumJobs`
- `win32print.GetJob`

Captured fields:

- `computer_name`
- `printer_name`
- `document_name`
- `pages`
- `timestamp`
- `print_type`
- `paper_size`

Important behavior:

- Poll interval default: `0.5s`
- Debug logs for printer/job detection and parsed metadata
- Color detection fallback from job DEVMODE -> printer DEVMODE -> monochrome-name fallback
- Paper-size mapping to `A4/A3/Letter/Unknown`

## `client/run_client.py`

Purpose:

- Lightweight CLI wrapper for remote monitor clients

## 4. API Layer

## `server/api.py`

Purpose:

- Exposes all desktop/API actions through FastAPI endpoints
- Logs API request latency and status
- Triggers periodic daily-backup checks

Main endpoints:

- `GET /health`
- `GET/PUT /api/settings`
- `POST/GET /api/print-jobs`
- `GET/POST /api/services/catalog`
- `POST /api/services/record`
- `GET /api/dashboard`
- `GET /api/reports/{period}`
- `GET /api/data-retention/status`
- `POST /api/data-retention/execute`
- `POST /api/backup/run`

## `server/models.py`

Purpose:

- Pydantic validation for requests

Important models:

- `PrintJobCreate` includes `paper_size`
- `SettingsUpdate` includes retention + backup config

## 5. Database Layer

## `server/database.py`

Purpose:

- Thread-safe SQLite access using `RLock`
- WAL mode and connection pragmas
- Schema migration handling for existing databases
- Billing logic, reports, retention, archive, backup

Key design choices:

- Money calculations use `Decimal` and 2-decimal quantization
- Historical job records persist `price_per_page` and `total_cost`
- Settings include backup and retention options
- `run_daily_backup()` uses SQLite backup API for safe copies

Primary methods:

- `get_settings()` / `update_settings(...)`
- `add_print_job(...)`
- `list_print_jobs(...)`
- `add_service_catalog(...)`
- `record_service(...)`
- `get_dashboard(day)`
- `get_report(period, day)`
- `archive_old_records(days)`
- `delete_old_records(days)`
- `run_daily_backup(force=False)`

## 6. Database Schema

## `database/schema.sql`

Tables:

- `print_jobs` (includes `print_type`, `paper_size`, `price_per_page`, `total_cost`, `timestamp`)
- `services_catalog`
- `service_records`
- `settings` (pricing, retention, backup)

Indexes:

- `idx_print_jobs_timestamp`
- `idx_service_records_timestamp`
- `idx_service_records_service_id`

## `database/init_db.py`

Purpose:

- Initializes DB file from schema and migration logic

Run with:

```bash
python database/init_db.py
```

## 7. UI Modules

## `ui/main_window.py`

Purpose:

- Main shell with dashboard, print log, services, reports, settings
- Theme toggle and periodic refresh
- Daily backup trigger + retention notification

## `ui/dashboard.py`

Purpose:

- Renders top KPI cards (print counts, B&W/color pages, services, revenue)

## `ui/services_panel.py`

Purpose:

- Service catalog button grid and add-service dialog

## `ui/settings_panel.py`

Purpose:

- Pricing, retention, and backup configuration
- Manual retention and backup execution
- Mouse-wheel protection on numeric inputs

## `ui/reports_panel.py`

Purpose:

- Daily/weekly/monthly reporting
- A3/A4 print counters and revenue summaries

## `ui/theme.py`

Purpose:

- Light/Dark theme palette and global stylesheet

## Supporting UI utilities

- `ui/formatting.py`: stable currency formatting (`INR 0.00`)
- `ui/input_filters.py`: wheel-event blocking for billing fields
- `ui/resources.py`: packaged/development resource path resolution
- `ui/icons/*.svg`: scalable icon assets

## 8. Packaging

## `CyberCafeManager.spec`

Purpose:

- PyInstaller spec for standalone Windows EXE
- Bundles `database/schema.sql`, `config/settings.json`, and `ui/icons/*.svg`

Build command:

```bash
pyinstaller CyberCafeManager.spec
```

## 9. Logging and Diagnostics

Log file:

- `logs/application.log`

Covers:

- printer detection and captured jobs
- database writes
- API request/response timing
- retention/backup actions
- errors and exceptions

Enable debug mode:

```powershell
$env:MANANI_LOG_LEVEL = "DEBUG"
python main.py
```

## 10. Safe Extension Guidelines

When adding features:

1. Preserve existing endpoint contracts where possible.
2. Add migration-safe schema updates in `Database._migrate_schema()`.
3. Keep money math in `Decimal`.
4. Keep UI billing controls protected from accidental wheel input.
5. Validate with:

```bash
python database/init_db.py
python main.py
```
