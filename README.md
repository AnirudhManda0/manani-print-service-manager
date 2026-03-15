# ManAni Print & Service Manager

ManAni Print & Service Manager is a Windows desktop application for cyber cafes and print shops.
It combines print-job capture, service billing, reporting, and backup into one offline-capable workflow.

## Required Software and Dependencies

Install the following on a development machine:

- Python 3.10+
- Git
- PyInstaller
- Printer drivers for the printers used in the shop

Required Python libraries (installed through `requirements.txt`):

- PySide6
- FastAPI
- uvicorn
- requests
- pywin32
- pydantic

Install command:

```bash
pip install -r requirements.txt
```

## Development Setup

1. Clone repository:

```bash
git clone https://github.com/AnirudhManda0/manani-print-service-manager.git
cd manani-print-service-manager
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Initialize database:

```bash
python database/init_db.py
```

4. Run application:

```bash
python main.py
```

## Project Architecture

Data flow:

`Windows Printer -> Print Spooler -> client/print_monitor.py -> server/api.py -> server/database.py -> SQLite -> UI`

Main modules:

- `main.py`: runtime bootstrap, logging, mode selection, UI/API launch
- `client/print_monitor.py`: spooler polling and print metadata capture
- `server/api.py`: FastAPI routes for UI and monitor clients
- `server/database.py`: billing logic, reporting queries, retention, backups
- `ui/*`: operator interface (dashboard, services, settings, reports)

## Runtime Modes

Single computer mode:

```bash
python main.py --mode single
```

Central server mode:

```bash
python main.py --mode server
python main.py --mode server --headless
```

Client monitor mode:

```bash
python main.py --mode client --server-url http://<SERVER_IP>:8787
```

or:

```bash
python client/run_client.py --server-url http://<SERVER_IP>:8787 --poll-interval 0.5
```

## Build Instructions

Generate portable EXE:

```bash
pyinstaller CyberCafeManager.spec
```

Build output:

- `dist/CyberCafeManager.exe`

This EXE is packaged with Python runtime and dependencies, so it can run on Windows 10/11 systems even when Python is not installed.

## Portable Distribution

Portable file to distribute:

- `dist/CyberCafeManager.exe`

At first launch, the EXE auto-creates runtime folders next to itself:

- `config/`
- `database/`
- `logs/`
- `backup/`

## How to Share the Software

Share this file:

- `dist/CyberCafeManager.exe`

Recommended sharing methods:

- USB drive
- Google Drive
- GitHub release
- Email attachment

Example portable folder structure:

```text
CyberCafeManager/
  CyberCafeManager.exe
```

End users only need to double-click `CyberCafeManager.exe`.

## Features

- Automatic print capture using Windows spooler APIs
- B&W and color billing with Decimal precision
- Paper-size capture (`A4`, `A3`, `Letter`, `Unknown`)
- Service catalog and one-click service recording
- Daily/weekly/monthly reports
- Data retention actions (retain/archive/delete)
- Daily automatic SQLite backup
- Light/Dark desktop UI theme

## Troubleshooting

Printer not detected:

- Verify printer driver installation.
- Verify Print Spooler service is running.
- Verify monitor mode is active and API is reachable.

Port already in use:

- Close existing running app instance or change port in `config/settings.json`.

Database busy/locked:

- Avoid editing DB externally while app is running.
- Keep one central writer in multi-PC mode.

Enable debug logs:

```powershell
$env:MANANI_LOG_LEVEL = "DEBUG"
python main.py
```

## License

MIT License (`LICENSE`).
