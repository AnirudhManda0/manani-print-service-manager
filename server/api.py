"""FastAPI service layer for PrintX.

The desktop UI talks only to this API client/server boundary.
All persistence and business rules are delegated to server.database.Database.
"""

import os
import time
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request

from autostart import get_status as get_autostart_status, set_enabled as set_autostart_enabled
from branding import APP_API_TITLE, DEFAULT_DATABASE_NAME
from runtime_config import load_config_file, save_config_file
from server.database import Database
from server.models import (
    DataRetentionExecute,
    PrintJobCreate,
    PrintJobTypeUpdate,
    ServiceCatalogCreate,
    ServiceRecordCreate,
    SettingsUpdate,
    SystemConfigUpdate,
)

logger = logging.getLogger(__name__)


def create_app(
    db_path: str,
    schema_path: str,
    config_path: Optional[str] = None,
    app_version: str = "1.0.0",
) -> FastAPI:
    """Create configured FastAPI app bound to one Database instance."""
    db = Database(db_path=db_path, schema_path=schema_path)
    app = FastAPI(title=APP_API_TITLE, version=app_version)
    backup_check_state = {"last_check": 0.0}
    cfg_path = config_path or os.path.join(os.path.dirname(os.path.dirname(db_path)), "config", "settings.json")

    # Keep pricing in sync with runtime config defaults for first-run and portable deployments.
    try:
        runtime_cfg = load_config_file(cfg_path)
        current = db.get_settings()
        db.update_settings(
            bw_price_per_page=float(runtime_cfg.get("bw_price_per_page", current.get("bw_price_per_page", 2.0))),
            color_price_per_page=float(runtime_cfg.get("color_price_per_page", current.get("color_price_per_page", 10.0))),
            currency=str(current.get("currency", "INR")),
            retention_mode=str(current.get("retention_mode", "retain_all")),
            retention_days=int(current.get("retention_days", 30)),
            backup_enabled=bool(current.get("backup_enabled", True)),
            backup_folder=str(current.get("backup_folder", "backup")),
        )
    except Exception as config_exc:
        logger.warning("Could not sync runtime config pricing to DB settings: %s", config_exc)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logger(request: Request, call_next):
        # API middleware centralizes request timing logs and periodic backup checks.
        start = time.perf_counter()
        try:
            now = time.time()
            if now - backup_check_state["last_check"] > 300:
                backup_check_state["last_check"] = now
                try:
                    db.run_daily_backup(force=False)
                except Exception as backup_exc:
                    logger.warning("Daily backup check failed: %s", backup_exc)
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "API %s %s -> %s (%.2f ms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception("API %s %s failed (%.2f ms)", request.method, request.url.path, duration_ms)
            raise

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": app_version}

    @app.get("/api/version")
    def get_version() -> dict:
        return {"version": app_version}

    @app.get("/api/system-config")
    def get_system_config() -> dict:
        cfg = load_config_file(cfg_path)
        autostart = get_autostart_status()
        return {
            "server_ip": cfg.get("server_ip", "127.0.0.1"),
            "server_port": int(cfg.get("server_port", 8787)),
            "auto_discovery_enabled": bool(cfg.get("auto_discovery_enabled", True)),
            "discovery_port": int(cfg.get("discovery_port", 8788)),
            "computer_name": cfg.get("computer_name", ""),
            "operator_id": cfg.get("operator_id", "ADMIN"),
            "autostart_enabled": bool(cfg.get("autostart_enabled", autostart.get("enabled", False))),
            "autostart_supported": bool(autostart.get("supported", False)),
            "autostart_registry_enabled": bool(autostart.get("registry_enabled", False)),
            "autostart_startup_shortcut_enabled": bool(autostart.get("startup_shortcut_enabled", False)),
            "poll_interval": float(cfg.get("poll_interval", 0.5)),
            "bw_price_per_page": float(cfg.get("bw_price_per_page", 2.0)),
            "color_price_per_page": float(cfg.get("color_price_per_page", 10.0)),
        }

    @app.put("/api/system-config")
    def update_system_config(payload: SystemConfigUpdate) -> dict:
        cfg = load_config_file(cfg_path)
        cfg.update(
            {
                "server_ip": payload.server_ip.strip(),
                "server_port": int(payload.server_port),
                "auto_discovery_enabled": bool(payload.auto_discovery_enabled),
                "discovery_port": int(payload.discovery_port),
                "computer_name": payload.computer_name.strip() or cfg.get("computer_name", ""),
                "operator_id": payload.operator_id.strip() or cfg.get("operator_id", "ADMIN"),
                "autostart_enabled": bool(payload.autostart_enabled),
                "poll_interval": float(payload.poll_interval),
                "bw_price_per_page": float(payload.bw_price_per_page),
                "color_price_per_page": float(payload.color_price_per_page),
            }
        )
        saved = save_config_file(cfg_path, cfg)
        autostart_state = set_autostart_enabled(bool(saved.get("autostart_enabled", False)))
        autostart = get_autostart_status()
        return {
            "server_ip": saved.get("server_ip"),
            "server_port": int(saved.get("server_port", 8787)),
            "auto_discovery_enabled": bool(saved.get("auto_discovery_enabled", True)),
            "discovery_port": int(saved.get("discovery_port", 8788)),
            "computer_name": saved.get("computer_name"),
            "operator_id": saved.get("operator_id", "ADMIN"),
            "autostart_enabled": autostart_state,
            "autostart_supported": bool(autostart.get("supported", False)),
            "autostart_registry_enabled": bool(autostart.get("registry_enabled", False)),
            "autostart_startup_shortcut_enabled": bool(autostart.get("startup_shortcut_enabled", False)),
            "poll_interval": float(saved.get("poll_interval", 0.5)),
            "bw_price_per_page": float(saved.get("bw_price_per_page", 2.0)),
            "color_price_per_page": float(saved.get("color_price_per_page", 10.0)),
        }

    @app.get("/api/settings")
    def get_settings() -> dict:
        return db.get_settings()

    @app.put("/api/settings")
    def update_settings(payload: SettingsUpdate) -> dict:
        # Settings affect pricing, retention, and backup behavior used by billing/reporting.
        result = db.update_settings(
            bw_price_per_page=payload.bw_price_per_page,
            color_price_per_page=payload.color_price_per_page,
            currency=payload.currency,
            retention_mode=payload.retention_mode,
            retention_days=payload.retention_days,
            backup_enabled=payload.backup_enabled,
            backup_folder=payload.backup_folder,
        )
        try:
            cfg = load_config_file(cfg_path)
            cfg["bw_price_per_page"] = float(payload.bw_price_per_page)
            cfg["color_price_per_page"] = float(payload.color_price_per_page)
            save_config_file(cfg_path, cfg)
        except Exception as exc:
            logger.warning("Could not persist pricing to settings.json: %s", exc)
        return result

    @app.post("/api/print-jobs")
    def add_print_job(payload: PrintJobCreate) -> dict:
        # Print monitor pushes captured spooler jobs here.
        return db.add_print_job(
            operator_id=payload.operator_id,
            computer_name=payload.computer_name,
            printer_name=payload.printer_name,
            document_name=payload.document_name,
            source_job_key=payload.source_job_key,
            pages=payload.pages,
            print_type=payload.print_type,
            paper_size=payload.paper_size,
            timestamp=payload.timestamp,
        )

    @app.get("/api/print-jobs")
    def get_print_jobs(
        date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
        limit: int = Query(default=300, ge=1, le=5000),
    ) -> dict:
        return {"items": db.list_print_jobs(limit=limit, date_filter=date)}

    @app.delete("/api/print-jobs/{job_id}")
    def delete_print_job(job_id: int) -> dict:
        deleted = db.delete_print_job(job_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"print job {job_id} not found")
        return {"deleted": True, "id": job_id}

    @app.put("/api/print-jobs/{job_id}/type")
    def update_print_job_type(job_id: int, payload: PrintJobTypeUpdate) -> dict:
        try:
            return db.update_print_job_type(job_id=job_id, print_type=payload.print_type)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/dashboard")
    def get_dashboard(date: Optional[str] = Query(default=None, description="YYYY-MM-DD")) -> dict:
        # Dashboard is a daily summary view; UI updates cards from this payload.
        return db.get_dashboard(day=date)

    @app.get("/api/services/catalog")
    def list_service_catalog() -> dict:
        return {"items": db.list_services_catalog()}

    @app.get("/api/services/records")
    def list_service_records(
        date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
        limit: int = Query(default=200, ge=1, le=5000),
    ) -> dict:
        return {"items": db.list_service_records(limit=limit, date_filter=date)}

    @app.post("/api/services/catalog")
    def add_service_catalog(payload: ServiceCatalogCreate) -> dict:
        try:
            return db.add_service_catalog(payload.service_name, payload.default_price)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/services/record")
    def add_service_record(payload: ServiceRecordCreate) -> dict:
        try:
            return db.record_service(payload.service_id, payload.price, payload.timestamp)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/reports/{period}")
    def get_report(period: str, date: Optional[str] = Query(default=None, description="YYYY-MM-DD")) -> dict:
        # Reporting endpoint backs daily/weekly/monthly report screen.
        if period not in {"daily", "weekly", "monthly"}:
            raise HTTPException(status_code=400, detail="period must be daily, weekly, or monthly")
        try:
            return db.get_report(period=period, day=date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/data-retention/status")
    def get_data_retention_status(days: int = Query(default=30, ge=1, le=3650)) -> dict:
        return db.get_retention_status(days=days)

    @app.post("/api/data-retention/execute")
    def execute_data_retention(payload: DataRetentionExecute) -> dict:
        if payload.mode == "archive_30_days":
            return db.archive_old_records(days=payload.days)
        if payload.mode == "delete_30_days":
            return db.delete_old_records(days=payload.days)
        raise HTTPException(status_code=400, detail="Unsupported retention mode")

    @app.post("/api/backup/run")
    def run_daily_backup(force: bool = Query(default=False)) -> dict:
        # Manual trigger used by Settings panel and background periodic checks.
        return db.run_daily_backup(force=force)

    @app.on_event("shutdown")
    def _shutdown() -> None:
        db.close()

    return app


if __name__ == "__main__":
    import uvicorn

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    version_path = os.path.join(root, "version.txt")
    version = "1.0.0"
    if os.path.exists(version_path):
        with open(version_path, "r", encoding="utf-8") as handle:
            version = handle.read().strip() or version
    app = create_app(
        db_path=os.path.join(root, "database", DEFAULT_DATABASE_NAME),
        schema_path=os.path.join(root, "database", "schema.sql"),
        config_path=os.path.join(root, "config", "settings.json"),
        app_version=version,
    )
    uvicorn.run(app, host="0.0.0.0", port=8787)
