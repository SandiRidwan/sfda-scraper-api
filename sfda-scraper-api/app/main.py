# app/main.py
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import scraper, drugs
from app.schemas.models import HealthResponse

# ─── Logging Setup ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

settings = get_settings()


# ─── Lifespan (startup/shutdown) ────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Kode di sini jalan saat startup. Setelah yield = shutdown."""
    logger.info("Starting SFDA Scraper API...")
    logger.info(f"Environment: {settings.app_env}")
    init_db()  # Buat tabel jika belum ada
    logger.info("Database initialized ✓")
    yield
    logger.info("Shutting down...")


# ─── App Instance ────────────────────────────────────────
app = FastAPI(
    title="SFDA Drug Scraper API",
    description=(
        "REST API untuk scraping dan querying data obat dari "
        "Saudi Food & Drug Authority (SFDA). "
        "Dilengkapi Telegram notifications dan job tracking."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# ─── CORS Middleware ─────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_debug else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────
app.include_router(scraper.router)
app.include_router(drugs.router)


# ─── Root Endpoints ──────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "SFDA Drug Scraper API",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    """Health check — dipakai oleh Docker dan load balancer."""
    try:
        from app.database import get_connection
        conn = get_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        db_status = "ok"
    except Exception:
        db_status = "error"

    return HealthResponse(
        status="ok",
        environment=settings.app_env,
        database=db_status
    )