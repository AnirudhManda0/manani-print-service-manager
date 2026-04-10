"""Thread-safe SQLite data layer.

This module owns:
- schema initialization/migration
- billing calculations (Decimal-based)
- dashboard/report aggregation queries
- retention/archive operations
- daily backup creation

API handlers call into this class; UI never accesses SQLite directly.
"""

import os
import sqlite3
import threading
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple

import logging

from branding import DEFAULT_ARCHIVE_DATABASE_NAME, DEFAULT_BACKUP_PREFIX


logger = logging.getLogger(__name__)

MONEY_QUANT = Decimal("0.01")


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
        self._conn = None
        try:
            self._open_connection()
        except sqlite3.DatabaseError as exc:
            corrupt_path = self._quarantine_corrupt_database()
            logger.exception("Database error detected. Existing DB moved to %s and a fresh DB was created.", corrupt_path)
            self._open_connection()

    def _open_connection(self) -> None:
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._configure()
        self.initialize()

    def _quarantine_corrupt_database(self) -> str:
        corrupt_path = f"{self.db_path}.corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        try:
            if self._conn is not None:
                self._conn.close()
        except Exception:
            pass
        if os.path.exists(self.db_path):
            os.replace(self.db_path, corrupt_path)
        return corrupt_path

    @staticmethod
    def _to_decimal(value: object, fallback: str = "0") -> Decimal:
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal(fallback)

    @classmethod
    def _money(cls, value: object) -> Decimal:
        return cls._to_decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

    @staticmethod
    def _money_float(value: Decimal) -> float:
        return float(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))

    @staticmethod
    def _normalize_paper_size(paper_size: Optional[str]) -> str:
        if not paper_size:
            return "Unknown"
        token = str(paper_size).strip().upper()
        if token == "A3":
            return "A3"
        if token == "A4":
            return "A4"
        if token == "LETTER":
            return "Letter"
        return "Unknown"

    @staticmethod
    def _safe_backup_folder(value: Optional[str]) -> str:
        candidate = (value or "backup").strip()
        return candidate or "backup"

    def _configure(self) -> None:
        """Apply SQLite pragmas for reliability and concurrent read/write behavior."""
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.execute("PRAGMA foreign_keys=ON;")
            self._conn.commit()

    def initialize(self) -> None:
        """Load schema and apply backward-compatible migrations for existing databases."""
        with self._lock:
            with open(self.schema_path, "r", encoding="utf-8") as f:
                self._conn.executescript(f.read())
            self._migrate_schema()
            self._conn.commit()

    def _table_columns(self, table_name: str) -> set:
        return {row["name"] for row in self._conn.execute(f"PRAGMA table_info({table_name});").fetchall()}

    def _migrate_schema(self) -> None:
        """Backward-compatible schema migration for existing DB files."""
        settings_columns = self._table_columns("settings")
        if "retention_mode" not in settings_columns:
            self._conn.execute("ALTER TABLE settings ADD COLUMN retention_mode TEXT NOT NULL DEFAULT 'retain_all';")
        if "retention_days" not in settings_columns:
            self._conn.execute("ALTER TABLE settings ADD COLUMN retention_days INTEGER NOT NULL DEFAULT 30;")
        if "backup_enabled" not in settings_columns:
            self._conn.execute("ALTER TABLE settings ADD COLUMN backup_enabled INTEGER NOT NULL DEFAULT 1;")
        if "backup_folder" not in settings_columns:
            self._conn.execute("ALTER TABLE settings ADD COLUMN backup_folder TEXT NOT NULL DEFAULT 'backup';")
        if "last_backup_date" not in settings_columns:
            self._conn.execute("ALTER TABLE settings ADD COLUMN last_backup_date TEXT NOT NULL DEFAULT '';")

        print_columns = self._table_columns("print_jobs")
        if "operator_id" not in print_columns:
            self._conn.execute("ALTER TABLE print_jobs ADD COLUMN operator_id TEXT NOT NULL DEFAULT 'ADMIN';")
        if "source_job_key" not in print_columns:
            self._conn.execute("ALTER TABLE print_jobs ADD COLUMN source_job_key TEXT NOT NULL DEFAULT '';")
        if "paper_size" not in print_columns:
            self._conn.execute("ALTER TABLE print_jobs ADD COLUMN paper_size TEXT NOT NULL DEFAULT 'Unknown';")
        # Preserve the first occurrence of duplicate source keys so unique index can be created safely.
        self._conn.execute(
            """
            UPDATE print_jobs
            SET source_job_key = ''
            WHERE source_job_key <> ''
              AND id NOT IN (
                  SELECT MIN(id)
                  FROM print_jobs
                  WHERE source_job_key <> ''
                  GROUP BY source_job_key
              );
            """
        )
        self._conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_print_jobs_source_job_key
            ON print_jobs (source_job_key)
            WHERE source_job_key <> '';
            """
        )
        self._conn.execute(
            """
            UPDATE print_jobs
            SET
                pages = 1,
                total_cost = ROUND(COALESCE(price_per_page, 0), 2)
            WHERE pages IS NULL OR pages <= 0;
            """
        )

        self._conn.execute(
            """
            INSERT OR IGNORE INTO settings (
                id,
                bw_price_per_page,
                color_price_per_page,
                currency,
                retention_mode,
                retention_days,
                backup_enabled,
                backup_folder,
                last_backup_date
            )
            VALUES (1, 2.0, 10.0, 'INR', 'retain_all', 30, 1, 'backup', '');
            """
        )

        default_services = [
            ("PAN Card", 120.0),
            ("Exam Registration", 80.0),
            ("Scanning", 20.0),
            ("Lamination", 30.0),
            ("Photo Printing", 50.0),
        ]
        for service_name, default_price in default_services:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO services_catalog (service_name, default_price)
                VALUES (?, ?);
                """,
                (service_name, float(default_price)),
            )

    @staticmethod
    def _to_db_time(value: Optional[datetime]) -> str:
        dt = value or datetime.now()
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()

    def get_settings(self) -> Dict[str, object]:
        """Return normalized settings used by pricing, retention, and backup logic."""
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    bw_price_per_page,
                    color_price_per_page,
                    currency,
                    retention_mode,
                    retention_days,
                    backup_enabled,
                    backup_folder,
                    last_backup_date
                FROM settings
                WHERE id = 1;
                """
            ).fetchone()
            if row:
                data = dict(row)
                data["retention_mode"] = (
                    data["retention_mode"] if data["retention_mode"] in self.VALID_RETENTION_MODES else "retain_all"
                )
                data["retention_days"] = max(1, int(data.get("retention_days", 30) or 30))
                data["bw_price_per_page"] = self._money_float(self._money(data.get("bw_price_per_page", 2.0)))
                data["color_price_per_page"] = self._money_float(self._money(data.get("color_price_per_page", 10.0)))
                data["currency"] = (str(data.get("currency", "INR") or "INR").strip() or "INR").upper()
                data["backup_enabled"] = bool(int(data.get("backup_enabled", 1) or 0))
                data["backup_folder"] = self._safe_backup_folder(data.get("backup_folder", "backup"))
                data["last_backup_date"] = str(data.get("last_backup_date", "") or "")
                return data
            return {
                "bw_price_per_page": 2.0,
                "color_price_per_page": 10.0,
                "currency": "INR",
                "retention_mode": "retain_all",
                "retention_days": 30,
                "backup_enabled": True,
                "backup_folder": "backup",
                "last_backup_date": "",
            }

    def update_settings(
        self,
        bw_price_per_page: float,
        color_price_per_page: float,
        currency: str,
        retention_mode: str = "retain_all",
        retention_days: int = 30,
        backup_enabled: bool = True,
        backup_folder: str = "backup",
    ) -> Dict[str, object]:
        """Persist settings updates from UI/API.

        Prices are normalized to Decimal precision to keep billing deterministic.
        """
        safe_mode = retention_mode if retention_mode in self.VALID_RETENTION_MODES else "retain_all"
        safe_days = max(1, int(retention_days))
        safe_currency = (currency.strip() or "INR").upper()
        bw_price = self._money(bw_price_per_page)
        color_price = self._money(color_price_per_page)
        backup_flag = 1 if bool(backup_enabled) else 0
        safe_backup_folder = self._safe_backup_folder(backup_folder)
        with self._lock:
            self._conn.execute(
                """
                UPDATE settings
                SET
                    bw_price_per_page = ?,
                    color_price_per_page = ?,
                    currency = ?,
                    retention_mode = ?,
                    retention_days = ?,
                    backup_enabled = ?,
                    backup_folder = ?
                WHERE id = 1;
                """,
                (
                    self._money_float(bw_price),
                    self._money_float(color_price),
                    safe_currency,
                    safe_mode,
                    safe_days,
                    backup_flag,
                    safe_backup_folder,
                ),
            )
            self._conn.commit()

        logger.info(
            "Settings updated: currency=%s bw_price=%s color_price=%s retention=%s/%s backup_enabled=%s backup_folder=%s",
            safe_currency,
            bw_price,
            color_price,
            safe_mode,
            safe_days,
            bool(backup_flag),
            safe_backup_folder,
        )
        return self.get_settings()

    def add_print_job(
        self,
        operator_id: str,
        computer_name: str,
        printer_name: str,
        document_name: str,
        source_job_key: str,
        pages: int,
        print_type: str,
        paper_size: str = "Unknown",
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, object]:
        """Insert one print job and compute immutable billing fields.

        Billing flow:
        - choose price per page based on print_type and current settings
        - calculate total_cost with Decimal
        - store price_per_page/total_cost with the job so history remains stable
        """
        safe_pages = max(1, int(pages))
        safe_type = "color" if print_type == "color" else "black_and_white"
        safe_paper_size = self._normalize_paper_size(paper_size)
        safe_operator = (str(operator_id or "ADMIN").strip() or "ADMIN")[:120]
        safe_source_key = (str(source_job_key or "").strip())[:500]
        settings = self.get_settings()
        price_per_page = (
            self._money(settings["color_price_per_page"])
            if safe_type == "color"
            else self._money(settings["bw_price_per_page"])
        )
        total_cost = (price_per_page * Decimal(safe_pages)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        ts = self._to_db_time(timestamp)

        if safe_source_key:
            with self._lock:
                existing = self._conn.execute(
                    """
                    SELECT
                        id,
                        operator_id,
                        computer_name,
                        printer_name,
                        document_name,
                        source_job_key,
                        pages,
                        print_type,
                        paper_size,
                        price_per_page,
                        total_cost,
                        timestamp
                    FROM print_jobs
                    WHERE source_job_key = ?
                    LIMIT 1;
                    """,
                    (safe_source_key,),
                ).fetchone()
            if existing:
                logger.info(
                    "Duplicate print job skipped by source_job_key: key=%s id=%s computer=%s printer=%s",
                    safe_source_key,
                    existing["id"],
                    existing["computer_name"],
                    existing["printer_name"],
                )
                return dict(existing)

        with self._lock:
            try:
                cursor = self._conn.execute(
                    """
                    INSERT INTO print_jobs
                    (operator_id, computer_name, printer_name, document_name, source_job_key, pages, print_type, paper_size, price_per_page, total_cost, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        safe_operator,
                        computer_name,
                        printer_name,
                        document_name,
                        safe_source_key,
                        safe_pages,
                        safe_type,
                        safe_paper_size,
                        self._money_float(price_per_page),
                        self._money_float(total_cost),
                        ts,
                    ),
                )
                self._conn.commit()
                job_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                if not safe_source_key:
                    raise
                existing = self._conn.execute(
                    """
                    SELECT
                        id,
                        operator_id,
                        computer_name,
                        printer_name,
                        document_name,
                        source_job_key,
                        pages,
                        print_type,
                        paper_size,
                        price_per_page,
                        total_cost,
                        timestamp
                    FROM print_jobs
                    WHERE source_job_key = ?
                    LIMIT 1;
                    """,
                    (safe_source_key,),
                ).fetchone()
                if existing:
                    logger.info(
                        "Duplicate print job ignored on insert conflict: key=%s id=%s",
                        safe_source_key,
                        existing["id"],
                    )
                    return dict(existing)
                raise

        logger.info(
            "Print job captured: id=%s operator=%s computer=%s printer=%s pages=%s type=%s paper=%s total=%s source_key=%s",
            job_id,
            safe_operator,
            computer_name,
            printer_name,
            safe_pages,
            safe_type,
            safe_paper_size,
            total_cost,
            safe_source_key or "-",
        )
        return {
            "id": job_id,
            "operator_id": safe_operator,
            "computer_name": computer_name,
            "printer_name": printer_name,
            "document_name": document_name,
            "source_job_key": safe_source_key,
            "pages": safe_pages,
            "print_type": safe_type,
            "paper_size": safe_paper_size,
            "price_per_page": self._money_float(price_per_page),
            "total_cost": self._money_float(total_cost),
            "timestamp": ts,
        }

    def list_print_jobs(self, limit: int = 300, date_filter: Optional[str] = None) -> List[Dict[str, object]]:
        sql = """
            SELECT
                id,
                operator_id,
                computer_name,
                printer_name,
                document_name,
                source_job_key,
                pages,
                print_type,
                paper_size,
                price_per_page,
                total_cost,
                timestamp
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

    def delete_print_job(self, job_id: int) -> bool:
        """Delete one print transaction by id."""
        with self._lock:
            cursor = self._conn.execute("DELETE FROM print_jobs WHERE id = ?;", (int(job_id),))
            self._conn.commit()
            deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Print job deleted: id=%s", job_id)
        return deleted

    def update_print_job_type(self, job_id: int, print_type: str) -> Dict[str, object]:
        """Correct one print job classification and recalculate billing safely."""
        safe_type = "color" if print_type == "color" else "black_and_white"
        settings = self.get_settings()
        price_per_page = (
            self._money(settings["color_price_per_page"])
            if safe_type == "color"
            else self._money(settings["bw_price_per_page"])
        )
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    id,
                    operator_id,
                    computer_name,
                    printer_name,
                    document_name,
                    source_job_key,
                    pages,
                    print_type,
                    paper_size,
                    timestamp
                FROM print_jobs
                WHERE id = ?;
                """,
                (int(job_id),),
            ).fetchone()
            if row is None:
                raise ValueError(f"print job {job_id} not found")

            total_cost = (price_per_page * Decimal(int(row["pages"]))).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
            self._conn.execute(
                """
                UPDATE print_jobs
                SET print_type = ?, price_per_page = ?, total_cost = ?
                WHERE id = ?;
                """,
                (
                    safe_type,
                    self._money_float(price_per_page),
                    self._money_float(total_cost),
                    int(job_id),
                ),
            )
            self._conn.commit()

        logger.info("Print job type corrected: id=%s new_type=%s total=%s", job_id, safe_type, total_cost)
        return {
            "id": int(row["id"]),
            "operator_id": row["operator_id"],
            "computer_name": row["computer_name"],
            "printer_name": row["printer_name"],
            "document_name": row["document_name"],
            "source_job_key": row["source_job_key"],
            "pages": int(row["pages"]),
            "print_type": safe_type,
            "paper_size": row["paper_size"],
            "price_per_page": self._money_float(price_per_page),
            "total_cost": self._money_float(total_cost),
            "timestamp": row["timestamp"],
        }

    def add_service_catalog(self, service_name: str, default_price: float) -> Dict[str, object]:
        safe_price = self._money(default_price)
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO services_catalog (service_name, default_price)
                VALUES (?, ?);
                """,
                (service_name.strip(), self._money_float(safe_price)),
            )
            self._conn.commit()
            item_id = cursor.lastrowid

        logger.info("Service added: id=%s name=%s default_price=%s", item_id, service_name.strip(), safe_price)
        return {
            "id": item_id,
            "service_name": service_name.strip(),
            "default_price": self._money_float(safe_price),
        }

    def delete_service_catalog(self, service_id: int) -> bool:
        """Safely delete a service catalog item if it specifies no existing records."""
        with self._lock:
            # Check if there are existing records
            row = self._conn.execute("SELECT COUNT(*) AS c FROM service_records WHERE service_id = ?;", (service_id,)).fetchone()
            if row and row["c"] > 0:
                raise ValueError("Cannot delete service because it has existing service records.")

            cursor = self._conn.execute("DELETE FROM services_catalog WHERE id = ?;", (int(service_id),))
            self._conn.commit()
            deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Service catalog deleted: id=%s", service_id)
        return deleted

    def list_services_catalog(self) -> List[Dict[str, object]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, service_name, default_price FROM services_catalog ORDER BY service_name ASC;"
            ).fetchall()
        return [dict(r) for r in rows]

    def list_service_records(self, limit: int = 200, date_filter: Optional[str] = None) -> List[Dict[str, object]]:
        sql = """
            SELECT
                sr.id,
                sr.service_id,
                sc.service_name,
                sr.price,
                sr.timestamp
            FROM service_records sr
            JOIN services_catalog sc ON sc.id = sr.service_id
        """
        params: Tuple[object, ...]
        if date_filter:
            sql += " WHERE date(sr.timestamp) = date(?) "
            params = (date_filter,)
        else:
            params = tuple()
        sql += " ORDER BY sr.timestamp DESC LIMIT ?;"
        params = params + (int(limit),)

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
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

            final_price = self._money(price) if price is not None else self._money(row["default_price"])
            ts = self._to_db_time(timestamp)
            cursor = self._conn.execute(
                """
                INSERT INTO service_records (service_id, price, timestamp)
                VALUES (?, ?, ?);
                """,
                (service_id, self._money_float(final_price), ts),
            )
            self._conn.commit()
            rec_id = cursor.lastrowid

        logger.info("Service recorded: record_id=%s service_id=%s price=%s", rec_id, service_id, final_price)
        return {
            "id": rec_id,
            "service_id": int(row["id"]),
            "service_name": row["service_name"],
            "price": self._money_float(final_price),
            "timestamp": ts,
        }

    def _revenue_between(self, start_ts: str, end_ts: str) -> Dict[str, float]:
        """Aggregate print/service metrics for dashboard/report windows."""
        with self._lock:
            print_row = self._conn.execute(
                """
                SELECT
                    COUNT(*) AS total_print_jobs,
                    COALESCE(SUM(pages), 0) AS total_pages,
                    COALESCE(SUM(CASE WHEN print_type='black_and_white' THEN pages ELSE 0 END), 0) AS bw_pages,
                    COALESCE(SUM(CASE WHEN print_type='color' THEN pages ELSE 0 END), 0) AS color_pages,
                    COALESCE(SUM(CASE WHEN paper_size='A4' THEN 1 ELSE 0 END), 0) AS a4_print_jobs,
                    COALESCE(SUM(CASE WHEN paper_size='A3' THEN 1 ELSE 0 END), 0) AS a3_print_jobs,
                    COALESCE(SUM(CASE WHEN paper_size='Letter' THEN 1 ELSE 0 END), 0) AS letter_print_jobs,
                    COALESCE(SUM(CASE WHEN paper_size='Unknown' THEN 1 ELSE 0 END), 0) AS unknown_print_jobs,
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
        printing_revenue = self._money(print_row["printing_revenue"])
        service_revenue = self._money(service_row["service_revenue"])
        avg_service_price = self._money(service_row["avg_service_price"])
        return {
            "total_print_jobs": print_jobs,
            "total_pages": int(print_row["total_pages"]),
            "bw_pages": int(print_row["bw_pages"]),
            "color_pages": int(print_row["color_pages"]),
            "a4_print_jobs": int(print_row["a4_print_jobs"]),
            "a3_print_jobs": int(print_row["a3_print_jobs"]),
            "letter_print_jobs": int(print_row["letter_print_jobs"]),
            "unknown_print_jobs": int(print_row["unknown_print_jobs"]),
            "printing_revenue": self._money_float(printing_revenue),
            "avg_pages_per_job": round(float(print_row["avg_pages_per_job"]), 2),
            "avg_revenue_per_job": self._money_float(printing_revenue / print_jobs) if print_jobs else 0.0,
            "total_services": int(service_row["total_services"]),
            "service_revenue": self._money_float(service_revenue),
            "avg_service_price": self._money_float(avg_service_price),
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
        """Daily summary endpoint backing top dashboard cards."""
        start_ts, end_ts, label = self._range_from_period("daily", day)
        revenue = self._revenue_between(start_ts, end_ts)
        total = self._money(Decimal(str(revenue["printing_revenue"])) + Decimal(str(revenue["service_revenue"])))
        settings = self.get_settings()
        return {
            "date": label,
            **revenue,
            "total_revenue": self._money_float(total),
            "currency": settings["currency"],
            "trend_points": self._daily_trend_points(anchor_day=day, days=7),
            "contribution": {
                "printing_revenue": revenue["printing_revenue"],
                "service_revenue": revenue["service_revenue"],
            },
        }

    def _daily_trend_points(self, anchor_day: Optional[str], days: int = 7) -> List[Dict[str, object]]:
        if anchor_day:
            base_day = datetime.strptime(anchor_day, "%Y-%m-%d").date()
        else:
            base_day = date.today()
        points: List[Dict[str, object]] = []
        for offset in range(max(1, int(days)) - 1, -1, -1):
            current_day = base_day - timedelta(days=offset)
            start_ts = f"{current_day.isoformat()} 00:00:00"
            end_ts = f"{(current_day + timedelta(days=1)).isoformat()} 00:00:00"
            revenue = self._revenue_between(start_ts, end_ts)
            total = self._money(
                Decimal(str(revenue["printing_revenue"])) + Decimal(str(revenue["service_revenue"]))
            )
            points.append(
                {
                    "date": current_day.isoformat(),
                    "label": current_day.strftime("%d %b"),
                    "total_revenue": self._money_float(total),
                    "printing_revenue": revenue["printing_revenue"],
                    "service_revenue": revenue["service_revenue"],
                }
            )
        return points

    def _trend_points_for_period(self, period: str, anchor_day: Optional[str]) -> List[Dict[str, object]]:
        if period == "daily":
            return self._daily_trend_points(anchor_day=anchor_day, days=7)

        if anchor_day:
            base_day = datetime.strptime(anchor_day, "%Y-%m-%d").date()
        else:
            base_day = date.today()

        points: List[Dict[str, object]] = []
        if period == "weekly":
            start_of_week = base_day - timedelta(days=base_day.weekday())
            for offset in range(7, -1, -1):
                week_start = start_of_week - timedelta(weeks=offset)
                week_end = week_start + timedelta(days=7)
                revenue = self._revenue_between(
                    f"{week_start.isoformat()} 00:00:00",
                    f"{week_end.isoformat()} 00:00:00",
                )
                total = self._money(
                    Decimal(str(revenue["printing_revenue"])) + Decimal(str(revenue["service_revenue"]))
                )
                points.append(
                    {
                        "date": week_start.isoformat(),
                        "label": f"Wk {week_start.strftime('%d %b')}",
                        "total_revenue": self._money_float(total),
                        "printing_revenue": revenue["printing_revenue"],
                        "service_revenue": revenue["service_revenue"],
                    }
                )
            return points

        if period == "monthly":
            month_start = base_day.replace(day=1)
            for offset in range(5, -1, -1):
                ref = month_start
                for _ in range(offset):
                    ref = (ref.replace(day=1) - timedelta(days=1)).replace(day=1)
                next_month = (ref.replace(day=28) + timedelta(days=4)).replace(day=1)
                revenue = self._revenue_between(
                    f"{ref.isoformat()} 00:00:00",
                    f"{next_month.isoformat()} 00:00:00",
                )
                total = self._money(
                    Decimal(str(revenue["printing_revenue"])) + Decimal(str(revenue["service_revenue"]))
                )
                points.append(
                    {
                        "date": ref.isoformat(),
                        "label": ref.strftime("%b %y"),
                        "total_revenue": self._money_float(total),
                        "printing_revenue": revenue["printing_revenue"],
                        "service_revenue": revenue["service_revenue"],
                    }
                )
            return points

        return self._daily_trend_points(anchor_day=anchor_day, days=7)

    def get_report(self, period: str, day: Optional[str] = None) -> Dict[str, object]:
        """Period report endpoint backing Reports tab."""
        start_ts, end_ts, label = self._range_from_period(period, day)
        revenue = self._revenue_between(start_ts, end_ts)
        services = self._service_breakdown_between(start_ts, end_ts)
        total = self._money(Decimal(str(revenue["printing_revenue"])) + Decimal(str(revenue["service_revenue"])))
        settings = self.get_settings()
        return {
            "period": period,
            "label": label,
            "start": start_ts,
            "end": end_ts,
            "currency": settings["currency"],
            "summary": {
                **revenue,
                "total_revenue": self._money_float(total),
            },
            "trend_points": self._trend_points_for_period(period=period, anchor_day=day),
            "contribution": {
                "printing_revenue": revenue["printing_revenue"],
                "service_revenue": revenue["service_revenue"],
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
                operator_id TEXT NOT NULL DEFAULT 'ADMIN',
                computer_name TEXT NOT NULL,
                printer_name TEXT NOT NULL,
                document_name TEXT,
                pages INTEGER NOT NULL,
                print_type TEXT NOT NULL,
                paper_size TEXT NOT NULL DEFAULT 'Unknown',
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
        archive_columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA archive_db.table_info(print_jobs);").fetchall()
        }
        if "operator_id" not in archive_columns:
            self._conn.execute(
                "ALTER TABLE archive_db.print_jobs ADD COLUMN operator_id TEXT NOT NULL DEFAULT 'ADMIN';"
            )

    def archive_old_records(self, days: int = 30, archive_db_path: Optional[str] = None) -> Dict[str, object]:
        """Move old data to archive database while preserving reporting continuity."""
        safe_days = max(1, int(days))
        cutoff = (datetime.now() - timedelta(days=safe_days)).strftime("%Y-%m-%d %H:%M:%S")
        archive_path = archive_db_path or os.path.join(os.path.dirname(self.db_path), DEFAULT_ARCHIVE_DATABASE_NAME)
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
                        id, operator_id, computer_name, printer_name, document_name, pages, print_type, paper_size, price_per_page, total_cost, timestamp
                    )
                    SELECT
                        id, operator_id, computer_name, printer_name, document_name, pages, print_type, paper_size, price_per_page, total_cost, timestamp
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

        logger.info(
            "Archived old records: cutoff=%s print_jobs=%s service_records=%s path=%s",
            cutoff,
            print_count,
            service_count,
            archive_path,
        )
        return {
            "action": "archive",
            "archive_db_path": archive_path,
            "archived_print_jobs": print_count,
            "archived_service_records": service_count,
            "cutoff_timestamp": cutoff,
        }

    def delete_old_records(self, days: int = 30) -> Dict[str, object]:
        """Permanently delete records older than cutoff period."""
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

        logger.info("Deleted old records: cutoff=%s print_jobs=%s service_records=%s", cutoff, print_count, service_count)
        return {
            "action": "delete",
            "deleted_print_jobs": print_count,
            "deleted_service_records": service_count,
            "cutoff_timestamp": cutoff,
        }

    def _resolve_backup_folder(self, configured_folder: str) -> str:
        expanded = os.path.expandvars(os.path.expanduser(self._safe_backup_folder(configured_folder)))
        if os.path.isabs(expanded):
            return expanded

        db_dir = os.path.dirname(self.db_path)
        project_root = os.path.abspath(os.path.join(db_dir, ".."))
        return os.path.join(project_root, expanded)

    def run_daily_backup(self, force: bool = False) -> Dict[str, object]:
        """Create a dated SQLite backup file once per day (or on force)."""
        with self._lock:
            settings = self.get_settings()
            if not settings.get("backup_enabled", True) and not force:
                return {"status": "disabled", "backup_enabled": False}

            today = date.today().isoformat()
            if not force and settings.get("last_backup_date") == today:
                return {"status": "skipped", "reason": "already_backed_up_today", "date": today}

            backup_folder = self._resolve_backup_folder(str(settings.get("backup_folder", "backup")))
            os.makedirs(backup_folder, exist_ok=True)
            backup_path = os.path.join(backup_folder, f"{DEFAULT_BACKUP_PREFIX}_{today.replace('-', '_')}.db")

            backup_conn = sqlite3.connect(backup_path)
            try:
                self._conn.backup(backup_conn)
                backup_conn.commit()
            finally:
                backup_conn.close()

            self._conn.execute("UPDATE settings SET last_backup_date = ? WHERE id = 1;", (today,))
            self._conn.commit()

        logger.info("Database backup created: %s", backup_path)
        return {
            "status": "created",
            "date": today,
            "backup_path": backup_path,
        }
