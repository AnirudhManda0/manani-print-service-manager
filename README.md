# ManAni Print & Service Manager

ManAni Print & Service Manager is a Windows desktop application for cyber cafes and print shops.
It combines print-job capture, service billing, reporting, and backup into one offline-capable workflow.

## Required Software and Dependencies

Install the following on a development machine:

- Python 3.9 (recommended for Windows 7 and Windows 10 compatibility)
- Git
- PyInstaller
- Printer drivers for the printers used in the shop

Required Python libraries (installed through `requirements.txt`):

- PySide2
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

## Production Roles

Admin Server (Windows 7/10):

- Runs FastAPI + SQLite storage
- Shows dashboard, reports, settings, and print log
- Stores all transactions centrally
- Can also monitor local print jobs

Client Monitor (Windows 10):

- Detects print jobs from local USB/TCP-IP printers
- Sends print transactions to admin server via HTTP
- Does not keep permanent transaction data

## Configuration File

Runtime settings are stored in `config/settings.json`.

Example:

```json
{
  "mode": "single",
  "server_ip": "192.168.1.50",
  "server_port": 8787,
  "computer_name": "CLIENT-PC-01",
  "operator_id": "ADMIN",
  "poll_interval": 0.5,
  "bw_price_per_page": 2.0,
  "color_price_per_page": 10.0,
  "database_path": "database/cybercafe.db",
  "print_monitor_enabled": true
}
```

Settings can be edited from the UI Settings panel. Changes are saved back to `config/settings.json`.

## Build Instructions

Generate portable EXE:

```bash
pyinstaller --onefile --name CyberCafeManager main.py
```

or use the project spec:

```bash
pyinstaller CyberCafeManager.spec
```

Generate dedicated server and client executables:

```bash
pyinstaller CyberCafeServer.spec
pyinstaller CyberCafeClient.spec
```

Build output:

- `dist/CyberCafeManager.exe`
- `dist/CyberCafeServer.exe`
- `dist/CyberCafeClient.exe`

This EXE is packaged with Python runtime and dependencies, so it can run without a Python installation.

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
- or `dist/CyberCafeServer.exe` and `dist/CyberCafeClient.exe` for split deployment

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
- Operator ID tagging for print transactions
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

Spooler detection test (all printers):

1. Open terminal in project root.
2. Run:

```bash
python test_spooler_detection.py
```

3. Confirm your USB and network printers appear in the "Detected printers" list.
4. Print a small test page (Notepad is enough) to each printer one by one.
5. Check console output for:

- `New print job detected`
- `printer_name`
- `document_name`
- `total_pages`
- `submission_time`
- `user_name`
- page count greater than zero before job is recorded

Tip: Keep `MANANI_LOG_LEVEL=DEBUG` to see queue polling diagnostics (`Detected printer`, `Checking queue`, `Pages detected`, `Job recorded`).

## End-to-End Test

1. Start application (`python main.py` or executable).
2. Print a test document (for example 18-page PDF).
3. Verify Print Log shows correct `pages` value (not 0).
4. Verify Dashboard updates `Total Prints Today`, `B&W Pages`/`Color Pages`, and `Total Revenue`.
5. Verify Delete button removes selected print transaction.
6. Open Services -> Add Service, enter expressions like `10 * 2`, and verify calculated value is saved as `20`.

## Update-Safe Process

1. Stop running application.
2. Trigger/verify backup (Settings -> Run Backup Now), or copy `database/cybercafe.db`.
3. Replace executable (`CyberCafeServer.exe` / `CyberCafeClient.exe`).
4. Keep existing `database/` and `config/` folders unchanged.
5. Start application again.

Daily backup files are written to `backup/` (configurable in Settings).

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
