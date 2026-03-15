# Installation Guide - ManAni Print & Service Manager

This guide is for technicians and shop owners to install, configure, and validate ManAni Print & Service Manager.

## 1. Requirements

- Windows machine with printer drivers installed
- Python (for source deployment) or packaged EXE (for operator deployment)
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

1. Build executable:

```bash
pyinstaller CyberCafeManager.spec
```

2. Copy `dist/CyberCafeManager.exe` to target PC.
3. Run executable directly.

The app creates runtime folders/files automatically if missing:

- `config/settings.json`
- `database/schema.sql`
- `database/cybercafe.db`
- `logs/application.log`

## 4. First-Time Configuration

Open **Settings** and configure:

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
python main.py --mode server
```

(or headless)

```bash
python main.py --mode server --headless
```

### Client PCs

```bash
python main.py --mode client --server-url http://<SERVER_IP>:8787
```

or:

```bash
python client/run_client.py --server-url http://<SERVER_IP>:8787 --poll-interval 0.5
```

Validate that print jobs from client PCs appear on the server dashboard/log.

## 7. Backup and Recovery

- Main DB: `database/cybercafe.db`
- Automatic daily backup: `backup/cybercafe_YYYY_MM_DD.db` (or configured folder)
- Manual backup: Settings -> `Run Backup Now`

Restore process:

1. Stop application.
2. Replace `database/cybercafe.db` with a selected backup file copy.
3. Start application.

## 8. Post-Install Validation Checklist

- [ ] App starts without crash
- [ ] Dashboard loads
- [ ] Settings save successfully
- [ ] Numeric fields do not change by mouse-wheel scroll
- [ ] Service record can be added from UI
- [ ] Test print appears in print log
- [ ] Report shows B&W/Color and A3/A4 values
- [ ] Daily backup file is created
- [ ] `logs/application.log` is being written

## 9. Diagnostics and Support

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
