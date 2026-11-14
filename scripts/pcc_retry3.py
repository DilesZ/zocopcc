#!/usr/bin/env python3
"""Reintento: ficha HD550 en directo + precios de las tarjetas del buscador para el Momentum."""
import asyncio, json

HD550 = 'https://www.pccomponentes.com/auriculares-sennheiser-con-cable-circumaurales-abiertos-alta-fidelidad-150-ohm'
MOM_Q = 'https://www.pccomponentes.com/buscar/?query=Sennheiser+Momentum+True+Wireless+4+grafito+negro'

LDP_JS = """
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
          if (x['@type'] === 'Product') res.lds.push({name: x.name, sku: x.sku, gtin: x.gtin13 || x.ean || null, offers: x.offers});
          for (const v of Object.values(x)) if (v && typeof v === 'object') st.push(v);
        }
      }
    } catch(e) {}
  }
  return JSON.stringify(res);
})()
"""

CARDS_JS = """
(() => {
  const base = 'https://www.pccomponentes.com/';
  const out = [];
  const seen = new Set();
  document.querySelectorAll('a[href]').forEach(a => {
    const href = a.href || '';
    if (!href.startsWith(base)) return;
    const path = href.slice(base.length).replace(/\\?.*$/, '').replace(/#.*$/, '');
    if (!path || path.split('/').length !== 1) return;
    if (path.startsWith('buscar') || path.startsWith('marcas') || path.startsWith('opiniones')) return;
    if (seen.has(path)) return;
    const card = a.closest('article') || a.closest('li') || a.parentElement;
    const txt = (card ? card.innerText : a.innerText || '').replace(/\\s+/g, ' ').trim();
    const pm = txt.match(/([0-9]{1,4}(?:[.][0-9]{3})*|[0-9]{1,5})(?:[.,][0-9]{2})?\\s*€/);
    if (!txt || !pm) return;
    seen.add(path);
    out.push({path: path, text: txt.slice(0, 180), price: pm[0]});
  });
  return JSON.stringify(out.slice(0, 8));
})()
"""


async def wait_clear(tab, max_s=75):
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
    results = json.load(open('/home/z/my-project/data/pcc_live.json'))

    # 1) buscador Momentum (tarjetas)
    tab = await browser.get(MOM_Q)
    ok, t = await wait_clear(tab)
    print('BUSCADOR:', t[:40] if ok else 'RETO', flush=True)
    if ok:
        cards = []
        for _ in range(6):
            await tab.sleep(3)
            try:
                raw = await tab.evaluate(CARDS_JS)
                cards = json.loads(raw)
                if isinstance(cards, str):
                    cards = json.loads(cards)
                if cards:
                    break
            except Exception:
                cards = []
        prev = json.load(open('/home/z/my-project/data/pcc_search_live.json'))
        prev['sennheiser-momentum-true-wireless-4'] = {'query': 'Sennheiser Momentum True Wireless 4 grafito negro', 'url': MOM_Q, 'items': cards}
        json.dump(prev, open('/home/z/my-project/data/pcc_search_live.json', 'w'), ensure_ascii=False, indent=1)
        for c in cards[:5]:
            print('  CARD:', c['path'][:70], '|', c['price'], flush=True)

    # 2) ficha HD550
    await tab.get(HD550)
    ok, t = await wait_clear(tab)
    print('HD550:', t[:60] if ok else 'RETO', flush=True)
    if ok:
        await tab.sleep(2)
        raw = await tab.evaluate(LDP_JS)
        data = json.loads(raw)
        if isinstance(data, str):
            data = json.loads(data)
        results['sennheiser-hd-550'] = {'url': HD550, **data}
        json.dump(results, open('/home/z/my-project/data/pcc_live.json', 'w'), ensure_ascii=False, indent=1)
        for x in (data.get('lds') or [])[:3]:
            off = x.get('offers') or {}
            print('  HD550 LDP:', str(x.get('name'))[:44], '| sku:', x.get('sku'), '|', off.get('price'), '|', (off.get('seller') or {}).get('name'), flush=True)
    try:
        await browser.stop()
    except Exception:
        pass


asyncio.run(main())
