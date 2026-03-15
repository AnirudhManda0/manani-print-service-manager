"""FastAPI service layer for ManAni Print & Service Manager.

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

from server.database import Database
from server.models import DataRetentionExecute, PrintJobCreate, ServiceCatalogCreate, ServiceRecordCreate, SettingsUpdate

logger = logging.getLogger(__name__)


def create_app(db_path: str, schema_path: str) -> FastAPI:
    """Create configured FastAPI app bound to one Database instance."""
    db = Database(db_path=db_path, schema_path=schema_path)
    app = FastAPI(title="ManAni Print & Service Manager API", version="1.1.0")
    backup_check_state = {"last_check": 0.0}

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
        return {"status": "ok"}

    @app.get("/api/settings")
    def get_settings() -> dict:
        return db.get_settings()

    @app.put("/api/settings")
    def update_settings(payload: SettingsUpdate) -> dict:
        # Settings affect pricing, retention, and backup behavior used by billing/reporting.
        return db.update_settings(
            bw_price_per_page=payload.bw_price_per_page,
            color_price_per_page=payload.color_price_per_page,
            currency=payload.currency,
            retention_mode=payload.retention_mode,
            retention_days=payload.retention_days,
            backup_enabled=payload.backup_enabled,
            backup_folder=payload.backup_folder,
        )

    @app.post("/api/print-jobs")
    def add_print_job(payload: PrintJobCreate) -> dict:
        # Print monitor pushes captured spooler jobs here.
        return db.add_print_job(
            computer_name=payload.computer_name,
            printer_name=payload.printer_name,
            document_name=payload.document_name,
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

    @app.get("/api/dashboard")
    def get_dashboard(date: Optional[str] = Query(default=None, description="YYYY-MM-DD")) -> dict:
        # Dashboard is a daily summary view; UI updates cards from this payload.
        return db.get_dashboard(day=date)

    @app.get("/api/services/catalog")
    def list_service_catalog() -> dict:
        return {"items": db.list_services_catalog()}

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
    app = create_app(
        db_path=os.path.join(root, "database", "cybercafe.db"),
        schema_path=os.path.join(root, "database", "schema.sql"),
    )
    uvicorn.run(app, host="0.0.0.0", port=8787)
