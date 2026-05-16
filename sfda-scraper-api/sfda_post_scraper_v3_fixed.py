# sfda_post_scraper_v3_fixed.py — FIXED VERSION dengan double JSON parse
import json
import time
import random
from datetime import datetime
from curl_cffi import requests as cffi_requests
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

SFDA_BASE_URL = "https://www.sfda.gov.sa"
SFDA_API = f"{SFDA_BASE_URL}/GetDrugs.php"

# Headers seperti captured
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{SFDA_BASE_URL}/en/drugs-list",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
}

def fetch_page(page, max_retries=5):
    """
    Fetch halaman dengan double JSON parse
    1. Parse response → dapat field "data" (string)
    2. Parse "data" string → dapat object dengan drugs
    """
    
    data = {
        "TradeName": "",
        "Agent": "",
        "ManufacturerName": "",
        "RegNo": "",
        "page": page
    }
    
    for attempt in range(max_retries):
        try:
            timeout = 30 + (attempt * 10)
            
            if attempt > 0:
                delay = 0.8 * (2 ** (attempt - 1)) + random.uniform(0, 1)
                print(f"  ⏳ Page {page} attempt {attempt+1}: waiting {delay:.1f}s...")
                time.sleep(delay)
            
            print(f"  📡 Page {page} attempt {attempt+1}: POST (timeout={timeout}s)")
            
            response = cffi_requests.post(
                SFDA_API,
                data=data,
                headers=HEADERS,
                timeout=timeout,
                impersonate="chrome120"
            )
            
            if response.status_code != 200:
                print(f"  ⚠ HTTP {response.status_code}")
                if attempt < max_retries - 1:
                    continue
                else:
                    return page, [], f"HTTP {response.status_code}"
            
            # PARSE LEVEL 1 — response JSON
            try:
                resp_json = response.json()
            except json.JSONDecodeError as e:
                print(f"  ❌ JSON parse L1 error: {e}")
                print(f"     Response: {response.text[:200]}")
                if attempt < max_retries - 1:
                    continue
                else:
                    return page, [], f"JSON L1 parse error"
            
            # Cek apakah ada field "data"
            if "data" not in resp_json:
                print(f"  ❌ No 'data' field in response")
                print(f"     Response keys: {list(resp_json.keys())}")
                if attempt < max_retries - 1:
                    continue
                else:
                    return page, [], "No 'data' field"
            
            data_str = resp_json.get("data", "")
            
            # PARSE LEVEL 2 — data string adalah JSON juga!
            try:
                drugs_dict = json.loads(data_str)
            except json.JSONDecodeError as e:
                print(f"  ❌ JSON parse L2 error: {e}")
                print(f"     Data str: {data_str[:200]}")
                if attempt < max_retries - 1:
                    continue
                else:
                    return page, [], f"JSON L2 parse error"
            
            # Convert dict to list
            drugs = []
            if isinstance(drugs_dict, dict):
                # drugs_dict keys are: "0", "1", "2", ... atau numeric indices
                for key in sorted(drugs_dict.keys(), key=lambda x: int(x) if x.isdigit() else 0):
                    drugs.append(drugs_dict[key])
            elif isinstance(drugs_dict, list):
                drugs = drugs_dict
            
            print(f"  ✅ Page {page}: {len(drugs)} drugs | attempt {attempt+1}")
            return page, drugs, None
        
        except cffi_requests.exceptions.Timeout:
            print(f"  ⚠ Timeout after {timeout}s (attempt {attempt+1}/{max_retries})")
            if attempt >= max_retries - 1:
                return page, [], "Timeout"
        
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:100]} (attempt {attempt+1}/{max_retries})")
            if attempt >= max_retries - 1:
                return page, [], str(e)[:100]
    
    return page, [], "Failed after max retries"


