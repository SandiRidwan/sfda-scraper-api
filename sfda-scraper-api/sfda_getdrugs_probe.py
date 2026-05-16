"""
sfda_getdrugs_probe.py
Fokus intercept GetDrugs.php - tangkap exact request + response
Run: python sfda_getdrugs_probe.py
"""

from playwright.sync_api import sync_playwright
import json, time

captured = []

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        # ── Intercept REQUEST ──────────────────────────────────
        def on_request(req):
            if 'GetDrugs' in req.url:
                entry = {
                    'url': req.url,
                    'method': req.method,
                    'post_data': req.post_data,
                    'headers': dict(req.headers),
                }
                captured.append(entry)
                print('\n[GetDrugs REQUEST #' + str(len(captured)) + ']')
                print('  Method : ' + req.method)
                print('  URL    : ' + req.url)
                if req.post_data:
                    print('  POST   : ' + req.post_data[:500])
                else:
                    print('  POST   : (none — GET request)')
                # Print semua query params dari URL
                if '?' in req.url:
                    params = req.url.split('?')[1]
                    print('  PARAMS : ' + params)

        # ── Intercept RESPONSE ─────────────────────────────────
        def on_response(resp):
            if 'GetDrugs' in resp.url:
                try:
                    body = resp.json()
                    result = body.get('data', {}).get('result', {})
                    drugs = result.get('results', [])
                    print('\n[GetDrugs RESPONSE]')
                    print('  currentPage  : ' + str(result.get('currentPage')))
                    print('  pageCount    : ' + str(result.get('pageCount')))
                    print('  pageSize     : ' + str(result.get('pageSize')))
                    print('  rowCount     : ' + str(result.get('rowCount')))
                    print('  firstRowOnPage: ' + str(result.get('firstRowOnPage')))
                    print('  lastRowOnPage : ' + str(result.get('lastRowOnPage')))
                    print('  drugs count  : ' + str(len(drugs)))
                    if drugs:
                        print('  first drug   : ' + str(drugs[0].get('registerNumber')))
                        print('  last drug    : ' + str(drugs[-1].get('registerNumber')))

                    # Save full response
                    with open('getdrugs_response_p' + str(result.get('currentPage','?')) + '.json', 'w') as f:
                        json.dump(body, f, indent=2)
                    print('  Saved to getdrugs_response.json')
                except Exception as e:
                    print('[GetDrugs RESPONSE ERROR] ' + str(e))

        page.on('request', on_request)
        page.on('response', on_response)

        # ── Load page 1 ────────────────────────────────────────
        print('Loading page 1...')
        page.goto('https://www.sfda.gov.sa/en/drugs-list', timeout=30000)
        page.wait_for_load_state('networkidle')
        time.sleep(3)

        # ── Click Next Page ────────────────────────────────────
        print('\nClicking Next Page...')
        try:
            next_btn = page.query_selector('.pager__item--next a, a[rel=next], .next a')
            if next_btn:
                next_btn.click()
                time.sleep(4)
                print('Next page clicked — check REQUEST #2 above')
            else:
                print('Next button not found — trying JS scroll instead')
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(3)
        except Exception as e:
            print('Click error: ' + str(e))

        # ── Click Next Page sekali lagi ─────────────────────────
        print('\nClicking Next Page (page 3)...')
        try:
            next_btn2 = page.query_selector('.pager__item--next a, a[rel=next]')
            if next_btn2:
                next_btn2.click()
                time.sleep(4)
                print('Page 3 clicked — check REQUEST #3 above')
        except Exception as e:
            print('Click error p3: ' + str(e))

        browser.close()

    # ── Summary ────────────────────────────────────────────────
    print('\n' + '='*60)
    print('SUMMARY - ' + str(len(captured)) + ' GetDrugs requests captured')
    print('='*60)
    for i, c in enumerate(captured):
        print('\nRequest #' + str(i+1))
        print('  URL   : ' + c['url'])
        print('  Method: ' + c['method'])
        print('  POST  : ' + str(c['post_data']))
        if '?' in c['url']:
            print('  PARAMS: ' + c['url'].split('?')[1])

    # Save all captured
    with open('sfda_captured.json', 'w') as f:
        json.dump(captured, f, indent=2, default=str)
    print('\nAll captured saved to sfda_captured.json')

if __name__ == '__main__':
    run()
