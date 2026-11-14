#!/usr/bin/env python3
"""Reintenta 1 ficha y sondea endpoints de búsqueda interna de PCC desde la página (cookies CF activas)."""
import asyncio, json

MOMENTUM = 'https://www.pccomponentes.com/sennheiser-momentum-true-wireless-4-auriculares-bluetooth-con-cancelacion-de-ruido-grafito-negro'
PROBES = [
    '/search/suggest?q=fiio',
    '/api/search/suggest?q=fiio',
    '/searchbar/suggest?q=fiio',
    '/rest/search/suggest?q=fiio',
    '/api/v2/search?q=fiio',
    '/search?q=fiio',
    '/_next/data/search?q=fiio',
    '/services/searchservice/suggest?q=fiio',
]


async def main():
    import nodriver as uc
    browser = await uc.start(
        browser_executable_path='/home/z/.cache/puppeteer/chrome/linux-157.0.8103.50/chrome-linux64/chrome',
        headless=False, xvfb_display=':99',
        browser_args=['--lang=es-ES', '--window-size=1400,900'],
    )
    tab = await browser.get(MOMENTUM)
    title = ''
    for _ in range(45):
        await tab.sleep(2)
        try:
            title = await tab.evaluate('document.title')
        except Exception:
            continue
        if title and 'moment' not in title.lower():
            break
    print('MOMENTUM TITULO:', title)
    if 'moment' not in (title or '').lower():
        raw = await tab.evaluate("""
        (() => {
          const res = {lds: []};
          for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
            try {
              const o = JSON.parse(s.textContent);
              const st = [o];
              while (st.length) {
                const x = st.pop();
                if (Array.isArray(x)) { st.push(...x); continue; }
                if (x && typeof x === 'object') {
                  if (x['@type'] === 'Product') res.lds.push({name: x.name, sku: x.sku, offers: x.offers});
                  for (const v of Object.values(x)) if (v && typeof v === 'object') st.push(v);
                }
              }
            } catch(e) {}
          }
          const m = document.body.innerText.match(/([0-9]{1,4}[.,][0-9]{2})\\s*€/);
          res.firstPrice = m ? m[1] : null;
          return JSON.stringify(res);
        })()
        """)
        try:
            data = json.loads(raw)
            if isinstance(data, str):
                data = json.loads(data)
        except Exception:
            data = {}
        print('MOMENTUM LDPs:', len(data.get('lds') or []), '| firstPrice:', data.get('firstPrice'))
        for x in (data.get('lds') or [])[:5]:
            off = x.get('offers') or {}
            print('  -', str(x.get('name'))[:50], '| sku:', x.get('sku'), '|', off.get('price'), '|', (off.get('seller') or {}).get('name'))
        results = json.load(open('/home/z/my-project/data/pcc_live.json'))
        results['sennheiser-momentum-true-wireless-4'] = data
        json.dump(results, open('/home/z/my-project/data/pcc_live.json', 'w'), ensure_ascii=False, indent=1)

    # sondeo de endpoints
    for p in PROBES:
        try:
            r = await tab.evaluate(f"""
            fetch('{p}', {{headers: {{'Accept': 'application/json'}}}}).then(r => r.text().then(t => JSON.stringify({{st: r.status, ct: (r.headers.get('content-type')||''), n: t.length, head: t.slice(0,150)}})))
            """)
            print(f"{p:44} -> {str(r)[:220]}")
        except Exception as e:
            print(f"{p:44} -> ERR {str(e)[:80]}")
        await tab.sleep(1)
    try:
        await browser.stop()
    except Exception:
        pass


asyncio.run(main())
