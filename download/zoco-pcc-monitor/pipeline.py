#!/usr/bin/env python3
"""Orquestador del proceso completo: Zococity (directo) → PCComponentes (directo) → fusión → data.json.

Modo de uso:
    python3 pipeline.py                     # completo (~10-15 min)
    python3 pipeline.py --limit 2           # solo 2 productos (prueba rápida)
    python3 pipeline.py --skip-search       # sin verificación del buscador (más rápido)
"""
import json, os, re, sys, threading, time
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
PRODUCTS = os.path.join(BASE, 'products.json')
DATA = os.path.join(BASE, 'data.json')
DATA_PREV = os.path.join(BASE, 'data_prev.json')

from zoco_fetcher import fetch_products
from pcc_fetcher import fetch_fichas, verify_search, pick_offer, seller_of, avail_of, parse_card_price

DATA_LOCK = threading.Lock()


def load_json(path, default):
    try:
        return json.load(open(path, encoding='utf-8'))
    except Exception:
        return default


def merge(products, zoco, fichas, buscador, prev):
    """Fusiona las lecturas en directo con la caché previa como respaldo."""
    out = []
    for p in products:
        h = p['handle']
        rec = {'handle': h, 'cat': p.get('cat'), 'brand': p.get('brand') or ''}
        # --- Zoco (directo; respaldo: caché previa) ---
        z = zoco.get(h)
        if z and not z.get('error'):
            rec['title_zoco'] = z.get('title') or p.get('query')
            rec['price_zoco'] = (z.get('price_cents') or 0) / 100 if z.get('price_cents') else None
            rec['stock_zoco'] = z.get('available')
            rec['sku_zoco'] = z.get('sku')
            rec['ean'] = z.get('ean')
            rec['zoco_live'] = True
        else:
            zp = prev.get(h) or {}
            rec['title_zoco'] = zp.get('title_zoco') or p.get('query')
            rec['price_zoco'] = zp.get('price_zoco')
            rec['stock_zoco'] = zp.get('stock_zoco')
            rec['sku_zoco'] = zp.get('sku_zoco')
            rec['ean'] = zp.get('ean')
            rec['zoco_live'] = False
        rec['url_zoco'] = 'https://zococity.es/products/' + h

        # --- PCC (ficha en directo) ---
        f = fichas.get(h)
        lds = (f or {}).get('lds') or []
        chosen = crit = None
        if lds:
            chosen, crit = pick_offer(lds)
        if chosen:
            off = chosen['off']
            rec['in_pcc'] = True
            rec['title_pcc'] = chosen['ld'].get('name')
            rec['price_pcc'] = chosen['price']
            rec['code_pcc'] = chosen['ld'].get('sku')
            rec['seller_pcc'] = seller_of(off)
            rec['pcc_avail'] = avail_of(off)
            gtin = chosen['ld'].get('gtin')
            if gtin:
                rec['ean_pcc'] = str(gtin)
            own = [x for x in lds if 'pccomponentes' in seller_of(x.get('offers') or {}).lower()]
            rec['pcc_own_avail'] = avail_of(own[0]['offers']) if own else None
            rec['source_pcc'] = f'Ficha PCC en directo · {datetime.now().strftime("%d/%m/%Y %H:%M")}'
            rec['url_pcc'] = f.get('url') or p.get('url_pcc')
            rec['pcc_live'] = True
        elif (f or {}).get('lds') is not None and f.get('title') == 'Página no encontrada':
            # ficha conocida retirada → verificar por buscador más abajo
            rec['in_pcc'] = None
        else:
            # respaldo: caché previa
            zp = prev.get(h) or {}
            rec['in_pcc'] = zp.get('in_pcc')
            rec['title_pcc'] = zp.get('title_pcc')
            rec['price_pcc'] = zp.get('price_pcc')
            rec['code_pcc'] = zp.get('code_pcc')
            rec['seller_pcc'] = zp.get('seller_pcc')
            rec['pcc_avail'] = zp.get('pcc_avail')
            rec['source_pcc'] = zp.get('source_pcc')
            rec['url_pcc'] = zp.get('url_pcc') or p.get('url_pcc')
            rec['pcc_live'] = False
            rec['note_pcc'] = zp.get('note_pcc')

        # --- Buscador interno (verificación de ausencias / fichas nuevas) ---
        sr = (buscador or {}).get(h)
        if sr and sr.get('items'):
            from urllib.parse import quote
            # 1) ¿la tarjeta coincide con el modelo? (tokens del query en el path o el texto)
            toks = [t for t in re.split(r'[\s\-+]+', (p.get('query') or '').lower()) if len(t) >= 3]
            toks = [t for t in toks if t not in ('the', 'and', 'con', 'para')]
            def score(it):
                s = (it.get('path') + ' ' + it.get('text')).lower()
                return sum(1 for t in toks if t in s)
            best = max(sr['items'], key=score)
            ok_match = score(best) >= max(2, min(3, len(toks) - 1))
            pr = parse_card_price(best.get('text'))
            if ok_match and pr and not rec.get('in_pcc'):
                rec['in_pcc'] = True
                rec['title_pcc'] = best.get('text', '')[:90]
                rec['price_pcc'] = pr
                rec['source_pcc'] = f'Buscador interno PCC (tarjeta) · {datetime.now().strftime("%d/%m/%Y %H:%M")}'
                rec['url_pcc'] = 'https://www.pccomponentes.com/' + best.get('path')
                rec['pcc_live'] = True
            elif not ok_match and not rec.get('in_pcc') and p.get('verified_no_pcc'):
                rec['in_pcc'] = False
                rec['note_pcc'] = 'Sin ficha en PCComponentes (verificado en buscador interno en directo)'
        if rec.get('in_pcc') is None:
            prev_h = prev.get(h) or {}
            if prev_h.get('in_pcc') is not None:
                rec['in_pcc'] = prev_h.get('in_pcc')
            else:
                rec['in_pcc'] = False
        if not rec.get('in_pcc') and not rec.get('note_pcc') and p.get('note'):
            rec['note_pcc'] = p.get('note')
        out.append(rec)
    return out


