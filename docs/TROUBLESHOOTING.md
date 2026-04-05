# Troubleshooting

## Windows 7 Error: `api-ms-win-core-path-l1-1-0.dll`

Cause:
- the EXE was built with a modern Python/runtime toolchain that is not Windows 7 compatible

Fix:
- build `PrintX_Win7.exe` using Python 3.8
- use `requirements-win7.txt`
- build from the `windows7-legacy` lane

## No Print Jobs Detected

Check:

- printer appears in Windows Devices and Printers
- Print Spooler service is running
- `PRINTX_LOG_LEVEL=DEBUG` is enabled for diagnosis
- `test_spooler_detection.py` lists the printer

## Page Count Is Wrong

Check:

- print job is not being recorded too early
- the job reaches a final spooler state with `TotalPages` or `PagesPrinted`
- logs contain `Pages detected` before `Job recorded`

## Duplicate Transactions

Check:

- `source_job_key` is present in the API payload
- server is running the current build with unique index support

## UI Closed But Monitoring Stopped

Expected behavior:
- closing the window should hide PrintX to the tray

If not:
- verify the system tray is available in Windows
- reopen from the tray icon

## Config File Missing or Broken

PrintX recreates a default config automatically.
If the original JSON is unreadable, it is moved to:

- `settings.json.corrupt`

## Database Corruption

If SQLite cannot open correctly, PrintX attempts to quarantine the broken DB as:

- `printx.db.corrupt-YYYYMMDD-HHMMSS`

Then it creates a fresh database from `database/schema.sql`.
