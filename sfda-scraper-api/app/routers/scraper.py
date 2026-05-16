# app/routers/scraper.py
import threading
from fastapi import APIRouter, HTTPException
from app.schemas.models import ScrapeRequest, JobStatus
from app.services.scraper_service import create_job, get_job, run_scraper

router = APIRouter(prefix="/scraper", tags=["Scraper"])


@router.post("/scrape", status_code=202)
async def start_scrape(body: ScrapeRequest):
    """Start scraping job"""
    job_id = create_job()

    # Pakai threading — lebih reliable
    t = threading.Thread(
        target=run_scraper,
        kwargs={
            "job_id": job_id,
            "max_pages": body.max_pages,
            "notify_telegram": body.notify_telegram
        },
        daemon=True
    )
    t.start()

    return {
        "job_id": job_id,
        "status": "queued",
        "message": f"Scraping started. Check progress at /scraper/status/{job_id}",
        "telegram_notify": body.notify_telegram
    }


@router.get("/status/{job_id}", response_model=JobStatus)
async def job_status(job_id: str):
    """Get job status"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


@router.get("/results/{job_id}")
async def get_results(
    job_id: str,
    page: int = 1,
    page_size: int = 50,
    search: str = None,
    country: str = None,
    manufacturer: str = None
):
    """Get job results"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] not in ("done", "running"):
        raise HTTPException(
            status_code=400, 
            detail=f"Job status is '{job['status']}' - only 'running' or 'done' allowed"
        )
    
    from app.services.scraper_service import query_drugs
    return query_drugs(job_id, page, page_size, search, country, manufacturer)


@router.get("/export/{job_id}")
async def export_results(job_id: str):
    """Export results to Excel"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="Job not finished yet")
    
    try:
        import os
        import pandas as pd
        from datetime import datetime
        from app.database import get_connection
        
        conn = get_connection()
        rows = conn.execute(
            """SELECT registration_no, trade_name, scientific_name, manufacturer, 
               country, category, status, dosage_form, route, strength
               FROM drugs WHERE job_id=? ORDER BY registration_no""",
            (job_id,)
        ).fetchall()
        conn.close()
        
        if not rows:
            raise ValueError("No drugs found for this job")
        
        df = pd.DataFrame([dict(r) for r in rows])
        df.drop_duplicates(subset=["registration_no"], keep="first", inplace=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os_makedirs = os.makedirs("exports", exist_ok=True)
        output_file = f"exports/sfda_drugs_{job_id}_{timestamp}.xlsx"
        
        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Drugs", index=False)
            ws = writer.sheets["Drugs"]
            for col in ws.columns:
                max_len = max((len(str(cell.value or "")) for cell in col), default=10)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 45)
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
        
        return {
            "job_id": job_id,
            "file": output_file,
            "total_drugs": len(df),
            "message": f"Exported {len(df)} drugs to Excel"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")