![PrintX logo](assets/logo.png)

# PrintX

PrintX is a production-focused cyber cafe print and service management system for Windows desktops.
It combines:

- real-time Windows spooler monitoring
- accurate print billing for B&W and color jobs
- service logging and revenue tracking
- FastAPI + SQLite local server mode
- background monitoring with system tray behavior
- Windows auto-start support by registry and Startup-folder shortcut

## Release Targets

- `main`: Windows 10 and above, packaged as `PrintX.exe`
- `windows7-legacy`: Windows 7 compatibility lane, packaged as `PrintX_Win7.exe`

Important:
- the Windows 10 release can be built from this repo on the current modern toolchain
- the Windows 7 release must be built in a Python 3.8 legacy environment to avoid `api-ms-win-core-path-l1-1-0.dll` and related runtime issues

## Key Features

- Detects all installed printers through `win32print.EnumPrinters`
- Polls each queue through `win32print.EnumJobs`
- Classifies `color` vs `black_and_white` from spooler DEVMODE and printer capability fallbacks
- Avoids duplicate print entries with spooler job tracking and server-side idempotency
- Calculates print cost separately for B&W and color
- Records services with confirmation prompts
- Keeps the dashboard focused on KPI cards and moves charts into Reports
- Backs up the SQLite database daily
- Recreates missing settings safely and quarantines corrupted config/database files when possible

## Default Runtime Modes

- `single`: UI + API + monitor on one PC
- `server`: central server mode
- `client`: background print monitor only

## Quick Start

1. Install Python dependencies for the target release lane.
2. Run `python database/init_db.py`
3. Start the app with `python main.py`
4. Open Settings and confirm:
   - server IP / port
   - printer pricing
   - operator ID
   - auto-start preference

## Build Commands

Windows 10 build:

```powershell
python -m PyInstaller PrintX.spec
powershell -ExecutionPolicy Bypass -File .\build_release_packages.ps1 -Target windows10
```

Windows 7 legacy build:

```powershell
python -m PyInstaller PrintX_Win7.spec
powershell -ExecutionPolicy Bypass -File .\build_release_packages.ps1 -Target windows7
```

## Release Layout

- `releases/windows10/PrintX.exe`
- `releases/windows7/PrintX_Win7.exe`

## Documentation

- [Project Structure](docs/PROJECT_STRUCTURE.md)
- [Installation](docs/INSTALLATION.md)
- [User Guide](docs/USER_GUIDE.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Testing](docs/TESTING.md)

## Environment Variables

- `PRINTX_LOG_LEVEL`
- `PRINTX_SERVER_URL`
- `PRINTX_OPERATOR_ID`

## Notes

- Closing the main window sends PrintX to the system tray instead of stopping monitoring.
- Auto-start writes both a `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` entry and a Startup-folder shortcut on Windows.
- Packaged runtime logs are written to `logs/printx.log`.
- If `assets/logo.png` or `assets/app_icon.ico` is missing, the app still runs with fallback UI icons.
