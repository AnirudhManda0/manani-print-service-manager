# Project Memory

This file is the working memory for ManAni Print & Service Manager so future debugging and upgrades start with the right context.

## Current Goal

The application must run in a real cyber cafe on:

- Windows 7 admin server
- Windows 10 client PCs

It must:

- detect print jobs automatically from all installed printers
- capture non-zero page counts
- calculate print cost and dashboard totals correctly
- connect clients to the admin server automatically when possible
- keep central data only on the server

## Runtime Roles

- `single`: API + UI + print monitor on one PC
- `server`: admin server with UI/API and optional local print monitor
- `client`: print monitor only, sending transactions to admin server

## Important Architecture Notes

- Print detection lives in [client/print_monitor.py](C:/Users/Manda Anirudh/Documents/manani-print-manager/client/print_monitor.py)
- API lives in [server/api.py](C:/Users/Manda Anirudh/Documents/manani-print-manager/server/api.py)
- Billing/reporting/database logic lives in [server/database.py](C:/Users/Manda Anirudh/Documents/manani-print-manager/server/database.py)
- Runtime config normalization lives in [runtime_config.py](C:/Users/Manda Anirudh/Documents/manani-print-manager/runtime_config.py)
- LAN auto-discovery lives in [network_discovery.py](C:/Users/Manda Anirudh/Documents/manani-print-manager/network_discovery.py)

## Known Good Behavior

- Source run can detect printers and print jobs through pywin32.
- Server computes page-based totals and revenue from SQLite.
- Duplicate/retried print submissions are blocked by `source_job_key`.

## Main Failure That Was Observed

The packaged EXE did not behave like the working source version.

Likely causes:

- unsupported build stack for Windows 7
- missing packaged Windows print runtime pieces
- client fixed to wrong server URL and dropping jobs when the server was unreachable

## Recovery Changes Added

- automatic LAN server discovery through UDP broadcast
- in-memory retry queue for unsent print jobs
- printer inventory logging so packaged runs show detected printers
- PyInstaller specs updated with pywin32-related hidden imports
- build script now blocks non-Python-3.9 builds unless explicitly overridden

## Production Build Rule

For real Windows 7 deployment:

- build on Python 3.9
- prefer PySide2
- do not trust builds created with Python 3.10+ for Windows 7

## Key Config Values

- `server_ip`
- `server_port`
- `auto_discovery_enabled`
- `discovery_port`
- `computer_name`
- `operator_id`
- `poll_interval`
- `bw_price_per_page`
- `color_price_per_page`

## Next Verification Steps

1. Build on a Windows 7/Windows 10 compatible Python 3.9 environment.
2. Start `CyberCafeServer.exe`.
3. Start `CyberCafeClient.exe` on another PC without hardcoding server URL.
4. Confirm client discovers server automatically.
5. Print a multi-page document and confirm:
   - pages > 0
   - cost is correct
   - dashboard totals update
6. Check `logs/application.log` on both machines if anything fails.
