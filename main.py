"""Application entrypoint and runtime orchestrator.

Responsibilities:
- Configure logging
- Resolve packaged/development resource paths
- Ensure runtime folders/files exist
- Start API server, print monitor, and desktop UI based on selected mode
"""

import argparse
import json
import logging
import os
import shutil
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional

import requests
import uvicorn

from client.print_monitor import PrintMonitor, run_background_client
from server.api import create_app


DEFAULT_CONFIG = {
    "mode": "single",
    "api": {"host": "127.0.0.1", "port": 8787},
    "database": {"path": "database/cybercafe.db"},
    "print_monitor": {"enabled": True, "poll_interval_seconds": 0.5},
    "central_server_url": "http://127.0.0.1:8787",
}


def configure_logging() -> None:
    """Configure console + rotating file logs for production and packaged runtime."""
    logs_dir = os.path.join(install_root(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, "application.log")
    level_name = os.environ.get("MANANI_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def resource_path(relative_path):
    """Resolve data files from source tree (dev) or PyInstaller bundle (_MEIPASS)."""
    if getattr(sys, "frozen", False):
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def install_root() -> str:
    """Return writable runtime base folder (exe folder when frozen)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def bundled_root() -> str:
    """Return bundle extraction path when frozen, else project root."""
    return getattr(sys, "_MEIPASS", install_root())


def _copy_if_missing(source: str, destination: str) -> None:
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    if not os.path.exists(destination) and os.path.exists(source):
        shutil.copy2(source, destination)


def ensure_runtime_files() -> None:
    """Create runtime folders and copy bundled defaults if missing.

    This keeps the EXE portable: dropping the executable in any folder is enough.
    """
    runtime = install_root()
    bundle = bundled_root()

    os.makedirs(os.path.join(runtime, "config"), exist_ok=True)
    os.makedirs(os.path.join(runtime, "database"), exist_ok=True)
    os.makedirs(os.path.join(runtime, "logs"), exist_ok=True)
    os.makedirs(os.path.join(runtime, "backup"), exist_ok=True)

    config_dst = os.path.join(runtime, "config", "settings.json")
    schema_dst = os.path.join(runtime, "database", "schema.sql")
    config_src = os.path.join(bundle, "config", "settings.json")
    schema_src = os.path.join(bundle, "database", "schema.sql")

    _copy_if_missing(config_src, config_dst)
    _copy_if_missing(schema_src, schema_dst)

    if not os.path.exists(config_dst):
        with open(config_dst, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)

    if not os.path.exists(schema_dst):
        raise FileNotFoundError(f"schema.sql missing at {schema_dst}")


def resolve_runtime_path(configured_path: str) -> str:
    """Resolve relative config paths against runtime root for portability."""
    expanded = os.path.expandvars(os.path.expanduser(configured_path))
    if os.path.isabs(expanded):
        return expanded
    return os.path.join(install_root(), expanded)


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    ensure_runtime_files()
    default_config_path = os.path.join(install_root(), "config", "settings.json")
    final_path = config_path or default_config_path
    with open(final_path, "r", encoding="utf-8") as f:
        return json.load(f)


class APIServerThread:
    """Runs FastAPI/Uvicorn in a background thread so UI can stay responsive."""
    def __init__(self, db_path: str, schema_path: str, host: str, port: int) -> None:
        self.app = create_app(db_path=db_path, schema_path=schema_path)
        self.config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="warning",
            log_config=None,
        )
        self.server = uvicorn.Server(self.config)
        self.thread = threading.Thread(target=self.server.run, daemon=True, name="api-server")

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


def wait_for_api(base_url: str, retries: int = 30, delay: float = 0.3) -> bool:
    """Poll health endpoint until API is ready."""
    for _ in range(retries):
        try:
            if requests.get(f"{base_url}/health", timeout=1).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(delay)
    return False


def run_with_ui(api_url: str, monitor: Optional[PrintMonitor] = None) -> None:
    """Start Qt event loop and connect UI to API."""
    from PySide6.QtWidgets import QApplication

    from ui.api_client import APIClient
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    client = APIClient(api_url)
    window = MainWindow(client)
    window.show()
    exit_code = app.exec()
    if monitor:
        monitor.stop()
    raise SystemExit(exit_code)


def _runtime_paths(config: Dict[str, Any]) -> Dict[str, str]:
    """Build concrete DB/schema paths for the current runtime environment."""
    return {
        "db_path": resolve_runtime_path(config.get("database", {}).get("path", "database/cybercafe.db")),
        "schema_path": resource_path("database/schema.sql"),
    }


def _ui_api_url(host: str, port: int) -> str:
    # 0.0.0.0 is a bind host, not a UI client target.
    connect_host = "127.0.0.1" if host == "0.0.0.0" else host
    return f"http://{connect_host}:{port}"


def run_single_mode(config: Dict[str, Any]) -> None:
    """Single-PC mode: API + monitor + UI all on one machine."""
    paths = _runtime_paths(config)
    host = config["api"]["host"]
    port = int(config["api"]["port"])
    api_url = _ui_api_url(host, port)

    server = APIServerThread(db_path=paths["db_path"], schema_path=paths["schema_path"], host=host, port=port)
    server.start()
    if not wait_for_api(api_url):
        raise RuntimeError("API server did not start in time.")

    monitor = None
    if config.get("print_monitor", {}).get("enabled", True):
        monitor = PrintMonitor(
            api_base_url=api_url,
            poll_interval=float(config.get("print_monitor", {}).get("poll_interval_seconds", 0.5)),
        )
        monitor.start()

    try:
        run_with_ui(api_url, monitor=monitor)
    finally:
        if monitor:
            monitor.stop()
        server.stop()


def run_server_mode(config: Dict[str, Any], with_ui: bool = True) -> None:
    """Central server mode with optional UI."""
    paths = _runtime_paths(config)
    host = config["api"]["host"]
    port = int(config["api"]["port"])
    api_url = _ui_api_url(host, port)

    if with_ui:
        server = APIServerThread(db_path=paths["db_path"], schema_path=paths["schema_path"], host=host, port=port)
        server.start()
        if not wait_for_api(api_url):
            raise RuntimeError("API server did not start in time.")

        monitor = None
        if config.get("print_monitor", {}).get("enabled", True):
            monitor = PrintMonitor(
                api_base_url=api_url,
                poll_interval=float(config.get("print_monitor", {}).get("poll_interval_seconds", 0.5)),
            )
            monitor.start()

        try:
            run_with_ui(api_url=api_url, monitor=monitor)
        finally:
            if monitor:
                monitor.stop()
            server.stop()
    else:
        app = create_app(db_path=paths["db_path"], schema_path=paths["schema_path"])
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            log_config=None,
        )


def run_client_mode(config: Dict[str, Any], server_url: Optional[str] = None) -> None:
    """Client-only mode for remote PCs that only monitor printers and send jobs."""
    target = server_url or config.get("central_server_url", "http://127.0.0.1:8787")
    run_background_client(target, poll_interval=float(config.get("print_monitor", {}).get("poll_interval_seconds", 0.5)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ManAni Print & Service Manager")
    parser.add_argument("--mode", choices=["single", "server", "client"], default=None)
    parser.add_argument("--config", default=None, help="Path to settings.json")
    parser.add_argument("--headless", action="store_true", help="Server mode only: start API without desktop UI")
    parser.add_argument("--server-url", default=None, help="Client mode only: central server URL")
    return parser.parse_args()


def main() -> None:
    """Parse CLI args and dispatch the selected run mode."""
    configure_logging()
    args = parse_args()
    config = load_config(args.config)
    mode = args.mode or config.get("mode", "single")

    if mode == "single":
        run_single_mode(config)
    elif mode == "server":
        run_server_mode(config, with_ui=not args.headless)
    elif mode == "client":
        run_client_mode(config, server_url=args.server_url)
    else:
        raise ValueError("Unsupported mode")


if __name__ == "__main__":
    main()
