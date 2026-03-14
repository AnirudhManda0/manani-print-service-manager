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
        poll_interval: float = 1.2,
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
        while not self._stop_event.is_set():
            try:
                for printer_name in self._list_printers():
                    self._scan_printer(printer_name)
            except Exception as exc:
                logger.exception("Printer polling error: %s", exc)
            self._stop_event.wait(self.poll_interval)

    def _list_printers(self):
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        printers = win32print.EnumPrinters(flags)
        return [p[2] for p in printers if len(p) > 2]

    def _scan_printer(self, printer_name: str) -> None:
        handle = None
        try:
            handle = win32print.OpenPrinter(printer_name)
            jobs = win32print.EnumJobs(handle, 0, 256, 2)
            for job in jobs:
                job_key = f"{printer_name}:{job.get('JobId')}:{job.get('Submitted')}"
                if job_key in self._seen_jobs:
                    continue

                payload = self._job_to_payload(printer_name, handle, job)
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

    def _job_to_payload(self, printer_name: str, printer_handle, job: Dict[str, object]) -> Dict[str, object]:
        pages = int(job.get("TotalPages", 0) or 0)
        if pages <= 0:
            pages = int(job.get("PagesPrinted", 0) or 0)
        if pages <= 0:
            pages = 1

        print_type = "black_and_white"
        try:
            job_info = win32print.GetJob(printer_handle, int(job["JobId"]), 2)
            dev_mode = job_info.get("pDevMode")
            color_value = getattr(dev_mode, "Color", None)
            if color_value == getattr(win32con, "DMCOLOR_COLOR", 2):
                print_type = "color"
        except Exception:
            # If color information is not available, default to black_and_white.
            pass

        return {
            "computer_name": self.computer_name,
            "printer_name": printer_name,
            "document_name": str(job.get("pDocument", "") or ""),
            "pages": pages,
            "print_type": print_type,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }

    def _dispatch(self, payload: Dict[str, object]) -> None:
        if self.api_base_url:
            self._send_to_api(payload)
            return
        if self.on_job:
            self.on_job(payload)

    def _send_to_api(self, payload: Dict[str, object]) -> None:
        url = f"{self.api_base_url}/api/print-jobs"
        for attempt in range(3):
            try:
                response = requests.post(url, json=payload, timeout=3)
                response.raise_for_status()
                return
            except Exception as exc:
                logger.warning("Failed to submit print job (attempt %s/3): %s", attempt + 1, exc)
                time.sleep(0.5 * (attempt + 1))
        logger.error("Dropping print job after repeated API failures: %s", json.dumps(payload))


def run_background_client(server_url: str, poll_interval: float = 1.2) -> None:
    logging.basicConfig(
        level=logging.INFO,
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
    server = os.environ.get("CYBERCAFE_SERVER_URL", "http://127.0.0.1:8787")
    run_background_client(server)
