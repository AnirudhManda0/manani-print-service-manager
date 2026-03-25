# Deployment Runbook - CyberCafe Print & Service Manager

This runbook is the single reference for production rollout in a real cyber cafe.

## 1. Target Setup

- Admin Server PC: Windows 7
- Client Monitor PCs: Windows 10
- Network: same LAN (example `192.168.1.x`)
- Admin API URL example: `http://192.168.1.50:8787`

No Python installation is required on shop machines when using the packaged EXEs.

## 2. Deployment Artifacts

Primary artifacts:

- `release/CyberCafeServer.zip`
- `release/CyberCafeClient.zip`

Inside server package:

- `CyberCafeServer.exe`
- `config/settings.json`
- `database/schema.sql`
- `version.txt`

Inside client package:

- `CyberCafeClient.exe`
- `config/settings.json`
- `database/schema.sql`
- `version.txt`

## 3. Build Artifacts (Technician Machine)

Use a technician/build machine to create release packages.

Important compatibility note:

- For Windows 7 deployment, create final production builds with Python 3.9.
- Builds created with newer Python versions (for example 3.13) may not run on Windows 7.

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Build EXEs:

```bash
pyinstaller CyberCafeServer.spec
pyinstaller CyberCafeClient.spec
```

3. Build ZIPs:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release_packages.ps1
```

## 4. Install on Admin Server (Windows 7)

1. Copy `CyberCafeServer.zip` to admin PC.
2. Extract to folder, for example `D:\CyberCafeServer`.
3. Open `config/settings.json` and set:
   - `mode: "server"`
   - `server_ip: "192.168.1.50"`
   - `server_port: 8787`
   - `auto_discovery_enabled: true`
   - `discovery_port: 8788`
   - `computer_name: "ADMIN-PC"`
   - `operator_id: "ADMIN"`
4. Ensure printer drivers are installed.
5. Start `CyberCafeServer.exe`.
6. Verify API health by opening:
   - `http://192.168.1.50:8787/health`

## 5. Install on Client PC (Windows 10)

1. Copy `CyberCafeClient.zip` to client PC.
2. Extract to folder, for example `D:\CyberCafeClient`.
3. Edit `config/settings.json`:
   - `mode: "client"`
   - `auto_discovery_enabled: true`
   - `discovery_port: 8788`
   - `central_server_url: "http://192.168.1.50:8787"` (optional fallback)
   - `computer_name: "CLIENT-PC-01"` (unique per machine)
   - `operator_id: "ADMIN"` (or operator name used at this machine)
4. Ensure local printers are installed and test-print works in Windows.
5. Start `CyberCafeClient.exe`.

## 6. First Production Validation

1. Print one 2+ page document from each client PC.
2. Confirm Admin Print Log shows:
   - correct computer name
   - correct printer name
   - correct pages
   - non-zero cost
3. Confirm dashboard totals update.

## 7. Simultaneous Print Safety

The system supports concurrent submissions from multiple PCs.

Technical safeguards:

- Client monitor deduplicates local spooler jobs by printer/job/timestamp/document.
- Client monitor keeps unsent jobs in an in-memory retry queue while the app is running.
- Server stores jobs with idempotent `source_job_key`.
- SQLite WAL mode + thread lock protects concurrent writes.

Expected behavior:

- If 2 PCs print at the same time, both jobs are recorded independently.
- If a client retries the same API submission, duplicate rows are prevented.

Validation test:

1. Trigger print on two PCs at the same time.
2. Confirm two distinct rows appear in print log.
3. Confirm no repeated duplicate rows for the same job.

## 8. Update Procedure (Safe)

1. Stop server and clients.
2. Backup `database/cybercafe.db` and `config/settings.json`.
3. Replace executable files with newer version.
4. Keep existing `database/` and `config/` folders.
5. Restart services.

## 9. Rollback Procedure

1. Stop running EXEs.
2. Restore previous EXEs.
3. Restore `database/cybercafe.db` from backup if needed.
4. Restart and verify `/health`.

## 10. Troubleshooting

If print not detected:

- Check Windows Print Spooler service.
- Check printer appears in Devices and Printers.
- Check `logs/application.log`.
- Run spooler test on build machine:

```bash
python test_spooler_detection.py
```

If port conflict occurs:

- Change `server_port` in `config/settings.json`.

If client cannot submit:

- Verify client can open `http://<server_ip>:8787/health`.
- Confirm firewall allows chosen server port.
