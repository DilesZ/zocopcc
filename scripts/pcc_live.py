#!/usr/bin/env python3
"""Lee en DIRECTO las fichas de PCComponentes con nodriver (pasa Cloudflare).
Arranca directamente en la primera ficha (reto no interactivo), reutiliza pestaña,
recrea la pestaña si el reto se atasca.
Uso: python3 pcc_live.py <salida.json> [url1 url2 ...]
"""
import asyncio, json, sys

URLS_FILE = '/home/z/my-project/data/pcc_urls.json'


async def wait_clear(tab, max_s=40):
    """Espera a que el título deje de ser el reto CF."""
    title = ''
    for _ in range(max_s // 2):
        await tab.sleep(2)
        try:
            title = await tab.evaluate('document.title')
        except Exception:
            continue
        if title and 'moment' not in title.lower():
            return True, title
    return False, title


async def fetch_tab(tab, url, skip_nav=False):
    title = ''
    if not skip_nav:
        await tab.get(url)
        ok, title = await wait_clear(tab)
        if not ok:
            return None, ''
    await tab.sleep(1.5)
    raw = await tab.evaluate("""
    (() => {
      const res = {url: location.href, title: document.title, lds: []};
      const scripts = [...document.querySelectorAll('script[type="application/ld+json"]')];
      for (const s of scripts) {
        try {
          const o = JSON.parse(s.textContent);
          const stack = [o];
          while (stack.length) {
            const x = stack.pop();
            if (Array.isArray(x)) { stack.push(...x); continue; }
            if (x && typeof x === 'object') {
              if (x['@type'] === 'Product') {
                res.lds.push({name: x.name, sku: x.sku, brand: (x.brand||{}).name,
                              gtin: x.gtin13 || x.gtin12 || x.gtin8 || x.ean || null,
                              offers: x.offers});
              }
              for (const v of Object.values(x)) if (v && typeof v === 'object') stack.push(v);
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
        data = {'url': url, 'title': title, 'lds': []}
    return data, title


async def main():
    out_path = sys.argv[1]
    only_urls = sys.argv[2:] if len(sys.argv) > 2 else None
    urls = json.load(open(URLS_FILE))
    try:
        results = json.load(open(out_path))
    except Exception:
        results = {}
    for k in list(results):
        if results[k].get('title') in ('RETO_NO_SUPERADO',):
            del results[k]

    import nodriver as uc
    browser = await uc.start(
        browser_executable_path='/home/z/.cache/puppeteer/chrome/linux-157.0.8103.50/chrome-linux64/chrome',
        headless=False, xvfb_display=':99',
        browser_args=['--lang=es-ES', '--window-size=1400,900'],
    )
    if only_urls:
        wanted = set(only_urls)
        pending = [(h, u) for h, u in urls.items() if u in wanted or h in wanted]
    else:
        pending = [(h, u) for h, u in urls.items() if h not in results]
    total = len(pending)
    done = 0
    stuck = 0
    tab = None
    for n, (handle, url) in enumerate(pending, 1):
        handle = next((k for k, v in urls.items() if v == url), url)
        data = None
        try:
            if tab is None:
                tab = await browser.get(url)  # primera navegación: reto no interactivo
            else:
                await tab.get(url)
            ok, title = await wait_clear(tab, int(__import__('os').environ.get('PCC_WAIT','40')))
            if ok:
                await tab.sleep(1.5)
                data, _ = await fetch_tab(tab, url, skip_nav=True)
        except Exception as e:
            print(f"  [{n}] EXC: {str(e)[:100]}", flush=True)
        if data:
            done += 1
            stuck = 0
            results[handle] = data
        else:
            stuck += 1
            results[handle] = {'url': url, 'title': 'RETO_NO_SUPERADO', 'lds': []}
            if stuck >= 3:
                print('3 fallos consecutivos: aborto (sesión envenenada o bloqueo IP)', flush=True)
                json.dump(results, open(out_path, 'w'), ensure_ascii=False, indent=1)
                break
        json.dump(results, open(out_path, 'w'), ensure_ascii=False, indent=1)
        lds = (data or {}).get('lds') or []
        pcc_ld = next((x for x in lds if 'pccomponentes' in json.dumps(x.get('offers') or {}).lower()), None)
        use = pcc_ld or (lds[0] if lds else {})
        off = use.get('offers') or {}
        sell = ((off.get('seller') or {}).get('name')) or ((off.get('offeredBy') or {}).get('name'))
        print(f"[{n}/{total}] {handle[:30]:30} | {str(use.get('name'))[:32]:32} | sku:{use.get('sku')} | "
              f"{off.get('price')}€ | {str(off.get('availability','')).split('/')[-1][:12]} | vendedor:{sell}", flush=True)
        await asyncio.sleep(5)
    print(f'OK live: {done}/{total} fichas con datos')
    try:
        await browser.stop()
    except Exception:
        pass


if __name__ == '__main__':
    asyncio.run(main())
