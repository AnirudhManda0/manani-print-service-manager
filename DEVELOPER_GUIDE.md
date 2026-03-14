# Developer Guide

This document explains the internal architecture of **CyberCafe Print & Service Manager** so new developers can quickly understand, maintain, and extend the project.

## 1. High-Level Architecture

The application is divided into five layers:

1. `client` - Print monitoring and client forwarding logic
2. `server` - API endpoints and data/business logic
3. `database` - SQLite schema and initialization scripts
4. `ui` - Desktop operator interface (PySide6)
5. `config` - Runtime configuration

Runtime flow:

`Windows Print Spooler -> client/print_monitor.py -> server/api.py -> server/database.py -> SQLite -> ui/*`

## 2. File-by-File Overview

### `main.py`

**Purpose**
- Main application entrypoint.
- Boots the system in `single`, `server`, or `client` mode.
- Handles packaged-runtime resource resolution for PyInstaller builds.

**Why it exists**
- Centralizes startup concerns (config loading, API server lifecycle, UI startup, monitor startup).

**Interactions**
- Imports `create_app` from `server/api.py`
- Imports `PrintMonitor` from `client/print_monitor.py`
- Imports UI classes through `ui/api_client.py` and `ui/main_window.py`

**Important functions**
- `resource_path(relative_path) -> str`
  - Returns resource file path in dev mode or bundled EXE mode.
- `ensure_runtime_files() -> None`
  - Ensures `config/settings.json` and `database/schema.sql` are available at runtime.
- `load_config(config_path: Optional[str]) -> Dict[str, Any]`
  - Loads JSON settings and returns configuration dictionary.
- `wait_for_api(base_url, retries, delay) -> bool`
  - Polls API health endpoint before UI/monitor interaction.
- `run_single_mode(config) -> None`
  - Runs API server + monitor + UI on one machine.
- `run_server_mode(config, with_ui=True) -> None`
  - Runs central API mode, optionally with UI.
- `run_client_mode(config, server_url=None) -> None`
  - Runs print monitor client that posts jobs to a central server.
- `main() -> None`
  - Parses args, selects runtime mode, and starts system.

---

### `client/print_monitor.py`

**Purpose**
- Detects print jobs from Windows spooler and dispatches them to API.

**Why it exists**
- Print capture is asynchronous and system-specific; this isolates Windows print integration.

**Interactions**
- Uses `win32print` and `win32con` from `pywin32`.
- Sends job payloads to `POST /api/print-jobs` via `requests`.

**Important components**
- `PrintMonitor` class
  - `start()`, `stop()`: lifecycle controls
  - `_list_printers()`: enumerates printers
  - `_scan_printer(printer_name)`: reads jobs for a printer
  - `_job_to_payload(...)`: normalizes job metadata to API payload
  - `_send_to_api(payload)`: retries and sends to API
- `run_background_client(server_url, poll_interval)`
  - Runs monitor loop in standalone client mode.

**Captured fields**
- `computer_name`, `printer_name`, `document_name`, `pages`, `print_type`, `timestamp`

---

### `server/api.py`

**Purpose**
- Defines HTTP API endpoints and request/response behavior.

**Why it exists**
- Separates transport concerns (HTTP, validation, error handling) from data logic.

**Interactions**
- Uses `Database` from `server/database.py`.
- Uses request models from `server/models.py`.

**Important endpoints**
- `GET /health`
- `GET/PUT /api/settings`
- `POST/GET /api/print-jobs`
- `GET/POST /api/services/catalog`
- `POST /api/services/record`
- `GET /api/dashboard`
- `GET /api/reports/{period}`
- `GET /api/data-retention/status`
- `POST /api/data-retention/execute`

---

### `server/database.py`

**Purpose**
- Owns all SQLite operations and business calculations.

**Why it exists**
- Keeps pricing/report logic consistent across UI and API usage.
- Provides thread-safe DB operations for concurrent UI/API/monitor activity.

**Interactions**
- Reads schema from `database/schema.sql`.
- Called by `server/api.py`.

**Important methods**
- `initialize()`
  - Applies schema and compatibility migrations.
- `get_settings()`, `update_settings(...)`
  - Reads/updates print pricing, currency, retention settings.
- `add_print_job(...) -> Dict`
  - Computes `price_per_page`, `total_cost` and inserts print job.
- `list_print_jobs(limit, date_filter) -> List[Dict]`
  - Returns recent logs (optionally day-filtered).
- `add_service_catalog(...)`, `list_services_catalog()`
  - Manages service types.
- `record_service(...)`
  - Inserts service transaction record.
- `_revenue_between(start_ts, end_ts) -> Dict`
  - Core aggregation (COUNT, SUM, AVG) for print/services metrics.
