import os
import sqlite3
import threading
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple


class Database:
    """Thread-safe SQLite access layer used by API and desktop UI."""

    VALID_RETENTION_MODES = {"retain_all", "archive_30_days", "delete_30_days"}

    def __init__(self, db_path: str, schema_path: str) -> None:
        self.db_path = db_path
        self.schema_path = schema_path
        self._lock = threading.RLock()
        parent_dir = os.path.dirname(self.db_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._configure()
        self.initialize()

    def _configure(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.execute("PRAGMA foreign_keys=ON;")
            self._conn.commit()

    def initialize(self) -> None:
        with self._lock:
            with open(self.schema_path, "r", encoding="utf-8") as f:
                self._conn.executescript(f.read())
            self._migrate_schema()
            self._conn.commit()

    def _migrate_schema(self) -> None:
        """Backward-compatible schema migration for existing DB files."""
        columns = {
            row["name"] for row in self._conn.execute("PRAGMA table_info(settings);").fetchall()
        }
        if "retention_mode" not in columns:
            self._conn.execute(
                "ALTER TABLE settings ADD COLUMN retention_mode TEXT NOT NULL DEFAULT 'retain_all';"
            )
        if "retention_days" not in columns:
            self._conn.execute(
                "ALTER TABLE settings ADD COLUMN retention_days INTEGER NOT NULL DEFAULT 30;"
            )

        self._conn.execute(
            """
            INSERT OR IGNORE INTO settings (
                id, bw_price_per_page, color_price_per_page, currency, retention_mode, retention_days
            )
            VALUES (1, 2.0, 10.0, 'INR', 'retain_all', 30);
            """
        )

    @staticmethod
    def _to_db_time(value: Optional[datetime]) -> str:
        dt = value or datetime.now()
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def get_settings(self) -> Dict[str, object]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    bw_price_per_page,
                    color_price_per_page,
                    currency,
                    retention_mode,
                    retention_days
                FROM settings
                WHERE id = 1;
                """
            ).fetchone()
            if row:
                data = dict(row)
                data["retention_mode"] = (
                    data["retention_mode"] if data["retention_mode"] in self.VALID_RETENTION_MODES else "retain_all"
                )
                data["retention_days"] = int(data.get("retention_days", 30) or 30)
                return data
            return {
                "bw_price_per_page": 2.0,
                "color_price_per_page": 10.0,
                "currency": "INR",
                "retention_mode": "retain_all",
                "retention_days": 30,
            }

    def update_settings(
        self,
        bw_price_per_page: float,
        color_price_per_page: float,
        currency: str,
        retention_mode: str = "retain_all",
        retention_days: int = 30,
    ) -> Dict[str, object]:
        safe_mode = retention_mode if retention_mode in self.VALID_RETENTION_MODES else "retain_all"
        safe_days = max(1, int(retention_days))
        with self._lock:
            self._conn.execute(
                """
                UPDATE settings
                SET
                    bw_price_per_page = ?,
                    color_price_per_page = ?,
                    currency = ?,
                    retention_mode = ?,
                    retention_days = ?
                WHERE id = 1;
                """,
                (bw_price_per_page, color_price_per_page, currency, safe_mode, safe_days),
            )
            self._conn.commit()
        return self.get_settings()

    def add_print_job(
        self,
        computer_name: str,
        printer_name: str,
        document_name: str,
        pages: int,
        print_type: str,
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, object]:
        safe_pages = max(0, int(pages))
        safe_type = "color" if print_type == "color" else "black_and_white"
        settings = self.get_settings()
        price_per_page = settings["color_price_per_page"] if safe_type == "color" else settings["bw_price_per_page"]
        total_cost = round(float(price_per_page) * safe_pages, 2)
        ts = self._to_db_time(timestamp)

        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO print_jobs
                (computer_name, printer_name, document_name, pages, print_type, price_per_page, total_cost, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (computer_name, printer_name, document_name, safe_pages, safe_type, float(price_per_page), total_cost, ts),
            )
            self._conn.commit()
            job_id = cursor.lastrowid

        return {
            "id": job_id,
            "computer_name": computer_name,
            "printer_name": printer_name,
            "document_name": document_name,
            "pages": safe_pages,
            "print_type": safe_type,
            "price_per_page": float(price_per_page),
            "total_cost": total_cost,
            "timestamp": ts,
        }

    def list_print_jobs(self, limit: int = 300, date_filter: Optional[str] = None) -> List[Dict[str, object]]:
        sql = """
            SELECT id, computer_name, printer_name, document_name, pages, print_type, price_per_page, total_cost, timestamp
            FROM print_jobs
        """
        params: Tuple[object, ...]
        if date_filter:
            sql += " WHERE date(timestamp) = date(?) "
            params = (date_filter,)
        else:
            params = tuple()
        sql += " ORDER BY timestamp DESC LIMIT ?;"
        params = params + (int(limit),)

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def add_service_catalog(self, service_name: str, default_price: float) -> Dict[str, object]:
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO services_catalog (service_name, default_price)
                VALUES (?, ?);
                """,
                (service_name.strip(), float(default_price)),
            )
            self._conn.commit()
            item_id = cursor.lastrowid
        return {"id": item_id, "service_name": service_name.strip(), "default_price": float(default_price)}

    def list_services_catalog(self) -> List[Dict[str, object]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, service_name, default_price FROM services_catalog ORDER BY service_name ASC;"
            ).fetchall()
        return [dict(r) for r in rows]

    def record_service(
        self,
        service_id: int,
        price: Optional[float] = None,
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, object]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, service_name, default_price FROM services_catalog WHERE id = ?;",
                (service_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"service_id {service_id} does not exist")

            final_price = float(price) if price is not None else float(row["default_price"])
            ts = self._to_db_time(timestamp)
            cursor = self._conn.execute(
                """
                INSERT INTO service_records (service_id, price, timestamp)
                VALUES (?, ?, ?);
                """,
                (service_id, final_price, ts),
            )
            self._conn.commit()
            rec_id = cursor.lastrowid

        return {
            "id": rec_id,
            "service_id": int(row["id"]),
            "service_name": row["service_name"],
            "price": final_price,
            "timestamp": ts,
        }

    def _revenue_between(self, start_ts: str, end_ts: str) -> Dict[str, float]:
        with self._lock:
            print_row = self._conn.execute(
                """
                SELECT
                    COUNT(*) AS total_print_jobs,
                    COALESCE(SUM(pages), 0) AS total_pages,
                    COALESCE(SUM(CASE WHEN print_type='black_and_white' THEN pages ELSE 0 END), 0) AS bw_pages,
                    COALESCE(SUM(CASE WHEN print_type='color' THEN pages ELSE 0 END), 0) AS color_pages,
                    COALESCE(SUM(total_cost), 0) AS printing_revenue,
                    COALESCE(AVG(pages), 0) AS avg_pages_per_job
                FROM print_jobs
                WHERE timestamp >= ? AND timestamp < ?;
                """,
                (start_ts, end_ts),
            ).fetchone()

            service_row = self._conn.execute(
                """
                SELECT
                    COUNT(*) AS total_services,
                    COALESCE(SUM(price), 0) AS service_revenue,
                    COALESCE(AVG(price), 0) AS avg_service_price
                FROM service_records
                WHERE timestamp >= ? AND timestamp < ?;
                """,
                (start_ts, end_ts),
            ).fetchone()

        print_jobs = int(print_row["total_print_jobs"])
        printing_revenue = round(float(print_row["printing_revenue"]), 2)
        return {
            "total_print_jobs": print_jobs,
            "total_pages": int(print_row["total_pages"]),
            "bw_pages": int(print_row["bw_pages"]),
            "color_pages": int(print_row["color_pages"]),
            "printing_revenue": printing_revenue,
            "avg_pages_per_job": round(float(print_row["avg_pages_per_job"]), 2),
            "avg_revenue_per_job": round((printing_revenue / print_jobs), 2) if print_jobs else 0.0,
            "total_services": int(service_row["total_services"]),
            "service_revenue": round(float(service_row["service_revenue"]), 2),
            "avg_service_price": round(float(service_row["avg_service_price"]), 2),
        }

    def _service_breakdown_between(self, start_ts: str, end_ts: str) -> List[Dict[str, object]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT
                    sc.service_name,
                    COUNT(sr.id) AS count,
                    COALESCE(SUM(sr.price), 0) AS revenue
                FROM service_records sr
                JOIN services_catalog sc ON sc.id = sr.service_id
                WHERE sr.timestamp >= ? AND sr.timestamp < ?
                GROUP BY sr.service_id, sc.service_name
                ORDER BY sc.service_name ASC;
                """,
                (start_ts, end_ts),
            ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _range_from_period(period: str, anchor_date: Optional[str]) -> Tuple[str, str, str]:
        if anchor_date:
            base_date = datetime.strptime(anchor_date, "%Y-%m-%d").date()
        else:
            base_date = date.today()

        if period == "daily":
            start = base_date
            end = base_date + timedelta(days=1)
            label = start.isoformat()
        elif period == "weekly":
            start = base_date - timedelta(days=base_date.weekday())
            end = start + timedelta(days=7)
            label = f"{start.isoformat()} to {(end - timedelta(days=1)).isoformat()}"
        elif period == "monthly":
            start = base_date.replace(day=1)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
            label = start.strftime("%Y-%m")
        else:
            raise ValueError("period must be one of: daily, weekly, monthly")

        start_ts = f"{start.isoformat()} 00:00:00"
        end_ts = f"{end.isoformat()} 00:00:00"
        return start_ts, end_ts, label

    def get_dashboard(self, day: Optional[str] = None) -> Dict[str, object]:
        start_ts, end_ts, label = self._range_from_period("daily", day)
        revenue = self._revenue_between(start_ts, end_ts)
        total = round(revenue["printing_revenue"] + revenue["service_revenue"], 2)
        settings = self.get_settings()
        return {
            "date": label,
            **revenue,
            "total_revenue": total,
            "currency": settings["currency"],
        }

    def get_report(self, period: str, day: Optional[str] = None) -> Dict[str, object]:
        start_ts, end_ts, label = self._range_from_period(period, day)
        revenue = self._revenue_between(start_ts, end_ts)
        services = self._service_breakdown_between(start_ts, end_ts)
        total = round(revenue["printing_revenue"] + revenue["service_revenue"], 2)
        settings = self.get_settings()
        return {
            "period": period,
            "label": label,
            "start": start_ts,
            "end": end_ts,
            "currency": settings["currency"],
            "summary": {
                **revenue,
                "total_revenue": total,
            },
            "services_breakdown": services,
        }

    def get_retention_status(self, days: int = 30) -> Dict[str, object]:
        safe_days = max(1, int(days))
        cutoff = (datetime.now() - timedelta(days=safe_days)).strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            print_count = self._conn.execute(
                "SELECT COUNT(*) AS c FROM print_jobs WHERE timestamp < ?;", (cutoff,)
            ).fetchone()["c"]
            service_count = self._conn.execute(
                "SELECT COUNT(*) AS c FROM service_records WHERE timestamp < ?;", (cutoff,)
            ).fetchone()["c"]
            oldest_print = self._conn.execute("SELECT MIN(timestamp) AS ts FROM print_jobs;").fetchone()["ts"]
            oldest_service = self._conn.execute("SELECT MIN(timestamp) AS ts FROM service_records;").fetchone()["ts"]

        total_old = int(print_count) + int(service_count)
        return {
            "days": safe_days,
            "cutoff_timestamp": cutoff,
            "old_print_jobs": int(print_count),
            "old_service_records": int(service_count),
            "total_old_records": total_old,
            "has_old_data": total_old > 0,
            "oldest_print_timestamp": oldest_print,
            "oldest_service_timestamp": oldest_service,
        }

    def _ensure_archive_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS archive_db.print_jobs (
                id INTEGER PRIMARY KEY,
                computer_name TEXT NOT NULL,
                printer_name TEXT NOT NULL,
                document_name TEXT,
                pages INTEGER NOT NULL,
                print_type TEXT NOT NULL,
                price_per_page REAL NOT NULL,
                total_cost REAL NOT NULL,
                timestamp DATETIME NOT NULL
            );
            CREATE TABLE IF NOT EXISTS archive_db.services_catalog (
                id INTEGER PRIMARY KEY,
                service_name TEXT NOT NULL UNIQUE,
                default_price REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS archive_db.service_records (
                id INTEGER PRIMARY KEY,
                service_id INTEGER NOT NULL,
                price REAL NOT NULL,
                timestamp DATETIME NOT NULL
            );
            CREATE TABLE IF NOT EXISTS archive_db.archive_meta (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                cutoff_timestamp TEXT NOT NULL,
                archived_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS archive_db.idx_print_jobs_timestamp ON print_jobs (timestamp);
            CREATE INDEX IF NOT EXISTS archive_db.idx_service_records_timestamp ON service_records (timestamp);
            CREATE INDEX IF NOT EXISTS archive_db.idx_service_records_service_id ON service_records (service_id);
            """
        )

    def archive_old_records(self, days: int = 30, archive_db_path: Optional[str] = None) -> Dict[str, object]:
        safe_days = max(1, int(days))
        cutoff = (datetime.now() - timedelta(days=safe_days)).strftime("%Y-%m-%d %H:%M:%S")
        archive_path = archive_db_path or os.path.join(os.path.dirname(self.db_path), "cybercafe_archive.db")
        os.makedirs(os.path.dirname(archive_path), exist_ok=True)

        with self._lock:
            self._conn.execute("ATTACH DATABASE ? AS archive_db;", (archive_path,))
            try:
                self._ensure_archive_schema()
                print_count = int(
                    self._conn.execute(
                        "SELECT COUNT(*) AS c FROM print_jobs WHERE timestamp < ?;", (cutoff,)
                    ).fetchone()["c"]
                )
                service_count = int(
                    self._conn.execute(
                        "SELECT COUNT(*) AS c FROM service_records WHERE timestamp < ?;", (cutoff,)
                    ).fetchone()["c"]
                )

                if print_count == 0 and service_count == 0:
                    self._conn.execute("DETACH DATABASE archive_db;")
                    return {
                        "action": "archive",
                        "archive_db_path": archive_path,
                        "archived_print_jobs": 0,
                        "archived_service_records": 0,
                        "cutoff_timestamp": cutoff,
                    }

                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO archive_db.services_catalog (id, service_name, default_price)
                    SELECT sc.id, sc.service_name, sc.default_price
                    FROM services_catalog sc
                    WHERE sc.id IN (
                        SELECT DISTINCT service_id
                        FROM service_records
                        WHERE timestamp < ?
                    );
                    """,
                    (cutoff,),
                )

                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO archive_db.print_jobs (
                        id, computer_name, printer_name, document_name, pages, print_type, price_per_page, total_cost, timestamp
                    )
                    SELECT
                        id, computer_name, printer_name, document_name, pages, print_type, price_per_page, total_cost, timestamp
                    FROM print_jobs
                    WHERE timestamp < ?;
                    """,
                    (cutoff,),
                )

                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO archive_db.service_records (id, service_id, price, timestamp)
                    SELECT id, service_id, price, timestamp
                    FROM service_records
                    WHERE timestamp < ?;
                    """,
                    (cutoff,),
                )

                self._conn.execute("DELETE FROM service_records WHERE timestamp < ?;", (cutoff,))
                self._conn.execute("DELETE FROM print_jobs WHERE timestamp < ?;", (cutoff,))
                self._conn.execute(
                    """
                    INSERT INTO archive_db.archive_meta (action, cutoff_timestamp, archived_at)
                    VALUES ('archive', ?, ?);
                    """,
                    (cutoff, self._to_db_time(None)),
                )
                self._conn.commit()
                self._conn.execute("DETACH DATABASE archive_db;")
            except Exception:
                self._conn.rollback()
                self._conn.execute("DETACH DATABASE archive_db;")
                raise

        return {
            "action": "archive",
            "archive_db_path": archive_path,
            "archived_print_jobs": print_count,
            "archived_service_records": service_count,
            "cutoff_timestamp": cutoff,
        }

    def delete_old_records(self, days: int = 30) -> Dict[str, object]:
        safe_days = max(1, int(days))
        cutoff = (datetime.now() - timedelta(days=safe_days)).strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            print_count = int(
                self._conn.execute(
                    "SELECT COUNT(*) AS c FROM print_jobs WHERE timestamp < ?;", (cutoff,)
                ).fetchone()["c"]
            )
            service_count = int(
                self._conn.execute(
                    "SELECT COUNT(*) AS c FROM service_records WHERE timestamp < ?;", (cutoff,)
                ).fetchone()["c"]
            )
            self._conn.execute("DELETE FROM service_records WHERE timestamp < ?;", (cutoff,))
            self._conn.execute("DELETE FROM print_jobs WHERE timestamp < ?;", (cutoff,))
            self._conn.commit()

        return {
            "action": "delete",
            "deleted_print_jobs": print_count,
            "deleted_service_records": service_count,
            "cutoff_timestamp": cutoff,
        }
