#!/usr/bin/env python3
"""Orquestador del proceso completo: Zococity (directo) → PCComponentes (directo) → fusión → data.json.

Modo de uso:
    python3 pipeline.py                     # completo (~10-15 min)
    python3 pipeline.py --limit 2           # solo 2 productos (prueba rápida)
    python3 pipeline.py --skip-search       # sin verificación del buscador (más rápido)
"""
import json, os, re, sys, threading, time
from datetime import datetime
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
PRODUCTS = os.path.join(BASE, 'products.json')
DATA = os.path.join(BASE, 'data.json')
DATA_PREV = os.path.join(BASE, 'data_prev.json')

from zoco_fetcher import fetch_products
from pcc_fetcher import fetch_fichas, verify_search, pick_offer, seller_of, avail_of, parse_card_price
from fnac_fetcher import fetch_fnac
from carrefour_fetcher import fetch_carrefour

DATA_LOCK = threading.Lock()


def load_json(path, default):
    try:
        return json.load(open(path, encoding='utf-8'))
    except Exception:
        return default




def merge_store_offer(rec, store, offer, previous):
    """Conserva el último dato confirmado si la lectura de una tienda falla."""
    fields = ('title', 'price', 'seller', 'stock', 'sku', 'ean', 'url', 'source')
    if offer and offer.get('status') == 'matched':
        rec[f'title_{store}'] = offer.get('title')
        rec[f'price_{store}'] = offer.get('price')
        rec[f'seller_{store}'] = offer.get('seller') or None
        rec[f'stock_{store}'] = offer.get('availability')
        rec[f'sku_{store}'] = offer.get('sku') or None
        rec[f'ean_{store}'] = offer.get('ean')
        rec[f'url_{store}'] = offer.get('url')
        observed = offer.get('observed_at') or datetime.now(ZoneInfo('Europe/Madrid')).isoformat(timespec='seconds')
        rec[f'source_{store}'] = f'Ficha {store.title()} en directo · {observed[:16].replace("T", " ")}'
        rec[f'{store}_live'] = True
        rec[f'{store}_status'] = 'matched'
        rec.pop(f'note_{store}', None)
        return
    had_value = any(previous.get(f'price_{store}') is not None for _ in (0,))
    for field in fields:
        key = f'{field}_{store}'
        rec[key] = previous.get(key)
        if field == 'url' and not rec[key]:
            rec[key] = (offer or {}).get('url')
    rec[f'{store}_live'] = False
    rec[f'{store}_status'] = 'stale' if had_value else (offer or {}).get('status', 'unresolved')
    if (offer or {}).get('error'):
        rec[f'note_{store}'] = offer['error']
    elif had_value:
        rec[f'note_{store}'] = 'Se conserva el último precio confirmado; la ficha no se verificó en esta actualización.'
    else:
        rec[f'note_{store}'] = 'Sin coincidencia exacta por EAN en una ficha de producto publicada.'


def merge(products, zoco, fichas, buscador, retailers, prev):
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
            rec['source_pcc'] = f'Ficha PCC en directo · {datetime.now(ZoneInfo("Europe/Madrid")).strftime("%d/%m/%Y %H:%M")}'
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
                rec['source_pcc'] = f'Buscador interno PCC (tarjeta) · {datetime.now(ZoneInfo("Europe/Madrid")).strftime("%d/%m/%Y %H:%M")}'
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

        previous = prev.get(h) or {}
        for store in ('carrefour', 'fnac'):
            merge_store_offer(rec, store, (retailers.get(store) or {}).get(h), previous)
        out.append(rec)
    return out


def run(on_progress=None, cancel=None, limit=None, skip_search=False):
    """Ejecuta el proceso completo y reescribe data.json. Devuelve (n_fichas, n_buscador)."""
    cancel = cancel or {}
    products = load_json(PRODUCTS, [])
    if limit:
        products = products[:limit]
    previous_snapshot = load_json(DATA, {})
    previous_meta = previous_snapshot.get('meta') or {}
    prev = {r.get('handle'): r for r in previous_snapshot.get('products') or []}

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

    # 4) Nuevas tiendas: resolver URLs desde sus sitemaps oficiales y validar el EAN exacto.
    retailer_products = []
    for p in products:
        zp = zoco.get(p['handle']) or {}
        pp = prev.get(p['handle']) or {}
        retailer_products.append({**p, 'ean': zp.get('ean') or pp.get('ean')})
    retailers = {
        'carrefour': fetch_carrefour(retailer_products, prev, on_progress=cb, cancel=cancel),
        'fnac': fetch_fnac(retailer_products, prev, on_progress=cb, cancel=cancel),
    }

    # 5) Fusión y escritura
    records = merge(products, zoco, fichas, buscador, retailers, prev)
    generated_at = datetime.now(ZoneInfo('Europe/Madrid')).isoformat(timespec='seconds')
    event_name = os.environ.get('GITHUB_EVENT_NAME', 'manual')
    trigger_type = os.environ.get('TRIGGER_TYPE') or ('automatic' if event_name == 'schedule' else 'manual')
    last_manual_update = previous_meta.get('last_manual_update')
    last_automatic_update = previous_meta.get('last_automatic_update')
    if not limit:
        if trigger_type == 'automatic':
            last_automatic_update = generated_at
        else:
            last_manual_update = generated_at

    snapshot = {
        'generated_at': generated_at,
        'meta': {
            'zoco_source': 'Catálogo Shopify de zococity.es leído en directo (XHR /products/<handle>.js vía nodriver)',
            'pcc_source': 'Fichas oficiales de pccomponentes.com leídas en directo (JSON-LD vía nodriver, supera Cloudflare)',
            'carrefour_source': 'Fichas de producto del sitemap oficial y JSON-LD con EAN exacto',
            'fnac_source': 'Fichas de producto del sitemap oficial y JSON-LD con EAN exacto',
            'limit': limit, 'skip_search': skip_search,
            'n_zoco': sum(1 for r in records if r.get('zoco_live')),
            'n_fichas': sum(1 for r in records if r.get('pcc_live') and (r.get('source_pcc') or '').startswith('Ficha')),
            'n_buscador': len(buscador),
            'n_carrefour': sum(1 for r in records if r.get('carrefour_live')),
            'n_fnac': sum(1 for r in records if r.get('fnac_live')),
            'workflow_run_id': os.environ.get('GITHUB_RUN_ID'),
            'workflow_event': event_name,
            'trigger_type': trigger_type,
            'last_manual_update': last_manual_update,
            'last_automatic_update': last_automatic_update,
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
