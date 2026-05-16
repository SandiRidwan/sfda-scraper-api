# app/schemas/models.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ─── Request Models ─────────────────────────────────────

class ScrapeRequest(BaseModel):
    max_pages: Optional[int] = None  # None = scrape semua halaman
    notify_telegram: bool = True     # Kirim notif Telegram saat selesai?


# ─── Response Models ────────────────────────────────────

class JobStatus(BaseModel):
    id: str
    status: str          # queued | running | done | failed
    total_pages: int
    done_pages: int
    total_drugs: int
    progress_pct: float  # 0.0 – 100.0
    error: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[float] = None


class DrugRecord(BaseModel):
    registration_no: str
    trade_name: Optional[str] = None
    scientific_name: Optional[str] = None
    manufacturer: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    license_holder: Optional[str] = None
    dosage_form: Optional[str] = None
    route: Optional[str] = None
    strength: Optional[str] = None


class DrugListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: list[DrugRecord]


class HealthResponse(BaseModel):
    status: str
    environment: str
    database: str
    version: str = "1.0.0"