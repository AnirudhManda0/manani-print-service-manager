# ManAni Print & Service Manager

ManAni Print & Service Manager is an offline-first Windows desktop POS-style application for cyber cafes and print shops.
It captures print jobs automatically, records manual services, calculates billing, and produces revenue reports.

## Core Capabilities

- Automatic print capture from Windows Print Spooler (`win32print.EnumPrinters`, `EnumJobs`, `GetJob`)
- Color/B&W detection with fallback handling
- Paper-size detection (`A4`, `A3`, `Letter`, `Unknown`)
- Decimal-based price calculations for fractional pricing (for example `0.50` per page)
- Service catalog with one-click service recording
- Dashboard + print log + daily/weekly/monthly reports
- Data retention controls (retain, archive, delete)
- Daily automatic SQLite backup to `backup/cybercafe_YYYY_MM_DD.db`
- Light/Dark operator-friendly UI theme
- Single-PC mode and centralized multi-PC mode

## Architecture

Data flow:

`Printer -> Windows Spooler -> client/print_monitor.py -> server/api.py -> server/database.py -> SQLite -> UI`

Key modules:

- `client/print_monitor.py`: spooler polling and job metadata extraction
- `server/api.py`: FastAPI endpoints, request logging, backup trigger checks
- `server/database.py`: thread-safe SQLite operations, Decimal billing, reports, archiving, backup
- `ui/*`: POS desktop interface (dashboard, services, settings, reports)

## Project Structure

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
  INSTALLATION_GUIDE.md
  DEVELOPER_GUIDE.md
  LICENSE
  .gitignore
  CyberCafeManager.spec
```

## Installation (Source)

1. Install Python and add it to PATH.
2. Clone repository:

```bash
git clone https://github.com/AnirudhManda0/manani-print-service-manager.git
cd manani-print-service-manager
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Initialize database:

```bash
python database/init_db.py
```

5. Run app:

```bash
python main.py
```

## Runtime Modes

### Single PC

```bash
python main.py --mode single
```

### Central Server

```bash
python main.py --mode server
python main.py --mode server --headless
```

### Client Monitor (Remote PCs)

```bash
python main.py --mode client --server-url http://<SERVER_IP>:8787
```

or

```bash
python client/run_client.py --server-url http://<SERVER_IP>:8787 --poll-interval 0.5
```

## Printer Setup

1. Install printer drivers.
2. Confirm printers appear in `Devices and Printers`.
3. Ensure `Print Spooler` service is running (`services.msc`).
4. Print a test document.
5. Verify log entry in Print Log tab with:
   - printer name
   - document name
   - pages
   - print type
   - paper size
   - timestamp

## Settings and Billing

In **Settings**:

- Configure B&W and color price per page (supports fractional values)
- Configure currency code (displayed as `INR 0.00` style)
- Configure retention mode and days
- Configure daily backup enable/disable and backup folder
- Run retention/backup manually when needed

Historical records keep original `price_per_page` and `total_cost`.

## Backup and Data Safety

- SQLite WAL mode is enabled for stability.
- Daily backup is generated automatically when enabled.
- Manual backup can be triggered from Settings.
- Main DB: `database/cybercafe.db`
- Backup files: `backup/cybercafe_YYYY_MM_DD.db`

## Build Standalone EXE

```bash
pyinstaller CyberCafeManager.spec
```

Output:

- `dist/CyberCafeManager.exe`

## Basic Verification Procedure

1. Start app (`python main.py`).
2. Add service and record it once.
3. Print test document.
4. Confirm dashboard and report values update.
5. Confirm backup file appears in configured backup folder.

## Troubleshooting

### Printer not detected

- Recheck printer driver and spooler service.
- Verify monitor mode is running.
- Enable debug logs using `MANANI_LOG_LEVEL=DEBUG`.

### Port already in use

- Another app instance is likely running on API port `8787`.
- Close duplicate instance or change API port in `config/settings.json`.

### Database busy/locked

- Avoid editing DB in external tools during runtime.
- Keep one server writer in centralized mode.

## Documentation

- Setup and operator deployment: `INSTALLATION_GUIDE.md`
- Internal architecture: `DEVELOPER_GUIDE.md`
- Operator manual: `docs/CyberCafeManager_Documentation.docx`

## License

MIT License (`LICENSE`).
