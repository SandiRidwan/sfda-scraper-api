from curl_cffi import requests as cffi_requests

session = cffi_requests.Session(impersonate='chrome120')

r = session.post(
    'https://www.sfda.gov.sa/GetDrugs.php',
    data={'TradeName': '', 'Agent': '', 'ManufacturerName': '', 'RegNo': '', 'page': 1},
    headers={
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://www.sfda.gov.sa/en/drugs-list',
    },
    timeout=30
)

print(f'Status: {r.status_code}')
print(f'Response length: {len(r.text)}')
print(f'First 500 chars:\n{r.text[:500]}')
print()

try:
    data = r.json()
    print(f'✅ JSON OK!')
    print(f'   code: {data.get("code")}')
    result = data.get('data', {}).get('result', {})
    results = result.get('results', [])
    print(f'   results type: {type(results)}')
    print(f'   results count: {len(results)}')
except Exception as e:
    print(f'❌ Error: {e}')
    print(f'   Exception type: {type(e).__name__}')