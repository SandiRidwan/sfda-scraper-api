# app/services/scraper_service.py — DOCKER ANTI-BLOCK VERSION
#
# Root cause JSON parse error after ~40 pages in Docker:
# Server returns HTML error page (rate limit / IP block) instead of JSON
# Fix: detect HTML response early + longer delays + session warmup

import uuid
import time
import random
import sqlite3
import logging
import json
from datetime import datetime
from typing import Optional, Tuple, Dict, List

from curl_cffi import requests as cffi_requests

from app.database import get_connection
from app.config import get_settings
from app.services.telegram_service import (
    notify_job_started, notify_job_done, notify_job_failed, notify_milestone
)

logger = logging.getLogger(__name__)
settings = get_settings()

SFDA_API = "https://www.sfda.gov.sa/GetDrugs.php"
SFDA_HOME = "https://www.sfda.gov.sa/en/drugs-list"

HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.sfda.gov.sa/en/drugs-list",
}


# ─────────────────────────────────────────────────────────────
# SESSION — dengan warmup untuk Docker IP
# ─────────────────────────────────────────────────────────────

def create_session(warmup: bool = False) -> cffi_requests.Session:
    """
    Create curl_cffi session dengan optional warmup.
    Warmup = kunjungi homepage dulu sebelum hit API
    Ini penting untuk Docker karena cold IP tidak punya cookie/session history
    """
    session = cffi_requests.Session(impersonate="chrome120")

    if warmup:
        try:
            logger.info("🌐 Session warmup: visiting SFDA homepage...")
            # Visit homepage dulu — establish cookies + session
            r = session.get(
                SFDA_HOME,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                },
                timeout=20
            )
            logger.info(f"   Warmup status: {r.status_code} | cookies: {len(session.cookies)}")
            # Jeda setelah warmup
            time.sleep(random.uniform(2.0, 4.0))
        except Exception as e:
            logger.warning(f"   Warmup failed (non-fatal): {e}")

    logger.debug("✅ Created curl_cffi session (chrome120)")
    return session


# ─────────────────────────────────────────────────────────────
# RESPONSE VALIDATOR
# ─────────────────────────────────────────────────────────────

def validate_response(r) -> Tuple[Optional[List], Optional[str]]:
    """
    Validate response sebelum parse JSON.
    Server kadang return HTML error page saat rate limit — harus detect dini.
    """
    # Cek content type
    ct = r.headers.get("content-type", "").lower()

    if "text/html" in ct:
        # Server return HTML bukan JSON = rate limited / blocked
        snippet = r.text[:200].strip()
        logger.warning(f"⚠ Server returned HTML (rate limited?): {snippet[:80]}")
        return None, "HTML_RESPONSE"

    # Cek response kosong
    if not r.text or len(r.text.strip()) < 10:
        return None, "EMPTY_RESPONSE"

    # Cek apakah mulai dengan { atau [ (valid JSON)
    first_char = r.text.strip()[0]
    if first_char not in ('{', '['):
        snippet = r.text[:100].strip()
        logger.warning(f"⚠ Non-JSON response starts with '{first_char}': {snippet}")
        return None, f"NON_JSON_RESPONSE"

    try:
        data = r.json()
        result = data.get("data", {}).get("result", {})
        if not result or "results" not in result:
            return None, "INVALID_STRUCTURE"

        results = result.get("results", [])
        if isinstance(results, dict):
            results = list(results.values())

        return results, None

    except json.JSONDecodeError as e:
        return None, f"JSON_DECODE: {str(e)[:50]}"


# ─────────────────────────────────────────────────────────────
# FETCH PAGE
# ─────────────────────────────────────────────────────────────

