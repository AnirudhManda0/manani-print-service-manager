from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class PrintJobCreate(BaseModel):
    operator_id: str = Field(default="ADMIN", min_length=1, max_length=120)
    computer_name: str = Field(..., min_length=1, max_length=120)
    printer_name: str = Field(..., min_length=1, max_length=255)
    document_name: str = Field(default="", max_length=500)
    source_job_key: str = Field(default="", max_length=500)
    pages: int = Field(..., ge=1, le=100000)
    print_type: Literal["black_and_white", "color"] = "black_and_white"
    paper_size: Literal["A4", "A3", "Letter", "Unknown"] = "Unknown"
    timestamp: Optional[datetime] = None


class ServiceCatalogCreate(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=200)
    default_price: float = Field(..., ge=0)


class ServiceRecordCreate(BaseModel):
    service_id: int = Field(..., ge=1)
    price: Optional[float] = Field(default=None, ge=0)
    timestamp: Optional[datetime] = None


class SettingsUpdate(BaseModel):
    bw_price_per_page: float = Field(..., ge=0)
    color_price_per_page: float = Field(..., ge=0)
    currency: str = Field(..., min_length=1, max_length=8)
    retention_mode: Literal["retain_all", "archive_30_days", "delete_30_days"] = "retain_all"
    retention_days: int = Field(default=30, ge=1, le=3650)
    backup_enabled: bool = True
    backup_folder: str = Field(default="backup", min_length=1, max_length=260)


class DataRetentionExecute(BaseModel):
    mode: Literal["archive_30_days", "delete_30_days"]
    days: int = Field(default=30, ge=1, le=3650)


class SystemConfigUpdate(BaseModel):
    server_ip: str = Field(..., min_length=1, max_length=255)
    server_port: int = Field(..., ge=1, le=65535)
    computer_name: str = Field(default="", max_length=120)
    operator_id: str = Field(default="ADMIN", min_length=1, max_length=120)
    poll_interval: float = Field(default=0.5, ge=0.1, le=10.0)
    bw_price_per_page: float = Field(..., ge=0)
    color_price_per_page: float = Field(..., ge=0)
