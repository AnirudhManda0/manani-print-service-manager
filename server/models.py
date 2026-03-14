from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class PrintJobCreate(BaseModel):
    computer_name: str = Field(..., min_length=1, max_length=120)
    printer_name: str = Field(..., min_length=1, max_length=255)
    document_name: str = Field(default="", max_length=500)
    pages: int = Field(..., ge=0, le=100000)
    print_type: Literal["black_and_white", "color"] = "black_and_white"
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


class DataRetentionExecute(BaseModel):
    mode: Literal["archive_30_days", "delete_30_days"]
    days: int = Field(default=30, ge=1, le=3650)
