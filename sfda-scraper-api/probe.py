import requests
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Referer': 'https://www.sfda.gov.sa/en/drugs-list'
}

print("=== TEST 1: HTML pagination ===")
for pg in [0, 1, 2]:
    r = requests.get('https://www.sfda.gov.sa/en/drugs-list',
        params={'page': pg}, headers=headers, timeout=20)
    soup = BeautifulSoup(r.text, 'html.parser')
    tables = soup.find_all('table')
    rows = soup.find_all('tr')
    items = soup.find_all(class_=lambda x: x and 'drug' in str(x).lower())
    views_rows = soup.find_all(class_='views-row')
    print('page=' + str(pg) + ' tables=' + str(len(tables)) + ' tr=' + str(len(rows)) + ' drug_class=' + str(len(items)) + ' views-row=' + str(len(views_rows)))
    if tables:
        first_row = tables[0].find('tr')
        if first_row:
            print('  table_row: ' + first_row.get_text()[:100].strip())
    if views_rows:
        print('  views_row[0]: ' + views_rows[0].get_text()[:100].strip())

print()
print("=== TEST 2: Class names ===")
r0 = requests.get('https://www.sfda.gov.sa/en/drugs-list',
    params={'page': 0}, headers=headers, timeout=20)
soup0 = BeautifulSoup(r0.text, 'html.parser')
all_classes = set()
for tag in soup0.find_all(class_=True):
    for c in tag.get('class', []):
        all_classes.add(c)
keywords = ['drug','item','row','result','list','table','record','view','field']
relevant = [c for c in sorted(all_classes) if any(k in c.lower() for k in keywords)]
print('Relevant: ' + str(relevant[:20]))

print()
print("=== TEST 3: GetDrugs.php dengan Referer baru ===")
api_headers = {
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': 'https://www.sfda.gov.sa/en/drugs-list',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
for pg in [1, 2, 3]:
    r = requests.get('https://www.sfda.gov.sa/GetDrugs.php',
        params={'page': pg, 'pageSize': 20},
        headers=api_headers, timeout=20)
    try:
        result = r.json().get('data',{}).get('result',{})
        first = result.get('results',[{}])[0].get('registerNumber','EMPTY')
        print('page=' + str(pg) + ' curPage=' + str(result.get('currentPage')) + ' firstRow=' + str(result.get('firstRowOnPage')) + ' first=' + str(first))
    except Exception as e:
        print('page=' + str(pg) + ' ERROR: ' + str(e))