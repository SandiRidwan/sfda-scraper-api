# app/database.py
import sqlite3
import os
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Extract database path dari settings
if settings.database_url.startswith("sqlite:///"):
    DB_PATH = settings.database_url.replace("sqlite:///", "")
else:
    DB_PATH = settings.database_url

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """Buat koneksi SQLite. Dipanggil per request."""
    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False  # Wajib untuk FastAPI (multi-thread)
    )
    conn.row_factory = sqlite3.Row  # Hasil query bisa diakses seperti dict
    return conn


def init_db():
    """Buat semua tabel jika belum ada. Dipanggil saat startup."""
    conn = get_connection()
    try:
        conn.executescript("""
            -- Tabel untuk tracking scraping jobs
            CREATE TABLE IF NOT EXISTS jobs (
                id          TEXT PRIMARY KEY,
                status      TEXT DEFAULT 'queued',
                total_pages INTEGER DEFAULT 0,
                done_pages  INTEGER DEFAULT 0,
                total_drugs INTEGER DEFAULT 0,
                error       TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                started_at  TEXT,
                finished_at TEXT
            );

            -- Tabel untuk data obat hasil scraping
            CREATE TABLE IF NOT EXISTS drugs (
                job_id          TEXT,
                registration_no TEXT,
                trade_name      TEXT,
                scientific_name TEXT,
                manufacturer    TEXT,
                country         TEXT,
                category        TEXT,
                status          TEXT,
                license_holder  TEXT,
                dosage_form     TEXT,
                route           TEXT,
                strength        TEXT,
                PRIMARY KEY (job_id, registration_no)
            );

            -- Index untuk query cepat
            CREATE INDEX IF NOT EXISTS idx_drugs_job_id
                ON drugs(job_id);
            CREATE INDEX IF NOT EXISTS idx_drugs_trade_name
                ON drugs(trade_name);
            CREATE INDEX IF NOT EXISTS idx_drugs_manufacturer
                ON drugs(manufacturer);
            CREATE INDEX IF NOT EXISTS idx_drugs_country
                ON drugs(country);
            CREATE INDEX IF NOT EXISTS idx_drugs_registration_no
                ON drugs(registration_no);
        """)
        conn.commit()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database init error: {e}")
        raise
    finally:
        conn.close()