def fetch_page(
    page: int,
    session: cffi_requests.Session,
    max_retries: int = 7,
    base_delay: float = 2.0,
    is_docker: bool = True
) -> Tuple[List[Dict], Optional[str]]:
    """
    Fetch dengan adaptive retry.
    is_docker=True → pakai delay lebih panjang untuk hindari rate limit
    """

    for attempt in range(max_retries):
        try:
            timeout = 30 + (attempt * 5)

            if attempt > 0:
                delay = base_delay * (2 ** (attempt - 1)) + random.uniform(1.0, 3.0)
                logger.debug(f"⏳ Page {page} retry in {delay:.1f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(delay)

            logger.debug(f"📡 Page {page} attempt {attempt+1}: POST [timeout={timeout}s]")

            r = session.post(
                SFDA_API,
                data={
                    "TradeName": "",
                    "Agent": "",
                    "ManufacturerName": "",
                    "RegNo": "",
                    "page": page
                },
                headers=HEADERS,
                timeout=timeout
            )

            logger.debug(f"   [HTTP {r.status_code}] CT: {r.headers.get('content-type','?')[:40]}")
            r.raise_for_status()

            # Validate response
            results, err = validate_response(r)

            if err == "HTML_RESPONSE":
                # Rate limited — long cooldown
                cooldown = 30.0 + (attempt * 15.0)
                logger.warning(f"🚫 Rate limited on page {page} — cooling down {cooldown:.0f}s")
                time.sleep(cooldown)
                continue

            if err:
                logger.warning(f"⚠ Page {page}: {err}")
                if attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                return [], err

            if results:
                logger.info(f"✅ Page {page}: {len(results)} drugs | attempt {attempt+1}")
                return results, None
            else:
                if attempt < max_retries - 1:
                    continue
                return [], "Empty results after max retries"

        except Exception as e:
            error = str(e)[:60]
            logger.warning(f"⚠ Page {page} attempt {attempt+1}: {error}")
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
            return [], error

    return [], f"Failed after {max_retries} attempts"


# ─────────────────────────────────────────────────────────────
# JOB MANAGEMENT
# ─────────────────────────────────────────────────────────────

def create_job() -> str:
    job_id = str(uuid.uuid4())[:8]
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO jobs (id, status, total_pages, done_pages, total_drugs, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (job_id, "queued", 0, 0, 0)
        )
        conn.commit()
        logger.info(f"✓ Job {job_id} created")
        return job_id
    finally:
        conn.close()


def get_job(job_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return None
        job = dict(row)
        job["progress_pct"] = (
            round((job["done_pages"] / job["total_pages"]) * 100, 1)
            if job["total_pages"] > 0 else 0.0
        )
        return job
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# EXTRACT & SAVE
# ─────────────────────────────────────────────────────────────

def extract_drug_fields(drug: Dict) -> Optional[Dict]:
    if not isinstance(drug, dict):
        return None

    company = drug.get("company") or {}
    country = company.get("country") or {}
    drug_type = drug.get("drugType") or {}
    auth_status = drug.get("authorizationStatus") or {}
    route = drug.get("administrationRoute") or {}
    dosage_form = drug.get("pharmaceuticalForm") or {}

    return {
        "registration_no":  str(drug.get("registerNumber", "") or ""),
        "trade_name":       str(drug.get("tradeName", "") or ""),
        "scientific_name":  str(drug.get("scientificName", "") or ""),
        "manufacturer":     str(company.get("nameEn", "") or ""),
        "country":          str(country.get("nameEn", "") or ""),
        "category":         str(drug_type.get("nameEn", "") or ""),
        "status":           str(auth_status.get("nameEn", "") or ""),
        "license_holder":   str(company.get("nameEn", "") or ""),
        "dosage_form":      str(dosage_form.get("nameEn", "") or ""),
        "route":            str(route.get("nameEn", "") or ""),
        "strength":         str(drug.get("strength", "") or ""),
    }


def save_drugs_batch(conn: sqlite3.Connection, job_id: str, drugs: List[Dict]) -> int:
    if not drugs:
        return 0

    rows_to_insert = []
    for drug in drugs:
        extracted = extract_drug_fields(drug)
        if not extracted or not extracted["registration_no"]:
            continue
        rows_to_insert.append((
            job_id,
            extracted["registration_no"],
            extracted["trade_name"],
            extracted["scientific_name"],
            extracted["manufacturer"],
            extracted["country"],
            extracted["category"],
            extracted["status"],
            extracted["license_holder"],
            extracted["dosage_form"],
            extracted["route"],
            extracted["strength"],
        ))

    if not rows_to_insert:
        return 0

    try:
        conn.executemany("""
            INSERT OR IGNORE INTO drugs
            (job_id, registration_no, trade_name, scientific_name,
             manufacturer, country, category, status, license_holder,
             dosage_form, route, strength)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows_to_insert)
        conn.commit()
        return len(rows_to_insert)
    except Exception as e:
        logger.error(f"✗ Save error: {e}")
        conn.rollback()
        return 0


# ─────────────────────────────────────────────────────────────
# MAIN SCRAPER
# ─────────────────────────────────────────────────────────────

def run_scraper(
    job_id: str,
    max_pages: Optional[int] = None,
    notify_telegram: bool = True
):
    """
    Main scraper loop dengan anti-block untuk Docker environment.

    Perbedaan dari versi lokal:
    1. Session warmup — visit homepage dulu untuk establish cookies
    2. HTML response detection — detect rate limit sebelum JSON parse error
    3. Cooldown 30s+ saat rate limited (bukan langsung retry)
    4. Delay lebih panjang: 1.5–3.5s (vs 0.8–2.0s di lokal)
    5. Session rotate setiap 30 pages (bukan 50) untuk Docker
    """

    conn = get_connection()
    # warmup=True untuk Docker — establish cookies dari homepage dulu
    session = create_session(warmup=True)
    start_time = time.time()
    failed_pages = []
    rate_limit_count = 0

    try:
        logger.info(f"🚀 Job {job_id}: START | max_pages={max_pages}")

        # ── FETCH PAGE 1 ──────────────────────────────────────
        first_drugs, error = fetch_page(1, session, max_retries=5, base_delay=3.0)

        if error or not first_drugs:
            raise Exception(f"Page 1 failed: {error}")

        # ── DETERMINE TOTAL PAGES ─────────────────────────────
        total_pages = min(max_pages, settings.sfda_max_pages) if max_pages else settings.sfda_max_pages

        logger.info(f"📊 Total pages to scrape: {total_pages}")

        conn.execute(
            "UPDATE jobs SET status='running', total_pages=?, started_at=datetime('now') WHERE id=?",
            (total_pages, job_id)
        )
        conn.commit()

        # ── SAVE PAGE 1 ───────────────────────────────────────
        saved = save_drugs_batch(conn, job_id, first_drugs)
        total_drugs = saved

        conn.execute(
            "UPDATE jobs SET done_pages=1, total_drugs=? WHERE id=?",
            (total_drugs, job_id)
        )
        conn.commit()

        if notify_telegram:
            notify_job_started(job_id, total_pages)

        # ── SCRAPE PAGES 2+ ───────────────────────────────────
        for page_num in range(2, total_pages + 1):

            # Session rotate setiap 30 pages (lebih agresif untuk Docker)
            if page_num % 30 == 0:
                try:
                    session.close()
                except Exception:
                    pass
                logger.info(f"🔄 Session rotated at page {page_num}")
                session = create_session(warmup=True)  # warmup setiap rotate

            # Adaptive base delay — naik kalau banyak failures
            base_delay = 3.0 + (len(failed_pages) * 0.5) + (rate_limit_count * 2.0)
            base_delay = min(base_delay, 15.0)  # cap 15s

            results, err = fetch_page(
                page_num, session,
                max_retries=7,
                base_delay=base_delay,
                is_docker=True
            )

            if err:
                if "HTML_RESPONSE" in str(err) or "rate" in str(err).lower():
                    rate_limit_count += 1
                logger.warning(f"❌ Page {page_num} failed: {err}")
                failed_pages.append(page_num)
                continue

            if not results:
                logger.warning(f"⚠️  Page {page_num} empty — stopping")
                break

            saved_count = save_drugs_batch(conn, job_id, results)
            total_drugs += saved_count

            conn.execute(
                "UPDATE jobs SET done_pages=?, total_drugs=? WHERE id=?",
                (page_num, total_drugs, job_id)
            )
            conn.commit()

            if page_num % 20 == 0 or page_num <= 5:
                logger.info(f"✓ Page {page_num}/{total_pages} | total: {total_drugs} | "
                            f"failed: {len(failed_pages)} | rate_limits: {rate_limit_count}")
                if notify_telegram and page_num % 100 == 0:
                    notify_milestone(job_id, page_num, total_pages, total_drugs)

            # Delay lebih panjang untuk Docker (1.5–3.5s vs 0.8–2.0s lokal)
            delay = random.uniform(1.5, 3.5)
            time.sleep(delay)

        # ── DONE ──────────────────────────────────────────────
        duration = time.time() - start_time

        conn.execute(
            "UPDATE jobs SET status='done', finished_at=datetime('now'), total_drugs=?, done_pages=? WHERE id=?",
            (total_drugs, total_pages, job_id)
        )
        conn.commit()

        logger.info(f"✅ Job {job_id} DONE: {total_drugs} drugs in {duration:.0f}s")
        if failed_pages:
            logger.info(f"   Failed pages: {failed_pages[:20]}")
        if rate_limit_count > 0:
            logger.info(f"   Rate limit hits: {rate_limit_count}")

        if notify_telegram:
            notify_job_done(job_id, total_drugs, duration, total_pages)

    except Exception as e:
        logger.error(f"❌ Job {job_id} FAILED: {e}", exc_info=True)
        conn.execute(
            "UPDATE jobs SET status='failed', error=?, finished_at=datetime('now') WHERE id=?",
            (str(e)[:500], job_id)
        )
        conn.commit()
        if notify_telegram:
            notify_job_failed(job_id, str(e))

    finally:
        try:
            session.close()
        except Exception:
            pass
        conn.close()


# ─────────────────────────────────────────────────────────────
# QUERY
# ─────────────────────────────────────────────────────────────

def query_drugs(
    job_id: str,
    page: int = 1,
    page_size: int = 50,
    search: Optional[str] = None,
    country: Optional[str] = None,
    manufacturer: Optional[str] = None
) -> dict:
    conn = get_connection()
    try:
        conditions = ["job_id = ?"]
        params = [job_id]

        if search:
            conditions.append("(trade_name LIKE ? OR scientific_name LIKE ? OR registration_no LIKE ?)")
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term])

        if country:
            conditions.append("country = ?")
            params.append(country)

        if manufacturer:
            conditions.append("manufacturer LIKE ?")
            params.append(f"%{manufacturer}%")

        where = " AND ".join(conditions)
        total = conn.execute(f"SELECT COUNT(*) FROM drugs WHERE {where}", params).fetchone()[0]

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""SELECT registration_no, trade_name, scientific_name, manufacturer, country,
               category, status, license_holder, dosage_form, route, strength
               FROM drugs WHERE {where}
               ORDER BY registration_no
               LIMIT ? OFFSET ?""",
            params + [page_size, offset]
        ).fetchall()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
            "data": [dict(r) for r in rows]
        }
    finally:
        conn.close()