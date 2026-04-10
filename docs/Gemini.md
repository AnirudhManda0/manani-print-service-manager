# PrintX Gemini Notes

This file summarizes the Gemini-assisted updates and the project context that should be checked before future work.

## Project

- Name: PrintX
- Subtitle: Print and Service Manager
- Version: 2.0.0
- Root: C:\Users\Manda Anirudh\Documents\manani-print-manager
- Repository: AnirudhManda0/manani-print-service-manager

## Architecture

PrintX is an offline-first Windows desktop app for cyber cafe print/service billing.

- UI: Qt via ui/qt.py compatibility layer
- API: FastAPI local server
- Database: SQLite through server/database.py
- Print monitor: pywin32 Windows spooler polling in client/print_monitor.py
- Discovery: UDP LAN discovery in network_discovery.py
- Runtime modes: single, server, client

## Key Fixes From Gemini Pass

- Removed QTabWidget document mode to avoid the unwanted native separator line below KPI cards.
- Scoped QScrollArea styling in the Services tab so it does not cascade into service buttons.
- Added service catalog deletion API and UI path, with protection against deleting services already used in records.
- Improved color detection documentation and logging around job DEVMODE and printer capability fallback.
- Confirmed release lanes should remain releases/windows10 and releases/windows7, not temporary folders such as windows10+.

## Print Type Notes

- Job DEVMODE is the best source for B&W/color.
- Printer default DEVMODE is not a reliable per-job source because it often describes printer defaults or hardware capability.
- Virtual printers such as Microsoft Print to PDF may report grayscale/B&W output as color.
- For ambiguous jobs, operators can correct the Print Type cell in the Print Log and billing will recalculate.

## Build Notes

- Windows 10+: PrintX.spec -> releases/windows10/PrintX.exe
- Windows 7: PrintX_Win7.spec -> releases/windows7/PrintX_Win7.exe
- Windows 7 requires Python 3.8 to avoid missing api-ms-win-core-path-l1-1-0.dll.

## Cleanup Notes

Generated/runtime folders that should not be committed:

- build/
- dist/
- logs/
- backup/
- releases/*/config/
- releases/*/database/
- releases/*/logs/
- releases/*/backup/
- temporary release folders such as releases/windows10+ or releases/windows10/PrintXg
