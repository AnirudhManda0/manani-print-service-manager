# Installation Guide - ManAni Print & Service Manager

This guide is for technicians and shop owners to install, configure, and validate ManAni Print & Service Manager.

Important build rule:

- Final Windows 7 production EXEs must be built with Python 3.9.
- Builds created with newer Python versions should be treated as local testing builds only.

## 1. Requirements

- Windows machine with printer drivers installed
- Python 3.9 (for source deployment) or packaged EXE (for operator deployment)
- Network only required for multi-PC client/server mode

## 2. Source Installation

1. Copy or clone project:

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

4. Start app:

```bash
python main.py
```

## 3. EXE Installation

1. Build executables:

```bash
pyinstaller --onefile --name CyberCafeManager main.py
pyinstaller CyberCafeServer.spec
pyinstaller CyberCafeClient.spec
```

2. Copy `dist/CyberCafeServer.exe` to admin PC.
3. Copy `dist/CyberCafeClient.exe` to each client PC.
4. Run executable directly.

Optional: generate direct deployment ZIPs:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release_packages.ps1
```

This creates:

- `release/CyberCafeServer.zip`
- `release/CyberCafeClient.zip`

Each ZIP can be copied to the target machine, extracted, and run without Python installation.

The app creates runtime folders/files automatically if missing:

- `config/settings.json`
- `database/schema.sql`
- `database/cybercafe.db`
- `logs/application.log`
- `version.txt`

## 4. First-Time Configuration

Open **Settings** and configure:

- Server IP
- Server Port
- Auto discover server
- Discovery port
- Computer Name
- Operator ID
- Polling interval
- B&W price per page
- Color price per page
- Currency code
- Retention mode/days
- Daily backup enabled/disabled
- Backup folder path

Then open **Services** and add required service buttons.

## 5. Printer Configuration

1. Install printer driver and verify printer in `Devices and Printers`.
2. Ensure Windows `Print Spooler` is running.
3. Print a test page/document.
4. Verify entry appears in Print Log with:
   - printer name
   - document name
   - page count
   - print type
   - paper size

Virtual printers (for example Microsoft Print to PDF) are also polled by the monitor.

## 6. Multi-PC Deployment

### Central Server PC

```bash
python main.py --mode server --config config/settings.json
```

(or headless)

```bash
python main.py --mode server --headless --config config/settings.json
```

### Client PCs

```bash
python main.py --mode client --config config/settings.json
```

or:

```bash
python client/run_client.py --config config/settings.json
```

Validate that print jobs from client PCs appear on the server dashboard/log.

If `auto_discovery_enabled` is on, clients can find the admin server automatically on the local network instead of depending only on a hardcoded IP.

Concurrency safety:

- Multiple Windows 10 client PCs can submit print jobs at the same time.
- The server uses SQLite WAL mode + thread lock + idempotent `source_job_key` ingestion.
- Retries or network race conditions will not create duplicate print rows.

## 7. Backup and Recovery

- Main DB: `database/cybercafe.db`
- Automatic daily backup: `backup/cybercafe_YYYY_MM_DD.db` (or configured folder)
- Manual backup: Settings -> `Run Backup Now`

Restore process:

1. Stop application.
2. Replace `database/cybercafe.db` with a selected backup file copy.
3. Start application.

## 8. Safe Update Procedure

1. Stop server/client applications.
2. Run backup or copy `database/cybercafe.db`.
3. Replace executable with newer version.
4. Keep existing `config/settings.json` and `database/` files.
5. Start the application.

## 9. Post-Install Validation Checklist

- [ ] App starts without crash
- [ ] Dashboard loads
- [ ] Settings save successfully
- [ ] Numeric fields do not change by mouse-wheel scroll
- [ ] Service record can be added from UI
- [ ] Test print appears in print log with correct page count
- [ ] Simultaneous print from 2 PCs appears as two separate transactions (no duplicates)
- [ ] Client auto-discovers the server when fixed server URL is not manually entered
- [ ] Dashboard revenue reflects printed pages (for example 18 pages x 2 INR = 36 INR)
- [ ] Report shows B&W/Color and A3/A4 values
- [ ] Add Service expression input works (for example `10 * 2` stores `20`)
- [ ] Daily backup file is created
- [ ] `logs/application.log` is being written

## 10. Diagnostics and Support

- Set debug logs when troubleshooting:

```powershell
$env:MANANI_LOG_LEVEL = "DEBUG"
python main.py
```

- Check common files:
  - `logs/application.log`
  - `config/settings.json`
  - `database/cybercafe.db`

- If API port conflict occurs (`8787`), close duplicate app instance or change configured port.
