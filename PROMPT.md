# Project Memory

This file is the working memory for PrintX so future debugging and upgrades start with the right context.

## Product Goal

PrintX is a cyber cafe print and service management system with:

- Windows 10+ production release
- Windows 7 legacy release
- accurate spooler-based print tracking
- service billing
- SQLite persistence
- background tray monitoring
- auto-start support

## Runtime Roles

- `single`: UI + API + print monitor on one PC
- `server`: central admin server
- `client`: monitor-only client sending jobs to the server

## Important Files

- `main.py`
- `branding.py`
- `autostart.py`
- `client/print_monitor.py`
- `server/api.py`
- `server/database.py`
- `runtime_config.py`
- `network_discovery.py`

## Release Rules

- Windows 10+ build uses `PrintX.spec`
- Windows 7 build uses `PrintX_Win7.spec`
- Windows 7 build must be produced with Python 3.8 in a legacy-compatible environment

## Field Issue Already Observed

The Windows 7 runtime error `api-ms-win-core-path-l1-1-0.dll` is caused by building with a modern unsupported runtime stack.

## Current Product Decisions

- app branding is centralized in `branding.py`
- logo/icon live under `assets/`
- close-to-tray keeps monitoring alive
- `source_job_key` prevents duplicate print ingestion
- config corruption falls back to regenerated defaults
- database corruption is quarantined before new DB initialization
