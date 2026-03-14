# CyberCafe Print & Service Manager

CyberCafe Print & Service Manager is a desktop application for cyber cafes and print shops to automatically track print jobs, record manual services, and generate revenue reports.

It is designed for practical shop use with a simple operator UI, offline-first data storage, and support for both single-PC and centralized multi-PC deployments.

## Project Description

This software helps shop operators:

- Automatically detect print activity from Windows printers.
- Price black-and-white and color prints using configurable rates.
- Record manual services such as PAN card support, Aadhaar updates, online exam registrations, scanning, lamination, and photo printing.
- View daily, weekly, and monthly operational and revenue reports.
- Run fully offline with local SQLite storage.

## Key Features

- Automatic print detection via Windows spooler (`pywin32`)
- Black and white and color page pricing
- Manual service tracking and service catalog management
- Daily, weekly, and monthly reporting
- Offline SQLite database
- Single-PC and multi-PC centralized deployment
- Theme-ready POS-style desktop UI (Light/Dark modes)

## Architecture Overview

System data flow:

`Print Monitor -> API Server -> SQLite Database -> UI Dashboard`

### Module Responsibilities

- `client/print_monitor.py`
  - Polls the Windows print spooler and sends print job records to the API.
- `server/api.py`
  - Exposes HTTP endpoints for settings, print jobs, services, dashboard, and reports.
- `server/database.py`
  - Handles all SQLite operations, cost calculations, and report aggregation logic.
- `ui/*`
  - Operator desktop interface for dashboard, print log, services, settings, and reports.

## Project Structure

```text
project_root/
  client/
  server/
  ui/
  database/
  config/
  docs/
  tests/
  main.py
  requirements.txt
  CyberCafeManager.spec
  DEVELOPER_GUIDE.md
  LICENSE
  README.md
  .gitignore
```

## Installation Guide

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Initialize the database

```bash
python database/init_db.py
```

### 3) Start the application

```bash
python main.py
```

## Running Modes

### Single Computer Mode

Runs monitor + API + UI on one machine.

```bash
python main.py --mode single
```

### Server Mode

Runs central API/dashboard server (optionally headless).

```bash
python main.py --mode server
python main.py --mode server --headless
```

### Client Monitor Mode

Runs print monitor client that forwards print jobs to central server.

```bash
python main.py --mode client --server-url http://<SERVER_IP>:8787
# or
python client/run_client.py --server-url http://<SERVER_IP>:8787
```

## Printer Setup (Windows)

1. Install printer drivers from manufacturer.
2. Confirm printers appear in **Devices and Printers**.
3. Ensure **Print Spooler** service is running (`services.msc`).
4. Print a test page.
5. Verify print entry appears in the app's Print Log.

## Database Structure

Main SQLite tables:

- `print_jobs`
  - Stores detected print jobs including pages, print type, and computed cost.
- `services_catalog`
  - Stores available service types and default prices.
- `service_records`
  - Stores each performed service transaction.
- `settings`
  - Stores pricing, currency, and retention settings.

Schema source: `database/schema.sql`

## Build Executable (PyInstaller)

```bash
pyinstaller CyberCafeManager.spec
```

Output binary:

- `dist/CyberCafeManager.exe`

## Troubleshooting

### Printer not detected

- Verify printer driver installation.
- Confirm Windows Print Spooler is running.
- Confirm monitor is enabled in `config/settings.json`.

### Database locked

- Close duplicate app instances.
- Avoid opening the database from external tools during active writes.
- Restart the application and retry.

### Application startup errors

- Verify dependencies installed: `pip install -r requirements.txt`
- Reinitialize DB: `python database/init_db.py`
- Check `config/settings.json` syntax/values.

## Future Development Workflow

Use this update workflow for all future changes:

1. Modify code.
2. Run validation/tests.
3. Commit with meaningful message.
4. Push to remote.

Commands:

```bash
git add .
git commit -m "Describe feature or fix"
git push
```

Use clear commit messages (for example: `Fix print cost rounding`, `Add retention status API`, `Improve dark mode contrast`).
