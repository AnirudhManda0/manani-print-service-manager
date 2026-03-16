"""Standalone spooler detection test.

Usage:
    python test_spooler_detection.py

What it does:
1. Enumerates all installed printers with win32print.EnumPrinters.
2. Starts PrintMonitor polling every 0.5 seconds.
3. Logs each newly detected print job from any printer queue.
"""

import logging
import os
import time
from typing import List

try:
    import win32print
except ImportError:
    win32print = None

from client.print_monitor import PrintMonitor


def list_printers() -> List[str]:
    if win32print is None:
        raise RuntimeError("pywin32 is not installed. Run: pip install pywin32")

    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    names: List[str] = []

    try:
        entries = win32print.EnumPrinters(flags, None, 2)
        for entry in entries:
            if isinstance(entry, dict):
                name = str(entry.get("pPrinterName", "")).strip()
                if name:
                    names.append(name)
    except Exception:
        entries = win32print.EnumPrinters(flags)
        for entry in entries:
            if isinstance(entry, dict):
                name = str(entry.get("pName") or entry.get("pPrinterName") or "").strip()
            else:
                name = str(entry[2]).strip() if len(entry) > 2 else ""
            if name:
                names.append(name)

    unique = []
    seen = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        unique.append(name)
    return unique


def on_job(payload: dict) -> None:
    print("")
    print("New print job detected")
    print(f"  printer_name    : {payload.get('printer_name')}")
    print(f"  document_name   : {payload.get('document_name')}")
    print(f"  total_pages     : {payload.get('pages')}")
    print(f"  submission_time : {payload.get('submission_time')}")
    print(f"  operator_id     : {payload.get('operator_id')}")
    print(f"  user_name       : {payload.get('user_name') or 'N/A'}")
    print(f"  job_id          : {payload.get('job_id')}")


def main() -> None:
    level_name = os.environ.get("MANANI_LOG_LEVEL", "DEBUG").upper()
    level = getattr(logging, level_name, logging.DEBUG)
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    printers = list_printers()
    print("Detected printers:")
    if not printers:
        print("  (none found)")
    else:
        for name in printers:
            print(f"  - {name}")

    print("")
    print("Monitoring all printer queues every 0.5s.")
    print("Send a test page to any installed printer. Press Ctrl+C to stop.")

    monitor = PrintMonitor(on_job=on_job, poll_interval=0.5)
    monitor.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
        print("Stopped spooler detection test.")


if __name__ == "__main__":
    main()
