"""LAN discovery helpers for admin server auto-detection.

Clients use UDP broadcast to discover the running admin server when a fixed
server IP is not configured or is temporarily unavailable.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from typing import Dict, List, Optional


logger = logging.getLogger(__name__)

DISCOVERY_REQUEST = "PRINTX_DISCOVER_SERVER_V1"
DISCOVERY_RESPONSE = "PRINTX_DISCOVER_SERVER_RESPONSE_V1"
DEFAULT_DISCOVERY_PORT = 8788


def _make_payload(kind: str, **data: object) -> bytes:
    payload = {"kind": kind}
    payload.update(data)
    return json.dumps(payload).encode("utf-8")


def _parse_payload(raw: bytes) -> Dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8", errors="ignore"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def discover_server_urls(port: int = DEFAULT_DISCOVERY_PORT, timeout: float = 1.2) -> List[str]:
    """Broadcast discovery request and collect distinct server URLs."""
    urls: List[str] = []
    seen = set()
    deadline = time.time() + max(0.2, float(timeout))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", 0))
        sock.settimeout(0.25)
        packet = _make_payload(DISCOVERY_REQUEST)
        for address in ("255.255.255.255", "<broadcast>", "127.0.0.1"):
            try:
                sock.sendto(packet, (address, int(port)))
            except OSError:
                continue

        while time.time() < deadline:
            try:
                raw, _addr = sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break

            payload = _parse_payload(raw)
            if payload.get("kind") != DISCOVERY_RESPONSE:
                continue

            server_url = str(payload.get("server_url") or "").strip()
            if not server_url or server_url in seen:
                continue
            seen.add(server_url)
            urls.append(server_url)
    finally:
        sock.close()
    return urls


class ServerDiscoveryResponder:
    """UDP responder that advertises the admin server URL on the local LAN."""

    def __init__(self, server_url: str, computer_name: str, app_version: str, port: int = DEFAULT_DISCOVERY_PORT) -> None:
        self.server_url = server_url.rstrip("/")
        self.computer_name = computer_name
        self.app_version = app_version
        self.port = int(port)
        self._stop_event = threading.Event()
        self._thread = None  # type: Optional[threading.Thread]

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="server-discovery")
        self._thread.start()
        logger.info("Server discovery responder started on UDP %s for %s", self.port, self.server_url)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", self.port))
            sock.settimeout(1.0)
            response = _make_payload(
                DISCOVERY_RESPONSE,
                server_url=self.server_url,
                computer_name=self.computer_name,
                version=self.app_version,
            )
            while not self._stop_event.is_set():
                try:
                    raw, address = sock.recvfrom(2048)
                except socket.timeout:
                    continue
                except OSError:
                    break

                payload = _parse_payload(raw)
                if payload.get("kind") != DISCOVERY_REQUEST:
                    continue

                try:
                    sock.sendto(response, address)
                except OSError:
                    continue
        except OSError as exc:
            logger.warning("Server discovery responder could not bind UDP %s: %s", self.port, exc)
        finally:
            try:
                sock.close()
            except Exception:
                pass