def scrape_full(max_pages=876):
    """Main scraper — collect all pages"""
    
    print("\n" + "="*70)
    print("SFDA SCRAPER v3 FIXED — Double JSON Parse")
    print("="*70)
    print(f"Target: {max_pages} pages")
    
    all_drugs = []
    failed_pages = []
    
    # Test page 1 dulu
    print(f"\n📍 Testing page 1...")
    page_num, drugs, error = fetch_page(1)
    
    if error:
        print(f"❌ Page 1 failed: {error}")
        print("Aborting scrape.")
        return
    
    all_drugs.extend(drugs)
    print(f"✅ Page 1 successful: {len(drugs)} drugs")
    
    # Scrape pages 2 onwards
    print(f"\n📍 Scraping pages 2-{max_pages}...")
    
    for page in range(2, max_pages + 1):
        page_num, drugs, error = fetch_page(page)
        
        if error:
            print(f"  ✗ Page {page}: {error}")
            failed_pages.append(page)
        else:
            all_drugs.extend(drugs)
        
        # Progress update
        if page % 50 == 0:
            print(f"  Progress: {page}/{max_pages} pages | {len(all_drugs)} drugs collected")
        
        # Rate limiting
        time.sleep(random.uniform(0.5, 1.5))
    
    # Summary
    print(f"\n" + "="*70)
    print(f"SCRAPING COMPLETE")
    print(f"="*70)
    print(f"✅ Total drugs: {len(all_drugs)}")
    print(f"✅ Unique drugs: {len(set(d.get('registerNumber', '') for d in all_drugs if isinstance(d, dict)))}")
    print(f"⚠️ Failed pages: {len(failed_pages)} — {failed_pages[:10]}{'...' if len(failed_pages) > 10 else ''}")
    
    return all_drugs, failed_pages


def extract_drug_info(drug):
    """Extract key fields from drug object"""
    if not isinstance(drug, dict):
        return None
    
    return {
        "registerNumber": drug.get("registerNumber", ""),
        "tradeName": drug.get("tradeName", ""),
        "scientificName": drug.get("scientificName", ""),
        "manufacturer": drug.get("company", {}).get("nameEn", "") if isinstance(drug.get("company"), dict) else "",
        "country": drug.get("company", {}).get("country", {}).get("nameEn", "") if isinstance(drug.get("company"), dict) else "",
        "strength": drug.get("strength", ""),
        "packageSize": drug.get("packageSize", ""),
        "shelfLife": drug.get("shelfLife", ""),
        "price": drug.get("price", ""),
        "status": drug.get("marketingStatus", {}).get("nameEn", "") if isinstance(drug.get("marketingStatus"), dict) else "",
    }


def export_to_excel(drugs, filename="SFDA_drugs.xlsx"):
    """Export ke Excel dengan sanitasi"""
    
    print(f"\n📊 Exporting to Excel: {filename}")
    
    # Extract clean data
    clean_data = []
    for drug in drugs:
        info = extract_drug_info(drug)
        if info and info.get("registerNumber"):
            clean_data.append(info)
    
    # Deduplicate
    unique_drugs = {}
    for drug in clean_data:
        key = drug.get("registerNumber")
        if key:
            unique_drugs[key] = drug
    
    print(f"  After dedup: {len(unique_drugs)} unique drugs")
    
    # Create DataFrame
    df = pd.DataFrame(list(unique_drugs.values()))
    
    # Sanitize Arabic chars
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).apply(lambda x: ''.join(c for c in x if ord(c) < 0x0600 or ord(c) > 0x06FF))
    
    # Export
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Drugs", index=False)
        
        # Add summary sheet
        ws_summary = writer.book.create_sheet("Summary")
        ws_summary["A1"] = "SFDA Drugs Export Summary"
        ws_summary["A1"].font = Font(bold=True, size=12)
        ws_summary["A2"] = f"Total Records: {len(df)}"
        ws_summary["A3"] = f"Unique Drugs: {len(unique_drugs)}"
        ws_summary["A4"] = f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    print(f"✅ Exported: {filename}")
    return df


if __name__ == "__main__":
    # Scrape
    drugs, failed = scrape_full(max_pages=876)
    
    # Export
    if drugs:
        df = export_to_excel(drugs)
        print(f"\n🎯 FINAL RESULT:")
        print(f"  • Total rows in Excel: {len(df)}")
        print(f"  • Columns: {', '.join(df.columns.tolist())}")