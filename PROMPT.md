# PrintX Project Memory

This file is the working memory for PrintX so future debugging and upgrades start with the right context.

## Product Identity

- Product name: PrintX
- Subtitle: Print and Service Manager
- Current version: 2.0.0
- Workspace: C:\Users\Manda Anirudh\Documents\manani-print-manager
- GitHub repo: AnirudhManda0/manani-print-service-manager
- Target users: cyber cafe / print shop operators

## Product Goal

PrintX is a Windows-only cyber cafe print and service management system with:

- Windows 10+ production release
- Windows 7 legacy release
- automatic Windows spooler print tracking
- B&W and color billing
- service billing and service catalog management
- SQLite persistence
- background tray monitoring
- auto-start support
- offline-first operation with no internet requirement

## Runtime Roles

- single: UI + API + print monitor on one PC
- server: central admin server and dashboard
- client: monitor-only client sending jobs to the server over LAN

## Important Source Files

- main.py: runtime orchestrator for API, UI, print monitor, tray mode, and instance bridge
- branding.py: app name, executable names, database names, icon/logo paths
- autostart.py: Registry and Startup-folder shortcut management
- runtime_config.py: settings.json load/validate/save/fallback logic
- network_discovery.py: UDP server discovery on LAN
- instance_bridge.py: single-instance control so relaunch opens the existing UI
- client/print_monitor.py: Windows spooler monitor using pywin32
- server/api.py: FastAPI routes for dashboard, print jobs, services, reports, settings
- server/database.py: SQLite schema/migrations, billing, reports, backup, retention
- ui/main_window.py: desktop shell, dashboard, print log, tabs, tray behavior
- ui/services_panel.py: service action buttons, add/delete service flow
- ui/catalog_panel.py: service catalog and recent service records
- ui/reports_panel.py: reports and charts
- ui/settings_panel.py: configuration editor
- ui/qt.py: Qt compatibility shim for PySide2/PySide6

## Release Rules

- Windows 10+ build uses PrintX.spec and outputs releases/windows10/PrintX.exe
- Windows 7 build uses PrintX_Win7.spec and outputs releases/windows7/PrintX_Win7.exe
- Windows 7 build must use Python 3.8 to avoid api-ms-win-core-path-l1-1-0.dll issues
- Keep release folders neat: only releases/windows10 and releases/windows7 should be used
- Runtime folders inside release directories (config, database, logs, backup) are local generated data and should not be committed

## Configuration

Primary config file: config/settings.json

Important keys:

- mode: single/server/client
- server_ip and server_port
- auto_discovery_enabled and discovery_port
- computer_name
- operator_id
- autostart_enabled
- poll_interval
- bw_price_per_page
- color_price_per_page
- database_path
- print_monitor_enabled

Config corruption must be handled by quarantine and fallback defaults.

## Print Detection Decisions

- PrintX enumerates all printers with win32print.EnumPrinters.
- Each printer queue is polled with win32print.EnumJobs.
- Page count is resolved by waiting for TotalPages or PagesPrinted before recording.
- source_job_key prevents duplicate billing across retries and multiple clients.
- Color/B&W detection uses job DEVMODE first, job color properties next, then printer capability fallback.
- Printer default DEVMODE color is not reliable per job; it may describe hardware/defaults, not the current print choice.
- Virtual printers such as Microsoft Print to PDF can report grayscale jobs as color because the virtual driver receives rendered document data, not physical toner mode.
- If spooler data is ambiguous, bill conservatively and allow operator correction from the Print Log.

## UI Decisions

- Dashboard should show only KPI cards.
- Heavy charts belong in Reports.
- Print Log includes correction flow: double-click Print Type to switch B&W/color and recalculate billing.
- Services tab is for quick service actions.
- Catalog tab is for service catalog and recent service records.
- Closing the window hides to tray; monitoring continues.
- Exit Completely is the explicit shutdown path.

## Service Billing Decisions

- Add Service supports safe arithmetic expressions through AST parsing.
- Service action buttons require confirmation before recording.
- Services with existing records should not be deleted, to preserve history.
- Service catalog and service records are separate database concepts.

## Build Commands

Windows 10+:

```powershell
python -m PyInstaller PrintX.spec
powershell -ExecutionPolicy Bypass -File .\build_release_packages.ps1 -Target windows10
```

Windows 7 legacy:

```powershell
py -3.8 -m PyInstaller PrintX_Win7.spec
```

## Testing Focus

Before shop deployment test:

- 1, 5, 50, 100 page print jobs
- B&W billing and color billing
- real USB printer and TCP/IP printer behavior
- dashboard totals
- print log delete and print-type correction
- service add, delete, record, and catalog/history views
- reports daily/weekly/monthly
- close-to-tray and reopen existing instance
- auto-start from Settings
- missing/corrupt config and database recovery

## Known Field Issues

- Windows 7 api-ms-win-core-path-l1-1-0.dll means the EXE was built with a modern Python runtime; rebuild with Python 3.8.
- Microsoft Print to PDF may not be a reliable B&W/color validation device.
- If color classification is wrong, check logs/printx.log for print_type_source and spooler DEVMODE fields.
