"""
SFDA Drug Scraper v4 — Rate Limit Safe
- curl_cffi (Chrome TLS impersonation)
- Session rotation
- Adaptive delays
- Smart retry logic
"""

from curl_cffi import requests as cffi_requests
import time, random, json, os, sys
import pandas as pd
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────
URL        = "https://www.sfda.gov.sa/GetDrugs.php"
CHECKPOINT = "sfda_checkpoint.json"

HEADERS = {
    "Accept"          : "application/json, text/javascript, */*; q=0.01",
    "Content-Type"    : "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer"         : "https://www.sfda.gov.sa/en/drugs-list",
}

# ── FETCH WITH SMART RETRY ────────────────────────────────────
def fetch_page(page, max_retries=7, base_delay=2.0):
    """
    Fetch dengan adaptive retry + session rotation
    """
    # Create NEW session setiap 50 pages
    if page % 50 == 0:
        global session
        session = cffi_requests.Session(impersonate="chrome120")
        print(f"  🔄 Session rotated at page {page}")
    
    for attempt in range(max_retries):
        try:
            # Adaptive timeout
            timeout = 30 + (attempt * 5)
            
            # Delay sebelum retry
            if attempt > 0:
                delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0.5, 2.0)
                print(f"     ⏳ Retry in {delay:.1f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(delay)
            
            print(f"  📡 Page {page} attempt {attempt+1}: POST... [timeout={timeout}s]", end="", flush=True)
            
            r = session.post(
                URL,
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
            
            print(f" [HTTP {r.status_code}]")
            r.raise_for_status()
            
            # Parse response
            data = r.json()
            result = data.get("data", {}).get("result", {})
            
            # Check if result is valid
            if not result or "results" not in result:
                raise ValueError("Invalid response structure")
            
            results = result.get("results", [])
            
            # Convert dict to list if needed
            if isinstance(results, dict):
                results = list(results.values())
            
            # SUCCESS
            if results:
                print(f"✅ Page {page}: {len(results)} drugs | attempt {attempt+1}")
                return results, None
            else:
                # Empty results
                if attempt < max_retries - 1:
                    print(f"❌ Empty results → Retry")
                    continue
                else:
                    return [], "Empty results after max retries"
        
        except json.JSONDecodeError as e:
            error = f"JSON parse: {str(e)[:30]}"
            print(f" → {error}")
            if attempt < max_retries - 1:
                print(f"     → Retry in {base_delay * (2 ** attempt):.1f}s")
                time.sleep(base_delay * (2 ** attempt))
                continue
            return [], error
        
        except Exception as e:
            error = str(e)[:50]
            print(f" → {error}")
            if attempt < max_retries - 1:
                continue
            return [], error
    
    return [], f"Failed after {max_retries} attempts"

# ── INIT SESSION ──────────────────────────────────────────────
session = cffi_requests.Session(impersonate="chrome120")

# ── STEP 1: CONFIRM PAGINATION ────────────────────────────────
print("=" * 70)
print("STEP 1 — Confirm pagination")
print("=" * 70)

first_drugs = []
total_pages = 0
total_rows  = 0

for pg in [1, 2, 3]:
    results, err = fetch_page(pg, max_retries=3)
    
    if err:
        print(f"❌ Page {pg} failed: {err}")
        sys.exit(1)
    
    first_reg = results[0].get("registerNumber", "?") if results else "?"
    last_reg = results[-1].get("registerNumber", "?") if results else "?"
    
    print(f"  curPage={pg} | first={first_reg} | last={last_reg}\n")
    
    if pg == 1:
        # Extract metadata
        r = session.post(URL, data={"page": 1}, headers=HEADERS, timeout=30)
        meta = r.json().get("data", {}).get("result", {})
        total_pages = meta.get("pageCount", 438)
        total_rows = meta.get("rowCount", 8754)
        page_size = meta.get("pageSize", 20)
        
        print(f"  📊 Metadata:")
        print(f"     Total drugs : {total_rows}")
        print(f"     Total pages : {total_pages}")
        print(f"     Page size   : {page_size}\n")
    
    first_drugs.append(first_reg)
    time.sleep(random.uniform(1.0, 2.0))

if len(set(first_drugs)) == 3:
    print("✅ PAGINATION CONFIRMED!\n")
else:
    print(f"❌ PAGINATION FAILED: {first_drugs}\n")
    sys.exit(1)

# ── STEP 2: FULL SCRAPE ───────────────────────────────────────
print("=" * 70)
print(f"STEP 2 — Full scrape ({total_pages} pages, ~{total_rows} drugs)")
print("=" * 70 + "\n")

# Load checkpoint
def load_checkpoint():
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {"last_page": 0, "records": []}

def save_checkpoint(page, records):
    with open(CHECKPOINT, "w") as f:
        json.dump({"last_page": page, "records": records}, f)

checkpoint = load_checkpoint()
all_records = checkpoint["records"]
start_page = checkpoint["last_page"] + 1

if start_page > 1:
    print(f"Resuming from page {start_page} ({len(all_records)} records)\n")

# Scrape all pages
failed_pages = []

for page in range(start_page, total_pages + 1):
    # ADAPTIVE DELAY based on success rate
    if page > 5:
        # Increase delay if we have failures
        base_delay = 2.0 + (len(failed_pages) * 0.5)
    else:
        base_delay = 1.5
    
    results, err = fetch_page(page, max_retries=5, base_delay=base_delay)
    
    if err:
        print(f"❌ Page {page} failed: {err}")
        failed_pages.append(page)
        continue
    
    if not results:
        print(f"⚠️  Page {page} empty — stopping")
        break
    
    all_records.extend(results)
    save_checkpoint(page, all_records)
    
    # Progress report every 20 pages
    if page % 20 == 0 or page <= 5:
        print(f"✓ Page {page}/{total_pages} | collected: {len(all_records)} drugs\n")
    
    # Smart delay between requests
    delay = random.uniform(0.8, 2.0)
    time.sleep(delay)

print(f"\n✅ Scraping complete!")
print(f"   Total records: {len(all_records)}")
print(f"   Failed pages: {len(failed_pages)}")
if failed_pages:
    print(f"   Failed: {failed_pages[:10]}")

# ── STEP 3: EXPORT ────────────────────────────────────────────
print("\n" + "=" * 70)
print("STEP 3 — Export to Multiple Formats")
print("=" * 70)

df = pd.DataFrame(all_records)
print(f"Columns: {len(df.columns)} | Rows: {len(df)}")

# Deduplicate
before = len(df)
df.drop_duplicates(subset=["registerNumber"], keep="first", inplace=True)
after = len(df)
print(f"After dedup: {after} (removed {before - after} duplicates)\n")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# 1. CSV
print("📝 Exporting CSV...")
try:
    csv_file = f"sfda_drugs_{timestamp}.csv"
    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
    print(f"✅ CSV: {csv_file}\n")
except Exception as e:
    print(f"❌ CSV failed: {e}\n")

# 2. JSON
print("📝 Exporting JSON...")
try:
    json_file = f"sfda_drugs_{timestamp}.json"
    df.to_json(json_file, orient='records', force_ascii=False, indent=2)
    print(f"✅ JSON: {json_file}\n")
except Exception as e:
    print(f"❌ JSON failed: {e}\n")

# 3. Excel (English only)
print("📝 Exporting Excel...")
try:
    # Remove Arabic columns
    skip_cols = [col for col in df.columns if 'Ar' in col or col in [
        'scientificNames', 'drugCombinations', 'drugAgents', 
        'drugManufacturers', 'drugAvailabilities'
    ]]
    df_en = df.drop(columns=skip_cols, errors='ignore')
    
    # Remove Arabic text from remaining columns
    for col in df_en.columns:
        if df_en[col].dtype == 'object':
            df_en[col] = df_en[col].astype(str).str.replace(
                r'[\u0600-\u06FF]', '', regex=True
            )
    
    excel_file = f"sfda_drugs_{timestamp}_EN.xlsx"
    
    with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
        df_en.to_excel(writer, sheet_name="Drugs", index=False)
        ws = writer.sheets["Drugs"]
        for col in ws.columns:
            max_len = max((len(str(cell.value or "")) for cell in col), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 45)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
    
    print(f"✅ Excel: {excel_file}\n")
except Exception as e:
    print(f"❌ Excel failed: {e}\n")

# 4. Parquet
print("📝 Exporting Parquet...")
try:
    parquet_file = f"sfda_drugs_{timestamp}.parquet"
    df.to_parquet(parquet_file, index=False, compression='gzip')
    print(f"✅ Parquet: {parquet_file}\n")
except ImportError:
    print(f"⚠️  Parquet skipped (install: pip install pyarrow)\n")
except Exception as e:
    print(f"❌ Parquet failed: {e}\n")

# Summary
print("=" * 70)
print("📊 FINAL SUMMARY")
print("=" * 70)
print(f"✅ Total drugs: {after}")
print(f"✅ Columns: {len(df_en.columns if 'df_en' in locals() else df.columns)}")
print(f"✅ Export formats: CSV, JSON, Excel (EN), Parquet")

# Cleanup
if os.path.exists(CHECKPOINT):
    os.remove(CHECKPOINT)
    print(f"✅ Checkpoint cleaned up")

print("\n🎉 ALL DONE!")