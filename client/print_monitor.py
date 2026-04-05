"""Windows spooler monitor for all installed printers.

This module continuously polls every printer queue through pywin32 and emits
new print jobs exactly once.
"""

import json
import logging
import os
import socket
import threading
import time
from collections import deque
from datetime import datetime
from typing import Callable, Dict, List, Optional, Set

import requests
from network_discovery import DEFAULT_DISCOVERY_PORT, discover_server_urls

try:
    import pythoncom
    import pywintypes
    import win32con
    import win32print
except ImportError:  # pragma: no cover - only used on Windows with pywin32 installed.
    pythoncom = None
    pywintypes = None
    win32con = None
    win32print = None


logger = logging.getLogger(__name__)


class PrintMonitor:
    """Poll all printer queues and emit each spooler job once."""

    def __init__(
        self,
        api_base_url: Optional[str] = None,
        on_job: Optional[Callable[[Dict[str, object]], None]] = None,
        poll_interval: float = 0.5,
        computer_name: Optional[str] = None,
        operator_id: Optional[str] = None,
        auto_discovery_enabled: bool = True,
        discovery_port: int = DEFAULT_DISCOVERY_PORT,
        max_processed_jobs: int = 100000,
    ) -> None:
        self.api_base_url = self._normalize_api_url(api_base_url)
        self.on_job = on_job
        self.poll_interval = poll_interval
        self.computer_name = computer_name or socket.gethostname()
        self.operator_id = (operator_id or os.environ.get("PRINTX_OPERATOR_ID") or "ADMIN").strip() or "ADMIN"
        self.auto_discovery_enabled = bool(auto_discovery_enabled)
        self.discovery_port = int(discovery_port)
        self.max_processed_jobs = max(1000, int(max_processed_jobs))

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._seen_jobs = set()
        self._seen_order = deque(maxlen=self.max_processed_jobs)
        self._pending_jobs: Dict[str, Dict[str, object]] = {}
        self._outbox = deque()
        self._api_candidates: List[str] = []
        self._discovered_urls: List[str] = []
        self._active_api_base_url = self.api_base_url
        self._last_discovery_at = 0.0
        self._last_connection_log_at = 0.0
        self._printer_snapshot: List[str] = []
        self._terminal_flush_delay = max(1.5, float(self.poll_interval) * 3)
        self._post_exit_wait = max(2.5, float(self.poll_interval) * 6)
        self._remember_api_candidate(self.api_base_url)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        if win32print is None:
            raise RuntimeError("pywin32 is not available. Install pywin32 to enable print monitoring.")
        logger.info(
            "Print monitor runtime ready: computer=%s auto_discovery=%s discovery_port=%s pythoncom=%s pywintypes=%s",
            self.computer_name,
            self.auto_discovery_enabled,
            self.discovery_port,
            pythoncom is not None,
            pywintypes is not None,
        )
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
                printers = self._list_printers()
                self._log_printer_inventory(printers)
                for printer_name in printers:
                    logger.debug("Detected printer: %s", printer_name)
                    self._scan_printer_queue(printer_name)
                self._drain_outbox()
            except Exception as exc:
                logger.exception("Printer polling error: %s", exc)
            self._stop_event.wait(self.poll_interval)

    @staticmethod
    def _normalize_api_url(url: Optional[str]) -> Optional[str]:
        text = str(url or "").strip().rstrip("/")
        if not text:
            return None
        if not text.lower().startswith(("http://", "https://")):
            return None
        return text

    def _remember_api_candidate(self, url: Optional[str]) -> None:
        normalized = self._normalize_api_url(url)
        if normalized and normalized not in self._api_candidates:
            self._api_candidates.append(normalized)

    def _refresh_discovered_urls(self, force: bool = False) -> None:
        if not self.auto_discovery_enabled:
            return
        now = time.monotonic()
        if not force and now - self._last_discovery_at < 15:
            return
        self._last_discovery_at = now
        discovered = [self._normalize_api_url(url) for url in discover_server_urls(port=self.discovery_port, timeout=1.2)]
        normalized = [url for url in discovered if url]
        if normalized != self._discovered_urls:
            if normalized:
                logger.info("Auto-discovered server URLs: %s", ", ".join(normalized))
            else:
                logger.info("No admin server discovered on UDP %s", self.discovery_port)
        self._discovered_urls = normalized
        for url in normalized:
            self._remember_api_candidate(url)

    def _candidate_api_urls(self, force_discovery: bool = False) -> List[str]:
        if force_discovery:
            self._refresh_discovered_urls(force=True)
        elif self.auto_discovery_enabled and not (self._active_api_base_url or self._api_candidates or self._discovered_urls):
            self._refresh_discovered_urls(force=False)
        urls: List[str] = []
        for url in [self._active_api_base_url] + self._api_candidates + self._discovered_urls:
            normalized = self._normalize_api_url(url)
            if normalized and normalized not in urls:
                urls.append(normalized)
        return urls

    def _log_printer_inventory(self, printers: List[str]) -> None:
        if printers == self._printer_snapshot:
            return
        self._printer_snapshot = list(printers)
        if printers:
            logger.info("Detected printers (%s): %s", len(printers), ", ".join(printers))
        else:
            logger.warning("Detected printers (0): no printers available from Windows spooler")

    def _list_printers(self) -> List[str]:
        """Enumerate all locally installed and connected printers."""
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        printers: List[str] = []

        # Level 2 returns rich dict entries and is preferred when available.
        try:
            entries = win32print.EnumPrinters(flags, None, 2)
            for entry in entries:
                if isinstance(entry, dict):
                    name = str(entry.get("pPrinterName", "")).strip()
                    if name:
                        printers.append(name)
        except Exception as exc:
            logger.debug("EnumPrinters(level=2) failed, falling back to default level: %s", exc)

        if not printers:
            entries = win32print.EnumPrinters(flags)
            for entry in entries:
                if isinstance(entry, dict):
                    name = str(entry.get("pName") or entry.get("pPrinterName") or "").strip()
                else:
                    name = str(entry[2]).strip() if len(entry) > 2 else ""
                if name:
                    printers.append(name)

        # Preserve order while removing duplicates.
        seen = set()
        unique_printers = []
        for name in printers:
            if name in seen:
                continue
            seen.add(name)
            unique_printers.append(name)
        return unique_printers

    def _scan_printer_queue(self, printer_name: str) -> None:
        """Poll one printer queue using EnumJobs and emit unseen jobs."""
        handle = None
        logger.debug("Checking queue: %s", printer_name)
        try:
            handle = win32print.OpenPrinter(printer_name)
            jobs = win32print.EnumJobs(handle, 0, 1024, 2)
            current_pending_keys: Set[str] = set()
            now = time.monotonic()
            for job in jobs:
                job_id = self._safe_int(job.get("JobId"), default=0)
                if job_id <= 0:
                    continue

                pending_key = self._pending_job_key(printer_name=printer_name, job_id=job_id)
                current_pending_keys.add(pending_key)
                state = self._merge_pending_state(pending_key=pending_key, now=now, job=job, printer_name=printer_name)
                total_pages, pages_printed = self._extract_page_counts(job)
                logger.debug(
                    "Queue snapshot: printer=%s job_id=%s total_pages=%s pages_printed=%s status=%s",
                    printer_name,
                    job_id,
                    total_pages,
                    pages_printed,
                    self._safe_int(job.get("Status"), default=0),
                )
                if max(total_pages, pages_printed) <= 0:
                    logger.debug(
                        "Pages pending: printer=%s job_id=%s document=%s",
                        printer_name,
                        job_id,
                        state.get("document_name", ""),
                    )

            # Finalize jobs that disappeared from queue and completed jobs lingering in queue.
            self._flush_completed_pending_jobs(
                printer_name=printer_name,
                active_pending_keys=current_pending_keys,
                now=now,
            )
            self._flush_terminal_pending_jobs(
                printer_name=printer_name,
                active_pending_keys=current_pending_keys,
                printer_handle=handle,
                now=now,
            )
            self._cleanup_stale_pending_jobs(now=now)
        except Exception as exc:
            logger.debug("Queue check failed for printer '%s': %s", printer_name, exc)
        finally:
            if handle:
                try:
                    win32print.ClosePrinter(handle)
                except Exception:
                    pass

    @staticmethod
    def _pending_job_key(printer_name: str, job_id: int) -> str:
        return f"{printer_name}:{job_id}"

    def _merge_pending_state(self, pending_key: str, now: float, job: Dict[str, object], printer_name: str) -> Dict[str, object]:
        state = self._pending_jobs.get(pending_key) or {}
        total_pages, pages_printed = self._extract_page_counts(job)
        status_code = self._safe_int(job.get("Status"), default=0)
        previous_pages = max(
            self._safe_int(state.get("resolved_total_pages"), 0),
            self._safe_int(state.get("max_pages_printed"), 0),
        )
        state.update(
            {
                "printer_name": printer_name,
                "job_id": self._safe_int(job.get("JobId"), default=0),
                "document_name": str(job.get("pDocument") or state.get("document_name") or "").strip(),
                "submission_time": self._normalize_submission_time(job.get("Submitted")) or state.get("submission_time"),
                "user_name": str(job.get("pUserName") or state.get("user_name") or "").strip() or None,
                "status_code": status_code,
                "raw_job": dict(job),
            }
        )
        state["first_seen"] = float(state.get("first_seen", now))
        state["last_seen"] = now
        state["max_pages_printed"] = max(self._safe_int(state.get("max_pages_printed"), 0), pages_printed)
        state["resolved_total_pages"] = max(self._safe_int(state.get("resolved_total_pages"), 0), total_pages)
        current_pages = max(self._safe_int(state.get("resolved_total_pages"), 0), self._safe_int(state.get("max_pages_printed"), 0))
        if current_pages > previous_pages:
            state["last_page_change"] = now
        else:
            state["last_page_change"] = float(state.get("last_page_change", now))

        if self._is_terminal_status(status_code):
            state["terminal_since"] = float(state.get("terminal_since", now))
        else:
            state.pop("terminal_since", None)

        # If the job reappears in queue, clear any exit timer.
        state.pop("queue_exited_at", None)
        self._pending_jobs[pending_key] = state
        return state

    def _flush_completed_pending_jobs(self, printer_name: str, active_pending_keys: Set[str], now: float) -> None:
        prefix = f"{printer_name}:"
        candidate_keys = [k for k in self._pending_jobs.keys() if k.startswith(prefix) and k not in active_pending_keys]
        for key in candidate_keys:
            state = self._pending_jobs.get(key)
            if not state:
                continue
            state["queue_exited_at"] = float(state.get("queue_exited_at", now))
            pages = self._resolved_pages_from_state(state)
            if pages <= 0:
                pages = self._resolve_pages_after_job_exit(
                    printer_name=printer_name,
                    job_id=self._safe_int(state.get("job_id"), default=0),
                )
            if pages <= 0:
                elapsed_since_exit = now - float(state.get("queue_exited_at", now))
                if elapsed_since_exit < self._post_exit_wait:
                    # Give spooler a little more time to publish final page counts.
                    self._pending_jobs[key] = state
                    continue
                logger.warning(
                    "Page count unavailable for printer=%s job_id=%s. Using fallback pages=1.",
                    printer_name,
                    state.get("job_id"),
                )
                pages = 1

            payload = self._build_payload_from_state(
                state=state,
                pages=pages,
                printer_handle=None,
            )
            self._dispatch_if_new(payload)
            self._pending_jobs.pop(key, None)

    def _flush_terminal_pending_jobs(
        self,
        printer_name: str,
        active_pending_keys: Set[str],
        printer_handle,
        now: float,
    ) -> None:
        prefix = f"{printer_name}:"
        candidate_keys = [k for k in active_pending_keys if k.startswith(prefix)]
        for key in candidate_keys:
            state = self._pending_jobs.get(key)
            if not state:
                continue
            status_code = self._safe_int(state.get("status_code"), default=0)
            if not self._is_terminal_status(status_code):
                continue

            terminal_since = float(state.get("terminal_since", now))
            if now - terminal_since < self._terminal_flush_delay:
                continue

            pages = self._resolved_pages_from_state(state)
            if pages <= 0:
                continue

            payload = self._build_payload_from_state(
                state=state,
                pages=pages,
                printer_handle=printer_handle,
            )
            self._dispatch_if_new(payload)
            # Keep dedupe as source of truth even if spooler keeps completed entries.
            self._pending_jobs.pop(key, None)

    @staticmethod
    def _is_terminal_status(status_code: int) -> bool:
        if win32print is None:
            return False
        terminal_mask = (
            getattr(win32print, "JOB_STATUS_COMPLETE", 0)
            | getattr(win32print, "JOB_STATUS_PRINTED", 0)
            | getattr(win32print, "JOB_STATUS_DELETING", 0)
            | getattr(win32print, "JOB_STATUS_DELETED", 0)
        )
        if terminal_mask == 0:
            return False
        return bool(status_code & terminal_mask)

    def _resolved_pages_from_state(self, state: Dict[str, object]) -> int:
        return max(
            self._safe_int(state.get("resolved_total_pages"), default=0),
            self._safe_int(state.get("max_pages_printed"), default=0),
        )

    def _resolve_pages_after_job_exit(self, printer_name: str, job_id: int) -> int:
        if job_id <= 0:
            return 0
        handle = None
        max_pages = 0
        try:
            handle = win32print.OpenPrinter(printer_name)
            for _ in range(6):
                for level in (2, 1):
                    try:
                        job = win32print.GetJob(handle, int(job_id), level)
                        total_pages, pages_printed = self._extract_page_counts(job)
                        if total_pages > 0:
                            return total_pages
                        max_pages = max(max_pages, pages_printed)
                    except Exception:
                        continue
                time.sleep(0.25)
        except Exception:
            pass
        finally:
            if handle:
                try:
                    win32print.ClosePrinter(handle)
                except Exception:
                    pass
        return max_pages

    def _cleanup_stale_pending_jobs(self, now: float) -> None:
        to_remove = []
        for key, state in self._pending_jobs.items():
            first_seen = float(state.get("first_seen", now))
            if now - first_seen > 300:
                to_remove.append(key)
        for key in to_remove:
            self._pending_jobs.pop(key, None)

    def _dispatch_if_new(self, payload: Dict[str, object]) -> None:
        job_key = self._job_dedupe_key(payload)
        if job_key in self._seen_jobs:
            return
        logger.info(
            "New print job detected: printer=%s document=%s job_id=%s user=%s",
            payload.get("printer_name"),
            payload.get("document_name"),
            payload.get("job_id"),
            payload.get("user_name") or "N/A",
        )
        logger.debug(
            "Pages detected: printer=%s job_id=%s total_pages=%s",
            payload.get("printer_name"),
            payload.get("job_id"),
            payload.get("pages"),
        )
        self._dispatch(payload)
        self._remember_job(job_key)
        logger.debug(
            "Job recorded: printer=%s job_id=%s submission_time=%s",
            payload.get("printer_name"),
            payload.get("job_id"),
            payload.get("submission_time"),
        )

    @staticmethod
    def _extract_page_counts(job: Dict[str, object]) -> tuple[int, int]:
        total_pages = max(PrintMonitor._safe_int(job.get("TotalPages"), default=0), 0)
        pages_printed = max(PrintMonitor._safe_int(job.get("PagesPrinted"), default=0), 0)
        return total_pages, pages_printed

    @staticmethod
    def _extract_pages(job: Dict[str, object]) -> int:
        total_pages, pages_printed = PrintMonitor._extract_page_counts(job)
        return total_pages if total_pages > 0 else pages_printed

    def _job_dedupe_key(self, payload: Dict[str, object]) -> str:
        return (
            f"{payload.get('printer_name', '')}:"
            f"{payload.get('job_id', 0)}:"
            f"{payload.get('submission_time') or ''}:"
            f"{payload.get('document_name', '')}"
        )

    def _source_job_key(self, *, printer_name: str, job_id: int, submission_time: Optional[str], document_name: str) -> str:
        # Stable key used by server-side idempotency to avoid duplicates from retry races.
        return (
            f"{self.computer_name.strip()}|"
            f"{printer_name.strip()}|"
            f"{int(job_id)}|"
            f"{(submission_time or '').strip()}|"
            f"{document_name.strip()}"
        )

    def _remember_job(self, key: str) -> None:
        self._seen_jobs.add(key)
        self._seen_order.append(key)
        while len(self._seen_jobs) > self._seen_order.maxlen:
            old = self._seen_order.popleft()
            self._seen_jobs.discard(old)

    @staticmethod
    def _safe_int(value: object, default: int = 0) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_submission_time(submitted: object) -> str:
        """Normalize JOB_INFO submitted time to an ISO-like local timestamp."""
        if submitted is None:
            return ""

        if isinstance(submitted, datetime):
            return submitted.isoformat(timespec="seconds")

        if all(hasattr(submitted, key) for key in ("year", "month", "day", "hour", "minute", "second")):
            try:
                dt = datetime(
                    int(getattr(submitted, "year")),
                    int(getattr(submitted, "month")),
                    int(getattr(submitted, "day")),
                    int(getattr(submitted, "hour")),
                    int(getattr(submitted, "minute")),
                    int(getattr(submitted, "second")),
                )
                return dt.isoformat(timespec="seconds")
            except Exception:
                pass

        text = str(submitted).strip()
        if not text:
            return ""
        for candidate in (text, text.replace(" ", "T")):
            try:
                return datetime.fromisoformat(candidate).isoformat(timespec="seconds")
            except ValueError:
                continue
        return text

    def _detect_print_type(self, job_info: Dict[str, object], printer_info: Dict[str, object]) -> str:
        """Infer color mode from job or printer DEVMODE."""

        def _color_from_devmode(dev_mode) -> Optional[str]:
            if dev_mode is None or win32con is None:
                return None
            color_value = getattr(dev_mode, "Color", None)
            if color_value == getattr(win32con, "DMCOLOR_COLOR", 2):
                return "color"
            if color_value == getattr(win32con, "DMCOLOR_MONOCHROME", 1):
                return "black_and_white"
            return None

        detected = _color_from_devmode(job_info.get("pDevMode"))
        if detected:
            return detected
        detected = _color_from_devmode(printer_info.get("pDevMode"))
        if detected:
            return detected
        return "black_and_white"

    @staticmethod
    def _paper_size_label(paper_size_value: Optional[int]) -> str:
        if paper_size_value is None or win32con is None:
            return "Unknown"
        mapping = {
            getattr(win32con, "DMPAPER_A3", 8): "A3",
            getattr(win32con, "DMPAPER_A4", 9): "A4",
            getattr(win32con, "DMPAPER_LETTER", 1): "Letter",
        }
        return mapping.get(int(paper_size_value), "Unknown")

    def _read_extended_metadata(self, printer_handle, job_id: int, printer_name: str) -> Dict[str, str]:
        """Best-effort metadata lookup. Fallbacks are safe defaults."""
        print_type = "black_and_white"
        paper_size = "Unknown"
        try:
            printer_info = win32print.GetPrinter(printer_handle, 2)
            job_info = win32print.GetJob(printer_handle, int(job_id), 2)
            print_type = self._detect_print_type(job_info=job_info, printer_info=printer_info)
            job_dev_mode = job_info.get("pDevMode")
            printer_dev_mode = printer_info.get("pDevMode")
            paper_value = getattr(job_dev_mode, "PaperSize", None) or getattr(printer_dev_mode, "PaperSize", None)
            paper_size = self._paper_size_label(paper_value)
        except Exception:
            logger.debug("Could not read extended metadata for printer=%s job_id=%s", printer_name, job_id)
        return {"print_type": print_type, "paper_size": paper_size}

    def _build_payload_from_state(self, state: Dict[str, object], pages: int, printer_handle=None) -> Dict[str, object]:
        printer_name = str(state.get("printer_name", "") or "")
        job_id = self._safe_int(state.get("job_id"), default=0)
        document_name = str(state.get("document_name", "") or "")
        submission_time = str(state.get("submission_time", "") or "") or None
        user_name = str(state.get("user_name", "") or "").strip() or None
        metadata = {"print_type": "black_and_white", "paper_size": "Unknown"}
        if printer_handle is not None and job_id > 0:
            metadata = self._read_extended_metadata(printer_handle=printer_handle, job_id=job_id, printer_name=printer_name)
        event_time = submission_time or datetime.now().isoformat(timespec="seconds")
        return {
            "computer_name": self.computer_name,
            "operator_id": self.operator_id,
            "printer_name": printer_name,
            "document_name": document_name,
            "source_job_key": self._source_job_key(
                printer_name=printer_name,
                job_id=job_id,
                submission_time=submission_time,
                document_name=document_name,
            ),
            "pages": max(1, self._safe_int(pages, default=1)),
            "print_type": metadata["print_type"],
            "paper_size": metadata["paper_size"],
            "timestamp": event_time,
            "submission_time": submission_time,
            "user_name": user_name,
            "job_id": job_id,
        }

    def _dispatch(self, payload: Dict[str, object]) -> None:
        if self.api_base_url or self._api_candidates or self.auto_discovery_enabled:
            self._outbox.append(dict(payload))
            self._drain_outbox()
            return
        if self.on_job:
            self.on_job(payload)

    def _drain_outbox(self) -> None:
        while self._outbox:
            payload = self._outbox[0]
            if not self._send_to_api(payload):
                return
            self._outbox.popleft()

    def _send_to_api(self, payload: Dict[str, object]) -> bool:
        candidate_urls = self._candidate_api_urls(force_discovery=False)
        if not candidate_urls and self.auto_discovery_enabled:
            candidate_urls = self._candidate_api_urls(force_discovery=True)

        logger.debug(
            "Sending transaction to server: computer=%s printer=%s pages=%s candidates=%s",
            payload.get("computer_name"),
            payload.get("printer_name"),
            payload.get("pages"),
            ", ".join(candidate_urls) if candidate_urls else "none",
        )

        last_error = None
        for base_url in candidate_urls:
            url = f"{base_url}/api/print-jobs"
            try:
                response = requests.post(url, json=payload, timeout=3)
                response.raise_for_status()
                self._active_api_base_url = base_url
                self._remember_api_candidate(base_url)
                logger.debug(
                    "Transaction stored successfully: printer=%s job_id=%s",
                    payload.get("printer_name"),
                    payload.get("job_id"),
                )
                return True
            except Exception as exc:
                last_error = exc
                continue

        now = time.monotonic()
        if now - self._last_connection_log_at > 10:
            self._last_connection_log_at = now
            logger.warning(
                "Unable to reach admin server. Job will stay queued for retry. last_error=%s payload=%s",
                last_error,
                json.dumps(payload),
            )
        return False


def run_background_client(
    server_url: str,
    poll_interval: float = 0.5,
    computer_name: Optional[str] = None,
    operator_id: Optional[str] = None,
    auto_discovery_enabled: bool = True,
    discovery_port: int = DEFAULT_DISCOVERY_PORT,
) -> None:
    """Run monitor loop for standalone client deployment."""
    level_name = os.environ.get("PRINTX_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    monitor = PrintMonitor(
        api_base_url=server_url,
        poll_interval=poll_interval,
        computer_name=computer_name,
        operator_id=operator_id,
        auto_discovery_enabled=auto_discovery_enabled,
        discovery_port=discovery_port,
    )
    monitor.start()
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        monitor.stop()


if __name__ == "__main__":
    server = os.environ.get("PRINTX_SERVER_URL", "http://127.0.0.1:8787")
    run_background_client(server, poll_interval=0.5)
