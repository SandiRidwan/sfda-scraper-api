# app/services/telegram_service.py
import requests
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

TELEGRAM_API = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """
    Kirim pesan ke Telegram.
    Teknik advance: pakai HTML parse_mode untuk formatting rapi.
    Tidak raise exception — return False jika gagal (agar tidak crash main app).
    """
    try:
        resp = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": settings.telegram_chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            },
            timeout=10
        )
        if resp.status_code == 200:
            logger.info("Telegram message sent successfully")
            return True
        else:
            logger.error(f"Telegram error: {resp.status_code} — {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False  # Tidak crash app utama


def notify_job_started(job_id: str, total_pages: int):
    text = (
        "🚀 <b>Scraping Job Started</b>\n\n"
        f"📋 Job ID: <code>{job_id}</code>\n"
        f"📄 Pages to scrape: <b>{total_pages}</b>\n"
        f"🎯 Target: SFDA Drug Registry\n\n"
        "⏳ Will notify when complete..."
    )
    send_message(text)


def notify_job_done(job_id: str, total_drugs: int, duration_seconds: float,
                    pages_done: int):
    minutes = int(duration_seconds // 60)
    seconds = int(duration_seconds % 60)
    text = (
        "✅ <b>Scraping Job Complete!</b>\n\n"
        f"📋 Job ID: <code>{job_id}</code>\n"
        f"💊 Total drugs scraped: <b>{total_drugs:,}</b>\n"
        f"📄 Pages processed: <b>{pages_done}</b>\n"
        f"⏱️ Duration: <b>{minutes}m {seconds}s</b>\n\n"
        "📊 Query results at: <code>GET /drugs</code>"
    )
    send_message(text)


def notify_job_failed(job_id: str, error: str):
    text = (
        "❌ <b>Scraping Job Failed</b>\n\n"
        f"📋 Job ID: <code>{job_id}</code>\n"
        f"⚠️ Error: <code>{error[:200]}</code>\n\n"
        "Check logs for details."
    )
    send_message(text)


def notify_milestone(job_id: str, done_pages: int, total_pages: int,
                     drugs_so_far: int):
    """
    Kirim update progress setiap 100 halaman.
    Teknik advance: milestone notification agar klien tahu progress tanpa polling API.
    """
    pct = (done_pages / total_pages) * 100
    text = (
        f"📊 <b>Progress Update</b>\n\n"
        f"Job: <code>{job_id}</code>\n"
        f"Progress: <b>{done_pages}/{total_pages} pages ({pct:.1f}%)</b>\n"
        f"Drugs found so far: <b>{drugs_so_far:,}</b>"
    )
    send_message(text)