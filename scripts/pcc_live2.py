#!/usr/bin/env python3
"""Variante con la estructura exacta que pasa CF: browser.get, sondeo inline, extracción LDP, sin cierres.
Uso: python3 pcc_live2.py <salida.json> <handle>=<url> [<handle>=<url> ...]   (o nada → todas las pendientes)
"""
import asyncio, json, sys, os

URLS_FILE = '/home/z/my-project/data/pcc_urls.json'
EXTRACT_JS = """
(() => {
  const res = {url: location.href, title: document.title, lds: []};
  const scripts = [...document.querySelectorAll('script[type="application/ld+json"]')];
  for (const s of scripts) {
    try {
      const o = JSON.parse(s.textContent);
      const st = [o];
      while (st.length) {
        const x = st.pop();
        if (Array.isArray(x)) { st.push(...x); continue; }
        if (x && typeof x === 'object') {
          if (x['@type'] === 'Product') {
            res.lds.push({name: x.name, sku: x.sku, brand: (x.brand||{}).name,
                          gtin: x.gtin13 || x.gtin12 || x.gtin8 || x.ean || null,
                          offers: x.offers});
          }
          for (const v of Object.values(x)) if (v && typeof v === 'object') st.push(v);
        }
      }
    } catch(e) {}
  }
  const m = document.body.innerText.match(/([0-9]{1,4}[.,][0-9]{2})\\s*€/);
  res.firstPrice = m ? m[1] : null;
  return JSON.stringify(res);
})()
"""


async def main():
    out_path = sys.argv[1]
    args = sys.argv[2:]
    urls = json.load(open(URLS_FILE))
    try:
        results = json.load(open(out_path))
    except Exception:
        results = {}

    pairs = []
    if args:
        for a in args:
            h, _, u = a.partition('=')
            pairs.append((h, u or urls.get(h)))
    else:
        pairs = [(h, u) for h, u in urls.items() if h not in results]

    import nodriver as uc
    browser = await uc.start(
        browser_executable_path='/home/z/.cache/puppeteer/chrome/linux-157.0.8103.50/chrome-linux64/chrome',
        headless=False, xvfb_display=':99',
        browser_args=['--lang=es-ES', '--window-size=1400,900'],
    )
    first = True
    for n, (handle, url) in enumerate(pairs, 1):
        try:
            if first:
                tab = await browser.get(url)
                first = False
            else:
                await tab.get(url)
            ok = False
            for i in range(60):           # hasta 120 s
                await tab.sleep(2)
                try:
                    t = await tab.evaluate('document.title')
                except Exception:
                    continue
                if t and 'moment' not in t.lower():
                    ok = True
                    break
            if not ok:
                results[handle] = {'url': url, 'title': 'RETO_NO_SUPERADO', 'lds': []}
                print(f"[{n}/{len(pairs)}] {handle[:34]} RETO_NO_SUPERADO", flush=True)
                continue
            await tab.sleep(2)
            raw = await tab.evaluate(EXTRACT_JS)
            try:
                data = json.loads(raw)
                if isinstance(data, str):
                    data = json.loads(data)
            except Exception:
                data = {'url': url, 'title': 'EVAL_FALLIDO', 'lds': []}
            results[handle] = data
            lds = data.get('lds') or []
            pcc_ld = next((x for x in lds if 'pccomponentes' in json.dumps(x.get('offers') or {}).lower()), None)
            use = pcc_ld or (lds[0] if lds else {})
            off = use.get('offers') or {}
            sell = ((off.get('seller') or {}).get('name')) or ((off.get('offeredBy') or {}).get('name'))
            print(f"[{n}/{len(pairs)}] {handle[:34]:34} | {str(use.get('name'))[:34]:34} | sku:{use.get('sku')} | "
                  f"{off.get('price')}€ | {str(off.get('availability','')).split('/')[-1][:12]} | {sell}", flush=True)
        except Exception as e:
            results[handle] = {'url': url, 'title': 'ERROR ' + str(e)[:60], 'lds': []}
            print(f"[{n}/{len(pairs)}] {handle[:34]} ERROR {str(e)[:60]}", flush=True)
        json.dump(results, open(out_path, 'w'), ensure_ascii=False, indent=1)
        await tab.sleep(5)
    print('OK pcc_live2')
    try:
        await browser.stop()
    except Exception:
        pass


asyncio.run(main())
