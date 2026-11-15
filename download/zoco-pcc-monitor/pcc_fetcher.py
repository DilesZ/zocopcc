#!/usr/bin/env python3
"""Lectura EN DIRECTO de fichas de PCComponentes con navegador real (nodriver).

PCComponentes está tras Cloudflare: bloquea HTTP plano (403/429), la impersonación TLS
(curl_cffi con huella Chrome) NO basta, y los navegadores Selenium/Playwright/puppeteer
estándar quedan atascados en el reto «Just a moment...». La técnica que FUNCIONA:
nodriver (Chrome real no detectable). En Linux sin pantalla: Xvfb + headed.

REGLAS DE ORO (descubiertas a golpe de fallo — no las rompas):
  1. La PRIMERA navegación debe ser la URL objetivo (una ficha), nunca la portada.
  2. NUNCA cierres pestañas (tab.close() mata la sesión y Cloudflare endurece).
  3. Reutiliza SIEMPRE la misma pestaña: la cookie cf_clearance queda ganada.
  4. El reto es «non-interactive»: se resuelve solo esperando. Sondea document.title
     cada 2 s hasta que deje de decir «Just a moment...» (hasta 120 s).
  5. Deja 4-6 s entre fichas. Ráfagas rápidas degradan la reputación de la IP y
     Cloudflare escala a retos que ya no se auto-resuelven (cooldown: 10-30 min).
  6. La extracción se hace con el JSON-LD de la página (script application/ld+json,
     búsqueda recursiva de @type=Product): precio, disponibilidad, vendedor (seller),
     SKU interno (sku) y EAN (gtin13). Múltiples Product = una oferta por vendedor.
  7. tab.evaluate() no espera promesas: nada de fetch().then(); usa XHR síncrono
     o código puro sincrónico.
"""
import asyncio, json, re

from zoco_fetcher import find_chrome, ensure_display, chrome_args, chrome_sandbox, start_browser

PCC_BASE = 'https://www.pccomponentes.com/'

# Extracción de TODAS las ofertas Product del JSON-LD (recursivo, soporta @graph y arrays)
LDP_JS = """
(() => {
  const res = {url: location.href, title: document.title, lds: []};
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
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
  return JSON.stringify(res);
})()
"""