- `get_dashboard(day) -> Dict`
  - Daily dashboard summary.
- `get_report(period, day) -> Dict`
  - Daily/weekly/monthly summary + service breakdown.
- `get_retention_status(days) -> Dict`
  - Checks old-record counts before archive/delete actions.
- `archive_old_records(days, archive_db_path=None) -> Dict`
  - Moves old rows into archive DB.
- `delete_old_records(days) -> Dict`
  - Deletes old rows from primary DB.

---

### `server/models.py`

**Purpose**
- Pydantic request models for API validation.

**Why it exists**
- Prevents invalid payloads from reaching database layer.

**Interactions**
- Used by `server/api.py` endpoint function parameters.

**Key models**
- `PrintJobCreate`
- `ServiceCatalogCreate`
- `ServiceRecordCreate`
- `SettingsUpdate`
- `DataRetentionExecute`

---

### `ui/main_window.py`

**Purpose**
- Main desktop shell and navigation controller.

**Why it exists**
- Coordinates panel composition, refresh behavior, theme switching, and top-level user interactions.

**Interactions**
- Uses `APIClient` to fetch/store data.
- Embeds `DashboardPanel`, `ServicesPanel`, `ReportsPanel`, `SettingsPanel`.
- Uses `ThemeManager` from `ui/theme.py`.

**Important methods**
- `_build_print_log_tab()`
  - Builds print log table and date filter controls.
- `apply_theme()`, `toggle_theme()`
  - Global Light/Dark style switch.
- `refresh_all()`
  - Refreshes dashboard, log, and services state.
- `load_dashboard(day)`, `load_print_jobs(day)`
  - Reads API and updates UI widgets.
- `check_retention_notice()`
  - Prompts user when old data retention action is applicable.

---

### `ui/dashboard.py`

**Purpose**
- Dashboard KPI card widgets.

**Why it exists**
- Isolates visual summary components from main window.

**Interactions**
- Receives payload from `MainWindow.load_dashboard()`.

**Important classes**
- `StatCard`
- `DashboardPanel.update_metrics(payload)`

---

### `ui/services_panel.py`

**Purpose**
- Service catalog UI and service transaction recording.

**Why it exists**
- Manual service billing is a major non-print revenue workflow.

**Interactions**
- Uses `APIClient` for listing services, adding services, recording service usage.
- Emits `service_recorded` signal to refresh dashboard.

**Important components**
- `AddServiceDialog` (collects name and default price)
- `ServicesPanel.refresh_services()`
- `ServicesPanel.record_service(service)`

---

### `ui/settings_panel.py`

**Purpose**
- Update pricing, currency, and retention policy.

**Why it exists**
- Central operator control surface for financial and data lifecycle settings.

**Interactions**
- Reads/writes via `APIClient.get_settings() / update_settings()`
- Executes retention actions via `execute_retention()`

**Important methods**
- `load_settings()`
- `save_settings()`
- `run_retention()`

---

### `ui/reports_panel.py`

**Purpose**
- Calendar-based reporting UI for daily/weekly/monthly summaries.

**Why it exists**
- Gives operators and owners a quick financial/operational view.

**Interactions**
- Calls `APIClient.get_report(period, day)` and renders summary + breakdown.

**Important methods**
- `load_report()`
- `_render_report(report)`

---

## 3. API Client Layer

### `ui/api_client.py`

**Purpose**
- Thin wrapper around HTTP requests to backend API.

**Why it exists**
- Keeps widgets clean and reduces duplicate request code.

**Important methods**
- `get_dashboard`, `get_print_jobs`
- `get_settings`, `update_settings`
- `list_services`, `add_service`, `record_service`
- `get_report`
- `get_retention_status`, `execute_retention`

---

## 4. Database/Schema Files

### `database/schema.sql`

Defines:
- `print_jobs`
- `services_catalog`
- `service_records`
- `settings`

Also defines indexes for query performance and default settings seed values.

### `database/init_db.py`

Initializes database by instantiating `Database` class and applying schema/migrations.

---

## 5. Config and Packaging

### `config/settings.json`

Runtime configuration:
- mode
- API host/port
- database path
- print monitor behavior
- central server URL

### `CyberCafeManager.spec`

PyInstaller build specification:
- bundles `database/schema.sql`
- bundles `config/settings.json`
- sets hidden imports for Qt and pywin32 modules

---

## 6. Why This Design Works

- **Maintainability**: clear separation by runtime role (client/server/ui).
- **Reliability**: thread-safe DB layer and WAL mode for high write frequency.
- **Offline-first**: no cloud dependency required.
- **Deployable**: supports both source execution and bundled EXE runtime.
- **Extensible**: new reports/services/settings can be added with minimal impact across modules.
