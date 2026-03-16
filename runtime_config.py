"""Runtime configuration helpers for settings.json.

This module keeps JSON config handling centralized for:
- startup loading
- API-backed settings edits
- backward compatibility with legacy nested config
"""

import json
import os
import socket
from typing import Any, Dict
from urllib.parse import urlparse


DEFAULT_CONFIG: Dict[str, Any] = {
    "mode": "single",
    "server_ip": "127.0.0.1",
    "server_port": 8787,
    "computer_name": "",
    "operator_id": "ADMIN",
    "poll_interval": 0.5,
    "bw_price_per_page": 2.0,
    "color_price_per_page": 10.0,
    "database_path": "database/cybercafe.db",
    "print_monitor_enabled": True,
}


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_server_url(config: Dict[str, Any]) -> str:
    return f"http://{config['server_ip']}:{int(config['server_port'])}"


def normalize_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    cfg["computer_name"] = socket.gethostname()

    mode = str(raw.get("mode", cfg["mode"])) if isinstance(raw, dict) else cfg["mode"]
    cfg["mode"] = mode if mode in {"single", "server", "client"} else "single"

    if not isinstance(raw, dict):
        raw = {}

    # Preferred flat keys.
    if raw.get("server_ip"):
        cfg["server_ip"] = str(raw["server_ip"]).strip() or cfg["server_ip"]
    if raw.get("server_port") is not None:
        cfg["server_port"] = _safe_int(raw.get("server_port"), cfg["server_port"])
    if raw.get("computer_name"):
        cfg["computer_name"] = str(raw.get("computer_name")).strip() or cfg["computer_name"]
    if raw.get("operator_id"):
        cfg["operator_id"] = str(raw.get("operator_id")).strip() or cfg["operator_id"]
    if raw.get("poll_interval") is not None:
        cfg["poll_interval"] = _safe_float(raw.get("poll_interval"), cfg["poll_interval"])
    if raw.get("bw_price_per_page") is not None:
        cfg["bw_price_per_page"] = _safe_float(raw.get("bw_price_per_page"), cfg["bw_price_per_page"])
    if raw.get("color_price_per_page") is not None:
        cfg["color_price_per_page"] = _safe_float(raw.get("color_price_per_page"), cfg["color_price_per_page"])
    if raw.get("database_path"):
        cfg["database_path"] = str(raw.get("database_path")).strip() or cfg["database_path"]
    if raw.get("print_monitor_enabled") is not None:
        cfg["print_monitor_enabled"] = bool(raw.get("print_monitor_enabled"))

    # Legacy nested keys compatibility.
    api_cfg = raw.get("api")
    if isinstance(api_cfg, dict):
        if api_cfg.get("host"):
            cfg["server_ip"] = str(api_cfg.get("host")).strip() or cfg["server_ip"]
        if api_cfg.get("port") is not None:
            cfg["server_port"] = _safe_int(api_cfg.get("port"), cfg["server_port"])

    monitor_cfg = raw.get("print_monitor")
    if isinstance(monitor_cfg, dict):
        if monitor_cfg.get("poll_interval_seconds") is not None:
            cfg["poll_interval"] = _safe_float(monitor_cfg.get("poll_interval_seconds"), cfg["poll_interval"])
        if monitor_cfg.get("enabled") is not None:
            cfg["print_monitor_enabled"] = bool(monitor_cfg.get("enabled"))

    db_cfg = raw.get("database")
    if isinstance(db_cfg, dict) and db_cfg.get("path"):
        cfg["database_path"] = str(db_cfg.get("path")).strip() or cfg["database_path"]

    central_url = str(raw.get("central_server_url", "") or "").strip()
    if central_url and ("server_ip" not in raw and "server_port" not in raw):
        parsed = urlparse(central_url)
        if parsed.hostname:
            cfg["server_ip"] = parsed.hostname
        if parsed.port:
            cfg["server_port"] = parsed.port

    # Guardrails.
    if not (1 <= cfg["server_port"] <= 65535):
        cfg["server_port"] = DEFAULT_CONFIG["server_port"]
    cfg["poll_interval"] = max(0.1, cfg["poll_interval"])
    cfg["bw_price_per_page"] = max(0.0, cfg["bw_price_per_page"])
    cfg["color_price_per_page"] = max(0.0, cfg["color_price_per_page"])
    cfg["operator_id"] = str(cfg.get("operator_id", "ADMIN")).strip() or "ADMIN"

    # Backward-compatible computed nodes used by existing code.
    cfg["api"] = {"host": cfg["server_ip"], "port": cfg["server_port"]}
    cfg["database"] = {"path": cfg["database_path"]}
    cfg["print_monitor"] = {
        "enabled": cfg["print_monitor_enabled"],
        "poll_interval_seconds": cfg["poll_interval"],
    }
    cfg["central_server_url"] = build_server_url(cfg)
    return cfg


def serialize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_config(config)
    return {
        "mode": normalized["mode"],
        "server_ip": normalized["server_ip"],
        "server_port": normalized["server_port"],
        "computer_name": normalized["computer_name"],
        "operator_id": normalized["operator_id"],
        "poll_interval": normalized["poll_interval"],
        "bw_price_per_page": normalized["bw_price_per_page"],
        "color_price_per_page": normalized["color_price_per_page"],
        "database_path": normalized["database_path"],
        "print_monitor_enabled": normalized["print_monitor_enabled"],
    }


def load_config_file(config_path: str) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    if not os.path.exists(config_path):
        data = normalize_config({})
        save_config_file(config_path, data)
        return data

    with open(config_path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return normalize_config(raw)


def save_config_file(config_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    data = serialize_config(config)
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    return normalize_config(data)
