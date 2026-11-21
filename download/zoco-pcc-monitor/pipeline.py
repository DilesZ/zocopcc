#!/usr/bin/env python3
"""Orquestador del proceso completo: Zococity (directo) → PCComponentes (directo) → fusión → data.json.

Modo de uso:
    python3 pipeline.py                     # completo (~10-15 min)
    python3 pipeline.py --limit 2           # solo 2 productos (prueba rápida)
    python3 pipeline.py --skip-search       # sin verificación del buscador (más rápido)
"""
import json, os, re, shutil, sys, threading, time
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


def write_json_atomic(path, payload):
    """Escribe primero en un temporal y sustituye al final.

    Un corte a mitad de escritura no puede dejar data.json truncado; el
    workflow puede reintentar el scraping sin perder la instantanea anterior.
    """
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)




def merge_store_offer(rec, store, offer, previous, catalog_url=None):
    """Conserva el último dato confirmado si la lectura de una tienda falla."""
    offer = offer or {}
    fields = ('title', 'price', 'seller', 'stock', 'sku', 'ean', 'url', 'source')
    if offer.get('status') == 'matched':
        rec[f'title_{store}'] = offer.get('title')
        rec[f'price_{store}'] = offer.get('price')
        rec[f'seller_{store}'] = offer.get('seller') or None
        rec[f'stock_{store}'] = offer.get('availability')
        rec[f'sku_{store}'] = offer.get('sku') or None
        rec[f'ean_{store}'] = offer.get('ean')
        rec[f'url_{store}'] = offer.get('url') or catalog_url
        observed = offer.get('observed_at') or datetime.now(ZoneInfo('Europe/Madrid')).isoformat(timespec='seconds')
        source_label = offer.get('source') or f'Ficha {store.title()} en directo'
        rec[f'source_{store}'] = f'{source_label} · {observed[:16].replace("T", " ")}'
        rec[f'{store}_live'] = bool(offer.get('live', True))
        rec[f'{store}_status'] = 'matched'
        rec.pop(f'note_{store}', None)
        rec.pop(f'{store}_blocked_at', None)
        return
    had_value = previous.get(f'price_{store}') is not None
    for field in fields:
        key = f'{field}_{store}'
        rec[key] = previous.get(key)
    rec[f'url_{store}'] = rec.get(f'url_{store}') or offer.get('url') or catalog_url
    rec[f'{store}_live'] = False
    rec[f'{store}_status'] = 'stale' if had_value else offer.get('status', 'unresolved')
    blocked_at = offer.get('blocked_at')
    if not blocked_at and rec.get(f'{store}_status') == 'blocked':
        blocked_at = previous.get(f'{store}_blocked_at')
    if blocked_at:
        rec[f'{store}_blocked_at'] = blocked_at
    else:
        rec.pop(f'{store}_blocked_at', None)
    if offer.get('status') == 'cancelled':
        rec[f'note_{store}'] = 'Lectura cancelada antes de completar esta tienda.'
    elif offer.get('error'):
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
            merge_store_offer(rec, store, (retailers.get(store) or {}).get(h), previous,
                              catalog_url=p.get(f'url_{store}'))
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
    prev_gen = previous_snapshot.get('generated_at')
    prev = {}
    for r in previous_snapshot.get('products') or []:
        rec = dict(r)
        if prev_gen:
            rec.setdefault('_snapshot_generated_at', prev_gen)
        prev[rec.get('handle')] = rec

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

    # 4) Carrefour y Fnac: lectura directa de las fichas públicas configuradas.
    retailer_products = []
    for p in products:
        zp = zoco.get(p['handle']) or {}
        pp = prev.get(p['handle']) or {}
        retailer_products.append({**p, 'ean': zp.get('ean') or pp.get('ean') or p.get('ean')})
    retailers = {}
    for store, fetcher in (('carrefour', fetch_carrefour), ('fnac', fetch_fnac)):
        retailers[store] = fetcher(retailer_products, prev, on_progress=cb, cancel=cancel)

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
            'carrefour_source': 'Fichas oficiales por URL de producto y EAN exacto',
            'fnac_source': 'Fichas oficiales por URL de producto y EAN exacto',
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
            write_json_atomic(os.path.join(BASE, 'data_test.json'), snapshot)
        else:
            if os.path.exists(DATA):
                shutil.copy2(DATA, DATA_PREV)
            write_json_atomic(DATA, snapshot)
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
