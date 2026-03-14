# ManAni Print & Service Manager

ManAni Print & Service Manager is a Windows desktop application for cyber cafes and print shops to manage print billing, service transactions, and revenue reporting from one interface.

The system is designed to work in real shop environments with offline-first operation and simple workflows for non-technical operators.

## Project Overview

The software helps shops:

- Automatically capture print jobs from Windows printers.
- Calculate black-and-white and color print costs.
- Record manual services (PAN card, Aadhaar support, exam registrations, scanning, lamination, photo printing, etc.).
- Generate daily, weekly, and monthly reports.
- Run fully offline using SQLite.
- Operate in single-PC mode or centralized multi-PC mode.

## Key Features

- Automatic print detection via Windows print spooler (`pywin32`)
- B&W and color price-per-page configuration
- Service catalog and one-click service recording
- Dashboard with totals and revenue metrics
- Print log and calendar-based reporting
- Retention options for old records (retain/archive/delete)
- Light/Dark theme POS-style operator interface

## Architecture Overview

Data flow:

`Print Monitor -> API Server -> SQLite Database -> UI Dashboard`

### Main Components

- `client/print_monitor.py`
  - Detects print jobs from spooler and submits records to API.
- `server/api.py`
  - HTTP endpoints for jobs, settings, services, dashboard, reports, retention actions.
- `server/database.py`
  - Thread-safe SQLite operations, pricing logic, report aggregation.
- `ui/*`
  - Desktop UI for dashboard, services, settings, reports, and print logs.

## Repository Structure

```text
manani-print-manager/
  client/
  server/
  ui/
  database/
  config/
  docs/
  main.py
  requirements.txt
  README.md
  DEVELOPER_GUIDE.md
  INSTALLATION_GUIDE.md
  LICENSE
  .gitignore
  CyberCafeManager.spec
```

## Installation Guide (Developer/Technician)

### 1. Install Python

- Install Python on Windows and ensure it is added to `PATH`.
- Recommended: use the same Python version family across deployment systems.

### 2. Clone repository

```bash
git clone https://github.com/AnirudhManda0/manani-print-service-manager.git
cd manani-print-service-manager
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Initialize database

```bash
python database/init_db.py
```

### 5. Run application

```bash
python main.py
```

## Running Modes

### Single Computer Mode

Runs API + print monitor + UI on one PC.

```bash
python main.py --mode single
```

### Server Mode (Centralized)

Runs API and optional UI on central machine.

```bash
python main.py --mode server
python main.py --mode server --headless
```

### Client Monitor Mode

Runs lightweight print monitor on client PCs and sends jobs to central server.

```bash
python main.py --mode client --server-url http://<SERVER_IP>:8787
```

or:

```bash
python client/run_client.py --server-url http://<SERVER_IP>:8787
```

## Printer Setup Guide

1. Install printer drivers on each machine.
2. Confirm printers appear in **Control Panel > Devices and Printers**.
3. Ensure **Print Spooler** service is running (`services.msc`).
4. Print a test document.
5. Verify a new record appears in **Print Log**.

### Print Detection Workflow

`Windows Printer -> Print Spooler -> print_monitor.py -> API -> SQLite -> Dashboard/Reports`

Captured fields:

- printer name
- document name
- page count
- timestamp
- print type (B&W or color when detectable)

## Deployment Guide

### Build executable

```bash
pyinstaller CyberCafeManager.spec
```

Output:

- `dist/CyberCafeManager.exe`

### Share software with another PC

1. Copy executable (or full project folder) to target system.
2. Ensure printer drivers are installed on target machine.
3. Run application.
4. Configure print prices and services.
5. Print a sample document and verify detection/logging.

## Multi-PC Deployment (Cyber Cafe)

1. Set one machine as central server (`--mode server`).
2. Keep database on server machine.
3. Configure client machines to run monitor mode with server URL.
4. Verify all client print jobs appear on server dashboard/reporting screens.

## Database Structure

Main tables:

- `print_jobs`
- `services_catalog`
- `service_records`
- `settings`

Schema file: `database/schema.sql`

## Troubleshooting

### Printer not detected

- Check printer drivers.
- Confirm print spooler is running.
- Confirm monitor mode is enabled and API is reachable.

### Database locked

- Close duplicate app instances.
- Avoid external DB editors while app is active.
- Restart app after ensuring only one server writes to DB.

### Application startup errors

- Reinstall dependencies.
- Validate `config/settings.json`.
- Reinitialize DB with `python database/init_db.py`.

## Documentation

- Developer internals: `DEVELOPER_GUIDE.md`
- Installation/sharing guide: `INSTALLATION_GUIDE.md`
- Operator manual: `docs/CyberCafeManager_Documentation.docx`

## License

This project is licensed under the MIT License. See `LICENSE`.