def run(on_progress=None, cancel=None, limit=None, skip_search=False):
    """Ejecuta el proceso completo y reescribe data.json. Devuelve (n_fichas, n_buscador)."""
    cancel = cancel or {}
    products = load_json(PRODUCTS, [])
    if limit:
        products = products[:limit]
    prev = {r.get('handle'): r for r in load_json(DATA, {}).get('products') or []}

    def cb(phase, n, total, current):
        if on_progress:
            on_progress(phase, n, total, current)

    # 1) Zococity en directo
    handles = [p['handle'] for p in products]
    zoco = fetch_products(handles, on_progress=cb, cancel=cancel)

    # 2) Fichas de PCComponentes en directo (solo las con URL conocida)
    urls = {p['handle']: p['url_pcc'] for p in products if p.get('url_pcc')}
    urls = {h: u for h, u in urls.items() if h in set(handles)}
    fichas = fetch_fichas(urls, on_progress=cb, cancel=cancel)

    # 3) Verificación de los sin ficha conocida vía buscador interno
    buscador = {}
    if not skip_search:
        queries = {p['handle']: p.get('query') for p in products
                   if not p.get('url_pcc') and p['handle'] in set(handles)}
        if queries:
            buscador = verify_search(queries, on_progress=cb, cancel=cancel)

    # 4) Fusión y escritura
    records = merge(products, zoco, fichas, buscador, prev)
    snapshot = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'meta': {
            'zoco_source': 'Catálogo Shopify de zococity.es leído en directo (XHR /products/<handle>.js vía nodriver)',
            'pcc_source': 'Fichas oficiales de pccomponentes.com leídas en directo (JSON-LD vía nodriver, supera Cloudflare)',
            'limit': limit, 'skip_search': skip_search,
            'n_zoco': sum(1 for r in records if r.get('zoco_live')),
            'n_fichas': sum(1 for r in records if r.get('pcc_live') and (r.get('source_pcc') or '').startswith('Ficha')),
            'n_buscador': len(buscador),
        },
        'products': records,
    }
    with DATA_LOCK:
        if limit:
            # las actualizaciones de prueba (limit=N) no tocan el snapshot principal
            json.dump(snapshot, open(os.path.join(BASE, 'data_test.json'), 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=1)
        else:
            if os.path.exists(DATA):
                os.replace(DATA, DATA_PREV)
            json.dump(snapshot, open(DATA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return snapshot


if __name__ == '__main__':
    limit = skip = None
    args = sys.argv[1:]
    if '--limit' in args:
        limit = int(args[args.index('--limit') + 1])
    skip = '--skip-search' in args
    t0 = time.time()
    snap = run(on_progress=lambda ph, n, t, c: print(f'[{ph}] {n}/{t} · {c}', flush=True),
               limit=limit, skip_search=bool(skip))
    n_pcc = sum(1 for r in snap['products'] if r.get('in_pcc'))
    print(f"OK en {time.time()-t0:.0f}s: {len(snap['products'])} productos | en PCC: {n_pcc} | "
          f"zoco directo: {snap['meta']['n_zoco']} | fichas PCC: {snap['meta']['n_fichas']}")
