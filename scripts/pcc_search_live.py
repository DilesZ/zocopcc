#!/usr/bin/env python3
"""Busca productos en el buscador interno de PCComponentes EN DIRECTO (nodriver).
Guarda los primeros resultados (nombre, precio, URL, disponibilidad) por handle.
Al final reintenta la ficha del Momentum con la sesión caliente.
"""
import asyncio, json, re, sys

sys.path.insert(0, '/home/z/my-project/scripts')
from pcc_pipeline import QUERIES

OUT = '/home/z/my-project/data/pcc_search_live.json'
HANDLE_TW = 'audio-technica-ath-twx7'
NO_PCC = ['hifiman-sundara', 'grado-sr80x', 'topping-l50', 'topping-dx1', 'smsl-a2',
          'ifi-audio-zen-air-dac-2', 'rekkord-audio-f110', 'dual-cs418',
          'klipsch-the-fives-v2', 'kef-lsx-ii', 'dali-oberon-1c', 'triangle-ln01a',
          'bluesound-powernode-edge', 'arylic-s50-pro', 'fiio-ft5', 'sennheiser-hd800s',
          'sennheiser-hd-550', 'marantz-pm6007', 'marantz-nr1510', 'fosi-audio-merak-cd-player',
          'nad-d3020-v2', 'cambridge-audio-axa25', 'meze-audio-109-pro', HANDLE_TW]
MOMENTUM = 'https://www.pccomponentes.com/sennheiser-momentum-true-wireless-4-auriculares-bluetooth-con-cancelacion-de-ruido-grafito-negro'

SEARCH_JS = """
(() => {
  const base = 'https://www.pccomponentes.com/';
  const banned = ['buscar','categorias','marcas','grupos','blog','cookies','empresa','comunidad',
                  'informacion','mi-cuenta','carrito','checkout','login','register','wishlist',
                  'configurador','outlet','reacondicionado','opiniones','compare'];
  const out = [];
  const seen = new Set();
  document.querySelectorAll('a[href]').forEach(a => {
    const href = a.href || '';
    if (!href.startsWith(base)) return;
    const path = href.slice(base.length).replace(/\\?.*$/, '').replace(/#.*$/, '');
    if (!path || path.split('/').length !== 1) return;
    if (banned.some(b => path === b || path.startsWith(b + '/'))) return;
    if (seen.has(path)) return;
    const card = a.closest('article') || a.closest('li') || a.parentElement;
    const txt = (card ? card.innerText : a.innerText || '').replace(/\\s+/g, ' ').trim();
    if (!txt || txt.length < 10) return;
    const pm = txt.match(/([0-9]{1,4}(?:[.][0-9]{3})*|[0-9]{1,5})(?:[.,][0-9]{2})?\\s*€/);
    if (!pm) return;
    seen.add(path);
    out.push({path: path, text: txt.slice(0, 200), price: pm[0]});
  });
  return JSON.stringify(out.slice(0, 8));
})()
"""


async def wait_clear(tab, max_s=90):
    for _ in range(max_s // 2):
        await tab.sleep(2)
        try:
            t = await tab.evaluate('document.title')
        except Exception:
            continue
        if t and 'moment' not in t.lower():
            return True, t
    return False, ''


async def main():
    import nodriver as uc
    browser = await uc.start(
        browser_executable_path='/home/z/.cache/puppeteer/chrome/linux-157.0.8103.50/chrome-linux64/chrome',
        headless=False, xvfb_display=':99',
        browser_args=['--lang=es-ES', '--window-size=1400,900'],
    )
    try:
        results = json.load(open(OUT))
    except Exception:
        results = {}

    tab = await browser.get('https://www.pccomponentes.com/buscar/?query=fiio')
    ok, _ = await wait_clear(tab, 90)
    print('Sesion CF:', 'OK' if ok else 'FALLO', flush=True)
    if ok:
        for n, handle in enumerate(NO_PCC, 1):
            q = QUERIES.get(handle, handle)
            url = 'https://www.pccomponentes.com/buscar/?query=' + q.replace(' ', '+')
            await tab.get(url)
            ok2, title = await wait_clear(tab, 45)
            items = []
            if ok2:
                for _ in range(6):          # espera a que hidrate el listado
                    await tab.sleep(3)
                    try:
                        raw = await tab.evaluate(SEARCH_JS)
                        items = json.loads(raw)
                        if isinstance(items, str):
                            items = json.loads(items)
                        if items:
                            break
                    except Exception:
                        items = []
            results[handle] = {'query': q, 'url': url, 'items': items}
            json.dump(results, open(OUT, 'w'), ensure_ascii=False, indent=1)
            top = items[0] if items else None
            print(f"[{n}/{len(NO_PCC)}] {handle[:32]:32} | {q[:26]:26} | "
                  f"{('OK ' + top['path'][:40] + ' ' + top['price']) if top else 'SIN RESULTADOS'}", flush=True)
            await tab.sleep(3)

    # reintento de la ficha del Momentum con sesión caliente
    await tab.get(MOMENTUM)
    ok3, title = await wait_clear(tab, 90)
    if ok3:
        await tab.sleep(2)
        raw = await tab.evaluate("""
        (() => {
          const res = {lds: [], title: document.title};
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
          return JSON.stringify(res);
        })()
        """)
        try:
            data = json.loads(raw)
            if isinstance(data, str):
                data = json.loads(data)
        except Exception:
            data = {}
        prev = json.load(open('/home/z/my-project/data/pcc_live.json'))
        prev['sennheiser-momentum-true-wireless-4'] = {'url': MOMENTUM, **data}
        json.dump(prev, open('/home/z/my-project/data/pcc_live.json', 'w'), ensure_ascii=False, indent=1)
        print(f"MOMENTUM: {len(data.get('lds') or [])} LDPs | {str(data.get('title'))[:50]}", flush=True)
        for x in (data.get('lds') or [])[:6]:
            off = x.get('offers') or {}
            print('  -', str(x.get('name'))[:46], '| sku:', x.get('sku'), '|', off.get('price'), '|', (off.get('seller') or {}).get('name'), '|', str(off.get('availability', '')).split('/')[-1], flush=True)
    else:
        print('MOMENTUM: reto no superado', flush=True)
    try:
        await browser.stop()
    except Exception:
        pass


asyncio.run(main())
