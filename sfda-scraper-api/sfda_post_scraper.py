"""
sfda_post_scraper.py
Method: POST x-www-form-urlencoded
Body  : TradeName=&Agent=&ManufacturerName=&RegNo=&page=N
Run   : python sfda_post_scraper.py
"""

import requests, time, random, json, os
import pandas as pd

# ── CONFIG ────────────────────────────────────────────────────
URL        = "https://www.sfda.gov.sa/GetDrugs.php"
CHECKPOINT = "sfda_checkpoint.json"
OUTPUT     = "sfda_drugs_final.xlsx"

HEADERS = {
    "Accept"          : "application/json, text/javascript, */*; q=0.01",
    "Content-Type"    : "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer"         : "https://www.sfda.gov.sa/en/drugs-list",
    "User-Agent"      : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
}

# ── STEP 1: CONFIRM PAGINATION WORKS ────────────────────────
print("=" * 60)
print("STEP 1 — Confirm POST pagination works")
print("=" * 60)

first_drugs = []
for pg in [1, 2, 3]:
    r = requests.post(URL,
        data={"TradeName": "", "Agent": "", "ManufacturerName": "", "RegNo": "", "page": pg},
        headers=HEADERS, timeout=20)
    result = r.json().get("data", {}).get("result", {})
    drugs  = result.get("results", [])
    first  = drugs[0].get("registerNumber", "EMPTY") if drugs else "EMPTY"
    last   = drugs[-1].get("registerNumber", "EMPTY") if drugs else "EMPTY"

    print(f"page={pg} | curPage={result.get('currentPage')} | "
          f"firstRow={result.get('firstRowOnPage')} | "
          f"lastRow={result.get('lastRowOnPage')} | "
          f"first={first} | last={last}")

    if pg == 1:
        total_pages = result.get("pageCount", 0)
        total_rows  = result.get("rowCount", 0)
        page_size   = result.get("pageSize", 20)
        print(f"\n  Total drugs : {total_rows}")
        print(f"  Total pages : {total_pages}")
        print(f"  Page size   : {page_size}")
        print()

    first_drugs.append(first)

# Verify pagination bekerja
if len(set(first_drugs)) == 3:
    print("\n✅ PAGINATION CONFIRMED — setiap page return data berbeda!")
else:
    print("\n❌ PAGINATION MASIH GAGAL — semua page return data sama")
    print("   first_drugs:", first_drugs)
    exit(1)

# ── STEP 2: FULL SCRAPER ─────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2 — Full scrape")
print("=" * 60)

# Load checkpoint
def load_checkpoint():
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {"last_page": 0, "records": []}

def save_checkpoint(page, records):
    with open(CHECKPOINT, "w") as f:
        json.dump({"last_page": page, "records": records}, f)

checkpoint   = load_checkpoint()
all_records  = checkpoint["records"]
start_page   = checkpoint["last_page"] + 1

if start_page > 1:
    print(f"Resuming from page {start_page} ({len(all_records)} records already collected)")
else:
    # Page 1 sudah di-fetch di step 1 — ambil datanya
    r1 = requests.post(URL,
        data={"TradeName": "", "Agent": "", "ManufacturerName": "", "RegNo": "", "page": 1},
        headers=HEADERS, timeout=20)
    res1   = r1.json().get("data", {}).get("result", {})
    total_pages = res1.get("pageCount", 0)
    all_records.extend(res1.get("results", []))
    save_checkpoint(1, all_records)
    print(f"Page 1/{total_pages} | collected: {len(all_records)}")

# Fetch total_pages kalau belum ada (resume case)
if start_page > 1:
    r_probe = requests.post(URL,
        data={"TradeName": "", "Agent": "", "ManufacturerName": "", "RegNo": "", "page": 1},
        headers=HEADERS, timeout=20)
    total_pages = r_probe.json().get("data", {}).get("result", {}).get("pageCount", 0)

# Loop page 2 sampai akhir
for page in range(max(start_page, 2), total_pages + 1):
    try:
        r = requests.post(URL,
            data={"TradeName": "", "Agent": "", "ManufacturerName": "", "RegNo": "", "page": page},
            headers=HEADERS, timeout=30)
        result = r.json().get("data", {}).get("result", {})
        batch  = result.get("results", [])

        if not batch:
            print(f"  ⚠ Page {page} returned empty — stopping")
            break

        all_records.extend(batch)
        save_checkpoint(page, all_records)

        if page % 10 == 0 or page <= 5:
            print(f"Page {page}/{total_pages} | collected: {len(all_records)} | "
                  f"firstRow={result.get('firstRowOnPage')} | lastRow={result.get('lastRowOnPage')}")

        time.sleep(random.uniform(0.5, 1.2))

    except Exception as e:
        print(f"  ✗ Page {page} error: {e} — retrying in 5s")
        time.sleep(5)
        try:
            r = requests.post(URL,
                data={"TradeName": "", "Agent": "", "ManufacturerName": "", "RegNo": "", "page": page},
                headers=HEADERS, timeout=30)
            batch = r.json().get("data", {}).get("result", {}).get("results", [])
            all_records.extend(batch)
            save_checkpoint(page, all_records)
        except Exception as e2:
            print(f"  ✗ Page {page} retry failed: {e2} — skipping")

print(f"\n✅ Scraping done! Total records: {len(all_records)}")

# ── STEP 3: EXPORT EXCEL ─────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 3 — Export to Excel")
print("=" * 60)

df = pd.DataFrame(all_records)
print(f"Columns ({len(df.columns)}): {list(df.columns)}")
print(f"Rows: {len(df)}")

# Deduplicate
before = len(df)
df.drop_duplicates(subset=["registerNumber"], inplace=True)
print(f"After dedup: {len(df)} (removed {before - len(df)} duplicates)")

# Export
with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
    df.to_excel(writer, sheet_name="Drugs", index=False)

    # Auto-fit columns
    ws = writer.sheets["Drugs"]
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

    # Freeze header
    ws.freeze_panes = "A2"

print(f"✅ Saved to {OUTPUT}")
print(f"   Rows    : {len(df)}")
print(f"   Columns : {len(df.columns)}")

# Cleanup checkpoint
if os.path.exists(CHECKPOINT):
    os.remove(CHECKPOINT)
    print("   Checkpoint cleaned up")
