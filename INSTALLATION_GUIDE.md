# Installation Guide - ManAni Print & Service Manager

This guide explains how to distribute, install, and verify ManAni Print & Service Manager on a new computer.

## 1. Distribution Options

You can share the software in two common ways:

1. Source folder distribution (for technical setups)
2. EXE distribution (for operator-friendly setup)

## 2. Prerequisites

- Windows computer (printer-connected environment)
- Printer drivers installed
- Network access only needed for multi-PC server/client communication (not for cloud)

For source mode:

- Python installed and available in `PATH`

## 3. Installation from Source

### Step 1 - Copy project folder

Copy the full `manani-print-manager` folder to the target computer.

### Step 2 - Install dependencies

Open terminal in project root:

```bash
pip install -r requirements.txt
```

### Step 3 - Initialize database

```bash
python database/init_db.py
```

### Step 4 - Start application

```bash
python main.py
```

## 4. Installation from Executable

### Step 1 - Build executable (on build machine)

```bash
pyinstaller CyberCafeManager.spec
```

### Step 2 - Copy executable

Copy `dist/CyberCafeManager.exe` to target machine (USB/network share).

### Step 3 - Run executable

Double-click `CyberCafeManager.exe`.

The app will initialize required runtime files and database path automatically if missing.

## 5. Initial Configuration After Installation

1. Open **Settings** tab.
2. Set:
   - B&W price per page
   - Color price per page
   - Currency
3. Configure data retention mode if needed.
4. Open **Services** tab and add required services.
5. Print a sample document and verify it appears in Print Log.

## 6. Printer Connection Verification

1. Install printer driver.
2. Check printer appears in **Devices and Printers**.
3. Ensure **Print Spooler** service is running.
4. Print a test page.
5. Verify print record appears in app.

## 7. Immediate Post-Install Validation Checklist

- [ ] App launches without errors.
- [ ] Dashboard loads.
- [ ] Settings panel saves values.
- [ ] Database file exists in `database/`.
- [ ] Test print appears in print log.
- [ ] Service button click creates service record.
- [ ] Report shows expected totals.

## 8. Multi-PC Setup (Centralized Cafe)

### Server machine

```bash
python main.py --mode server
```

### Client machines

```bash
python main.py --mode client --server-url http://<SERVER_IP>:8787
```

or:

```bash
python client/run_client.py --server-url http://<SERVER_IP>:8787
```

Confirm print events from client PCs appear in server dashboard/logs.

## 9. Sharing Notes

- You can share by USB, LAN share, or repository clone.
- Keep backup copies of:
  - `database/cybercafe.db`
  - `config/settings.json`

## 10. Common Startup Checks

If startup fails:

1. Run `pip install -r requirements.txt` again.
2. Run `python database/init_db.py`.
3. Check `config/settings.json` syntax.
4. Verify no other process is occupying API port (default `8787`).
