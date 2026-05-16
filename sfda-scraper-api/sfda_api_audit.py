# sfda_api_audit.py — Debug SFDA API endpoint
import requests
from curl_cffi import requests as cffi_requests
import json
import time

BASE_URL = "https://www.sfda.gov.sa"

def test_get_endpoint():
    """Test standard GET request"""
    print("\n" + "="*60)
    print("TEST 1: GET /GetDrugs.php")
    print("="*60)
    
    params = {
        "page": 1,
        "pageSize": 20
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    try:
        resp = requests.get(
            f"{BASE_URL}/GetDrugs.php",
            params=params,
            headers=headers,
            timeout=10
        )
        print(f"Status: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('content-type')}")
        print(f"Response length: {len(resp.text)}")
        print(f"First 500 chars:\n{resp.text[:500]}")
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                print(f"✅ Valid JSON! Keys: {list(data.keys())}")
                return True
            except json.JSONDecodeError as e:
                print(f"❌ JSON parse error: {e}")
                return False
    except Exception as e:
        print(f"❌ Request error: {e}")
        return False

def test_post_endpoint():
    """Test POST with data body"""
    print("\n" + "="*60)
    print("TEST 2: POST /GetDrugs.php with data body")
    print("="*60)
    
    data = {
        "TradeName": "",
        "Agent": "",
        "ManufacturerName": "",
        "RegNo": "",
        "page": 1
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": BASE_URL
    }
    
    try:
        resp = requests.post(
            f"{BASE_URL}/GetDrugs.php",
            data=data,
            headers=headers,
            timeout=10
        )
        print(f"Status: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('content-type')}")
        print(f"Response length: {len(resp.text)}")
        print(f"First 500 chars:\n{resp.text[:500]}")
        
        if resp.status_code == 200:
            try:
                resp_data = resp.json()
                print(f"✅ Valid JSON! Keys: {list(resp_data.keys())}")
                return True
            except json.JSONDecodeError as e:
                print(f"❌ JSON parse error: {e}")
                return False
    except Exception as e:
        print(f"❌ Request error: {e}")
        return False

def test_curl_cffi():
    """Test dengan curl_cffi"""
    print("\n" + "="*60)
    print("TEST 3: POST /GetDrugs.php dengan curl_cffi (Chrome TLS)")
    print("="*60)
    
    data = {
        "TradeName": "",
        "Agent": "",
        "ManufacturerName": "",
        "RegNo": "",
        "page": 1
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": BASE_URL
    }
    
    try:
        resp = cffi_requests.post(
            f"{BASE_URL}/GetDrugs.php",
            data=data,
            headers=headers,
            timeout=10,
            impersonate="chrome120"
        )
        print(f"Status: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('content-type')}")
        print(f"Response length: {len(resp.text)}")
        print(f"First 500 chars:\n{resp.text[:500]}")
        
        if resp.status_code == 200:
            try:
                resp_data = resp.json()
                print(f"✅ Valid JSON! Keys: {list(resp_data.keys())}")
                return True
            except json.JSONDecodeError as e:
                print(f"❌ JSON parse error: {e}")
                return False
    except Exception as e:
        print(f"❌ Request error: {e}")
        return False

def test_browser_har():
    """Instruksi manual: capture HAR dari browser"""
    print("\n" + "="*60)
    print("TEST 4: Manual HAR Capture")
    print("="*60)
    print("""
    Langkah manual (jika endpoint masih belum ditemukan):
    1. Buka https://www.sfda.gov.sa di browser
    2. F12 → Network tab → filter "XHR"
    3. Coba cari drugs (misal: search dengan keyword)
    4. Cari request yang mengirim data
    5. Copy-paste URL lengkap, method, headers, body ke sini
    """)

if __name__ == "__main__":
    print("\n🔍 SFDA API AUDIT — Testing Various Methods")
    
    result1 = test_get_endpoint()
    time.sleep(2)
    
    result2 = test_post_endpoint()
    time.sleep(2)
    
    result3 = test_curl_cffi()
    
    if not result1 and not result2 and not result3:
        print("\n❌ SEMUA METHOD GAGAL — Endpoint mungkin berubah")
        print("Jalankan TEST 4 (manual HAR capture) untuk menemukan endpoint baru")
