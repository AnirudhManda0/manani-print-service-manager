"""Single-instance bridge so relaunching PrintX can show the existing UI."""

import logging
import socket
import threading
from typing import Callable, Optional


logger = logging.getLogger(__name__)

CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 45871
BUFFER_SIZE = 128


def send_control_message(message: str, timeout: float = 0.75) -> bool:
    """Send a small control message to an existing PrintX instance."""
    try:
        with socket.create_connection((CONTROL_HOST, CONTROL_PORT), timeout=timeout) as client:
            client.sendall(message.strip().encode("utf-8"))
            return True
    except OSError:
        return False


class InstanceBridgeServer:
    """Tiny localhost socket server used to reopen the running UI."""

    def __init__(self, on_message: Callable[[str], None]) -> None:
        self.on_message = on_message
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._server_socket: Optional[socket.socket] = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        if self.is_running:
            return True
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((CONTROL_HOST, CONTROL_PORT))
            server.listen(5)
            server.settimeout(0.5)
        except OSError as exc:
            logger.warning("PrintX instance bridge could not bind to %s:%s: %s", CONTROL_HOST, CONTROL_PORT, exc)
            try:
                server.close()
            except OSError:
                pass
            return False

        self._server_socket = server
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="printx-instance-bridge")
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.5)

    def _run(self) -> None:
        assert self._server_socket is not None
        while not self._stop_event.is_set():
            try:
                conn, _addr = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                try:
                    payload = conn.recv(BUFFER_SIZE).decode("utf-8", errors="ignore").strip()
                except OSError:
                    payload = ""
                if payload:
                    try:
                        self.on_message(payload)
                    except Exception:
                        logger.exception("PrintX instance bridge handler failed for payload=%s", payload)
