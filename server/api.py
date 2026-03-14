import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from server.database import Database
from server.models import DataRetentionExecute, PrintJobCreate, ServiceCatalogCreate, ServiceRecordCreate, SettingsUpdate


def create_app(db_path: str, schema_path: str) -> FastAPI:
    db = Database(db_path=db_path, schema_path=schema_path)
    app = FastAPI(title="CyberCafe Print & Service Manager API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/settings")
    def get_settings() -> dict:
        return db.get_settings()

    @app.put("/api/settings")
    def update_settings(payload: SettingsUpdate) -> dict:
        return db.update_settings(
            bw_price_per_page=payload.bw_price_per_page,
            color_price_per_page=payload.color_price_per_page,
            currency=payload.currency,
            retention_mode=payload.retention_mode,
            retention_days=payload.retention_days,
        )

    @app.post("/api/print-jobs")
    def add_print_job(payload: PrintJobCreate) -> dict:
        return db.add_print_job(
            computer_name=payload.computer_name,
            printer_name=payload.printer_name,
            document_name=payload.document_name,
            pages=payload.pages,
            print_type=payload.print_type,
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
