"""Windows print spooler monitor.

This client polls printer queues, extracts metadata, and sends jobs to FastAPI.
It is used in:
- single mode (same PC as API/UI)
- centralized mode (remote client PCs posting to central server)
"""

import json
import logging
import os
import socket
import threading
import time
from collections import deque
from datetime import datetime
from typing import Callable, Dict, Optional

import requests

try:
    import win32con
    import win32print
except ImportError:  # pragma: no cover - only used on Windows with pywin32 installed.
    win32con = None
    win32print = None


logger = logging.getLogger(__name__)


class PrintMonitor:
    """
    Polls Windows print spooler and emits print jobs once.
    The monitor can either call a local callback or POST to API.
    """

    def __init__(
        self,
        api_base_url: Optional[str] = None,
        on_job: Optional[Callable[[Dict[str, object]], None]] = None,
        poll_interval: float = 0.5,
        computer_name: Optional[str] = None,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/") if api_base_url else None
        self.on_job = on_job
        self.poll_interval = poll_interval
        self.computer_name = computer_name or socket.gethostname()

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._seen_jobs = set()
        self._seen_order = deque(maxlen=100000)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        if win32print is None:
            raise RuntimeError("pywin32 is not available. Install pywin32 to enable print monitoring.")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="print-monitor")
        self._thread.start()
        logger.info("Print monitor started on %s", self.computer_name)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("Print monitor stopped")

    def _run(self) -> None:
        # Poll all printers at a short interval to avoid missing short-lived spooler jobs.
        while not self._stop_event.is_set():
            try:
                printers = self._list_printers()
                logger.debug("Detected printers: %s", printers)
                for printer_name in printers:
                    self._scan_printer(printer_name)
            except Exception as exc:
                logger.exception("Printer polling error: %s", exc)
            self._stop_event.wait(self.poll_interval)

    def _list_printers(self):
        """Enumerate local and connected printers (includes virtual printers)."""
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        printers = win32print.EnumPrinters(flags)
        return [p[2] for p in printers if len(p) > 2]

    def _scan_printer(self, printer_name: str) -> None:
        """Read queued jobs from one printer and emit unseen jobs."""
        handle = None
        try:
            handle = win32print.OpenPrinter(printer_name)
            printer_info = win32print.GetPrinter(handle, 2)
            jobs = win32print.EnumJobs(handle, 0, 256, 2)
            logger.debug("Detected %s queued jobs on printer '%s'", len(jobs), printer_name)
            for job in jobs:
                job_key = f"{printer_name}:{job.get('JobId')}:{job.get('Submitted')}"
                if job_key in self._seen_jobs:
                    continue

                payload = self._job_to_payload(printer_name, handle, printer_info, job)
                logger.debug(
                    "Detected print job id=%s printer=%s document=%s pages=%s type=%s paper=%s",
                    job.get("JobId"),
                    payload["printer_name"],
                    payload["document_name"],
                    payload["pages"],
                    payload["print_type"],
                    payload["paper_size"],
                )
                self._dispatch(payload)
                self._remember_job(job_key)
        except Exception as exc:
            logger.debug("Unable to scan printer %s: %s", printer_name, exc)
        finally:
            if handle:
                try:
                    win32print.ClosePrinter(handle)
                except Exception:
                    pass

    def _remember_job(self, key: str) -> None:
        self._seen_jobs.add(key)
        self._seen_order.append(key)
        # Keep memory bounded.
        while len(self._seen_jobs) > self._seen_order.maxlen:
            old = self._seen_order.popleft()
            self._seen_jobs.discard(old)

    def _detect_print_type(self, job_info: Dict[str, object], printer_info: Dict[str, object]) -> str:
        """Infer print type with fallback chain: job devmode -> printer devmode -> name hint."""
        def _color_from_devmode(dev_mode) -> Optional[str]:
            if dev_mode is None:
                return None
            color_value = getattr(dev_mode, "Color", None)
            if color_value == getattr(win32con, "DMCOLOR_COLOR", 2):
                return "color"
            if color_value == getattr(win32con, "DMCOLOR_MONOCHROME", 1):
                return "black_and_white"
            return None

        # First try job-level DEVMODE (most accurate).
        detected = _color_from_devmode(job_info.get("pDevMode"))
        if detected:
            return detected

        # Fallback to printer default DEVMODE.
        detected = _color_from_devmode(printer_info.get("pDevMode"))
        if detected:
            return detected

        # Final fallback for monochrome-only devices identified by common naming.
        printer_name = str(printer_info.get("pPrinterName", "")).lower()
        mono_tokens = ("mono", "monochrome", "bw", "b/w")
        if any(token in printer_name for token in mono_tokens):
            return "black_and_white"

        return "black_and_white"

    @staticmethod
    def _paper_size_label(paper_size_value: Optional[int]) -> str:
        """Map DEVMODE paper size integer to friendly values used in reports."""
        if paper_size_value is None:
            return "Unknown"
        mapping = {
            getattr(win32con, "DMPAPER_A3", 8): "A3",
            getattr(win32con, "DMPAPER_A4", 9): "A4",
            getattr(win32con, "DMPAPER_LETTER", 1): "Letter",
        }
        return mapping.get(int(paper_size_value), "Unknown")

    def _job_to_payload(
        self,
        printer_name: str,
        printer_handle,
        printer_info: Dict[str, object],
        job: Dict[str, object],
    ) -> Dict[str, object]:
        """Convert raw spooler job to API payload.

        Billing is not calculated here; only metadata capture happens in monitor.
        """
        pages = int(job.get("TotalPages", 0) or 0)
        if pages <= 0:
            pages = int(job.get("PagesPrinted", 0) or 0)
        if pages <= 0:
            pages = 1

        print_type = "black_and_white"
        paper_size = "Unknown"
        try:
            job_info = win32print.GetJob(printer_handle, int(job["JobId"]), 2)
            print_type = self._detect_print_type(job_info=job_info, printer_info=printer_info)
            job_dev_mode = job_info.get("pDevMode")
            printer_dev_mode = printer_info.get("pDevMode")
            paper_value = getattr(job_dev_mode, "PaperSize", None) or getattr(printer_dev_mode, "PaperSize", None)
            paper_size = self._paper_size_label(paper_value)
        except Exception:
            logger.debug("Could not read extended metadata for printer=%s job_id=%s", printer_name, job.get("JobId"))

        return {
            "computer_name": self.computer_name,
            "printer_name": printer_name,
            "document_name": str(job.get("pDocument", "") or ""),
            "pages": pages,
            "print_type": print_type,
            "paper_size": paper_size,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }

    def _dispatch(self, payload: Dict[str, object]) -> None:
        """Deliver jobs either to API (normal path) or callback (local test path)."""
        if self.api_base_url:
            self._send_to_api(payload)
            return
        if self.on_job:
            self.on_job(payload)

    def _send_to_api(self, payload: Dict[str, object]) -> None:
        """POST captured print job to API with small retry window."""
        url = f"{self.api_base_url}/api/print-jobs"
        for attempt in range(3):
            try:
                response = requests.post(url, json=payload, timeout=3)
                response.raise_for_status()
                logger.debug(
                    "Submitted print job to API printer=%s doc=%s pages=%s",
                    payload.get("printer_name"),
                    payload.get("document_name"),
                    payload.get("pages"),
                )
                return
            except Exception as exc:
                logger.warning("Failed to submit print job (attempt %s/3): %s", attempt + 1, exc)
                time.sleep(0.5 * (attempt + 1))
        logger.error("Dropping print job after repeated API failures: %s", json.dumps(payload))


def run_background_client(server_url: str, poll_interval: float = 0.5) -> None:
    """Run monitor loop for standalone client deployment."""
    level_name = os.environ.get("MANANI_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    monitor = PrintMonitor(api_base_url=server_url, poll_interval=poll_interval)
    monitor.start()
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        monitor.stop()


if __name__ == "__main__":
    server = os.environ.get("MANANI_SERVER_URL") or os.environ.get("CYBERCAFE_SERVER_URL", "http://127.0.0.1:8787")
    run_background_client(server, poll_interval=0.5)