# Tarjetas de resultados del buscador interno (nombre, precio, ruta) — para verificar
# productos sin ficha conocida o para obtener precio cuando la ficha está blindada.
CARDS_JS = """
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


def seller_of(off):
    return ((off.get('seller') or {}).get('name')) or ((off.get('offeredBy') or {}).get('name')) or ''


def avail_of(off):
    a = str(off.get('availability') or '')
    return 'InStock' if 'InStock' in a else ('OutOfStock' if 'OutOfStock' in a else '')


def pick_offer(lds):
    """Elige la oferta representativa de la ficha según reglas probadas.
    Devuelve (ld, criterio) o (None, None)."""
    cands = []
    for x in lds or []:
        off = x.get('offers') or {}
        try:
            p = float(off.get('price'))
        except (TypeError, ValueError):
            continue
        cands.append({'ld': x, 'off': off, 'price': p, 'seller': seller_of(off), 'av': avail_of(off)})
    if not cands:
        return None, None
    own = [c for c in cands if 'pccomponentes' in c['seller'].lower()]
    instock = [c for c in cands if c['av'] == 'InStock']
    own_in = [c for c in own if c['av'] == 'InStock']
    if own_in:
        return min(own_in, key=lambda c: c['price']), 'PcComponentes (propio, en stock)'
    if own:
        return min(own, key=lambda c: c['price']), 'PcComponentes (propio)'
    if instock:
        return min(instock, key=lambda c: c['price']), 'Marketplace en PCC (en stock)'
    return min(cands, key=lambda c: c['price']), 'Marketplace en PCC'


async def _session(start_url):
    import nodriver as uc
    kwargs = ensure_display()
    browser = await start_browser()
    tab = await browser.get(start_url)
    return browser, tab


async def _wait_clear(tab, max_s):
    for _ in range(max_s // 2):
        await tab.sleep(2)
        try:
            t = await tab.evaluate('document.title')
        except Exception:
            continue
        if t and 'moment' not in t.lower():
            return True, t
    return False, ''


async def _run_fichas(url_by_handle, results, on_progress, cancel, max_wait, gap):
    first = True
    items = list(url_by_handle.items())
    for n, (handle, url) in enumerate(items, 1):
        if cancel.get('stop'):
            break
        try:
            if first:
                import nodriver as uc
                browser = await start_browser()
                tab = await browser.get(url)
                first = False
            else:
                await tab.get(url)
            ok, title = await _wait_clear(tab, max_wait)
            if not ok:
                results[handle] = {'url': url, 'title': 'RETO_NO_SUPERADO', 'lds': []}
            else:
                await tab.sleep(2)
                raw = await tab.evaluate(LDP_JS)
                data = json.loads(raw)
                if isinstance(data, str):
                    data = json.loads(data)
                results[handle] = data
        except Exception as e:
            results[handle] = {'url': url, 'title': 'ERROR ' + str(e)[:80], 'lds': []}
        if on_progress:
            on_progress('pcc_fichas', n, len(items), handle)
        try:
            await tab.sleep(gap)
        except Exception:
            pass
    try:
        await browser.stop()
    except Exception:
        pass


async def _run_search(queries_by_handle, results, on_progress, cancel, max_wait=60):
    import nodriver as uc
    kwargs = ensure_display()
    browser = await start_browser()
    first_q = next(iter(queries_by_handle.values()), 'audio')
    tab = await browser.get(PCC_BASE + 'buscar/?query=' + first_q.replace(' ', '+'))
    ok, _ = await _wait_clear(tab, max_wait)
    items_list = list(queries_by_handle.items())
    for n, (handle, q) in enumerate(items_list, 1):
        if cancel.get('stop'):
            break
        if not ok:
            results[handle] = {'query': q, 'items': [], 'error': 'RETO'}
            continue
        await tab.get(PCC_BASE + 'buscar/?query=' + q.replace(' ', '+'))
        ok2, _ = await _wait_clear(tab, max_wait)
        cards = []
        if ok2:
            for _ in range(6):                # espera hidratación del listado
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
        results[handle] = {'query': q, 'items': cards}
        if on_progress:
            on_progress('pcc_buscar', n, len(items_list), handle)
        try:
            await tab.sleep(3)
        except Exception:
            pass
    try:
        await browser.stop()
    except Exception:
        pass


def fetch_fichas(url_by_handle, on_progress=None, cancel=None, max_wait=120, gap=5):
    """Lee fichas de producto en directo. Devuelve {handle: {url, title, lds:[...]}}."""
    cancel = cancel or {}
    out = {}
    if url_by_handle:
        asyncio.run(_run_fichas(dict(url_by_handle), out, on_progress, cancel, max_wait, gap))
    return out


def verify_search(queries_by_handle, on_progress=None, cancel=None):
    """Busca en el buscador interno de PCC y devuelve tarjetas {handle: {query, items}}."""
    cancel = cancel or {}
    out = {}
    if queries_by_handle:
        asyncio.run(_run_search(dict(queries_by_handle), out, on_progress, cancel))
    return out


PRICE_RE = re.compile(r'(\d{1,4}(?:\.\d{3})*|\d{1,5})(?:[.,](\d{2}))?\s*€')


def parse_card_price(txt):
    """'226,08€' → 226.08 (formato español con punto de millar)."""
    m = PRICE_RE.search(txt or '')
    if not m:
        return None
    ent = m.group(1).replace('.', '')
    dec = (m.group(2) or '0')
    try:
        return float(ent + '.' + dec.ljust(2, '0')[:2])
    except ValueError:
        return None


if __name__ == '__main__':
    import sys
    url = sys.argv[1] or 'https://www.pccomponentes.com/audio-technica-ath-m50x-auriculares-de-estudio-cerrados'
    res = fetch_fichas({'test': url})
    d = res['test']
    chosen, crit = pick_offer(d.get('lds'))
    print('título:', d.get('title'))
    print('criterio:', crit)
    if chosen:
        off = chosen['off']
        print('oferta:', chosen['ld'].get('name'), '| sku:', chosen['ld'].get('sku'), '| precio:', off.get('price'), '| vendedor:', seller_of(off))
