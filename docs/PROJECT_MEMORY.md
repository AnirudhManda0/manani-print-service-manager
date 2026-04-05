# PrintX Project Memory

## Product Identity

- Product name: `PrintX`
- Windows 10+ executable: `PrintX.exe`
- Windows 7 executable: `PrintX_Win7.exe`

## Core Technical Decisions

- Desktop UI runs through Qt.
- Background monitoring uses pywin32 and the Windows Print Spooler.
- Data persistence stays in SQLite on the server/admin side.
- Client submissions are idempotent through `source_job_key`.
- UI close action hides to tray so monitoring continues.

## Important Release Truth

- Windows 10 builds can be produced from the modern environment.
- Windows 7 builds must be produced inside a Python 3.8 legacy environment.
- This is the key fix for the `api-ms-win-core-path-l1-1-0.dll` issue reported from the field.
