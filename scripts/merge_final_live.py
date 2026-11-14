#!/usr/bin/env python3
"""Post-procesa los datos EN DIRECTO (pcc_live.json + pcc_search_live.json) → final_dataset_v2.json.
Reglas de selección de oferta por ficha:
  1) oferta vendida por PcComponentes (preferente en stock)
  2) si no, la oferta más barata en stock
  3) si no, la más barata global
"""
import json, sys
from datetime import datetime

sys.path.insert(0, '/home/z/my-project/scripts')
from merge_final import CATS  # categorías por handle

LIVE = '/home/z/my-project/data/pcc_live.json'
SEARCH = '/home/z/my-project/data/pcc_search_live.json'
BASE = '/home/z/my-project/data/final_dataset.json'
OUT = '/home/z/my-project/data/final_dataset_v2.json'
NOW = '14/11/2026 (lectura en directo)'

# Productos verificados como sin ficha en PCC vía buscador en directo
VERIFIED_NO_PCC = {
    'hifiman-sundara', 'grado-sr80x', 'topping-l50', 'topping-dx1', 'smsl-a2',
    'ifi-audio-zen-air-dac-2', 'rekkord-audio-f110', 'dual-cs418',
    'klipsch-the-fives-v2', 'kef-lsx-ii', 'dali-oberon-1c', 'triangle-ln01a',
    'bluesound-powernode-edge', 'arylic-s50-pro', 'fiio-ft5', 'sennheiser-hd800s',
    'marantz-pm6007', 'marantz-nr1510', 'fosi-audio-merak-cd-player',
    'nad-d3020-v2', 'cambridge-audio-axa25', 'meze-audio-109-pro',
}
# Datos para productos sin ficha legible pero con tarjeta de búsqueda en directo
CARD_FALLBACK = {
    'sennheiser-hd-550': {'price': 226.08, 'path': 'auriculares-sennheiser-con-cable-circumaurales-abiertos-alta-fidelidad-150-ohm',
                          'src': 'Buscador PCC en directo (tarjeta) · 14/11/2026'},
    'sennheiser-momentum-true-wireless-4': {'price': 229.00, 'path': 'sennheiser-momentum-true-wireless-4-auriculares-bluetooth-con-cancelacion-de-ruido-grafito-negro',
                                            'src': 'Índice de búsqueda (Google Shopping) · 14/11/2026'},
}


def seller_of(off):
    return ((off.get('seller') or {}).get('name')) or ((off.get('offeredBy') or {}).get('name')) or ''


def avail_of(off):
    a = str(off.get('availability') or '')
    return 'InStock' if 'InStock' in a else ('OutOfStock' if 'OutOfStock' in a else '')


def pick(lds):
    """Elige (ld, criterio) según las reglas."""
    cands = []
    for x in lds:
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


def main():
    live = json.load(open(LIVE))
    base = json.load(open(BASE))
    try:
        srd = json.load(open(SEARCH))
    except Exception:
        srd = {}
    import os
    try:
        ts = datetime.fromtimestamp(os.path.getmtime(LIVE)).strftime('%H:%M')
    except Exception:
        ts = ''
    updated = 0
    for rec in base:
        h = rec['url_zoco'].replace('https://zococity.es/products/', '')
        if h in VERIFIED_NO_PCC:
            rec['in_pcc'] = False
            rec['price_pcc'] = None
            rec['code_pcc'] = None
            rec['title_pcc'] = None
            rec['source_pcc'] = 'Verificado en buscador de PCC en directo · ' + NOW
            rec['url_pcc'] = None
            rec['pcc_flags'] = {}
            rec['note_pcc'] = 'Sin ficha en PCComponentes el día de la consulta (búsqueda interna verificada)'
            continue
        if h == 'sennheiser-momentum-true-wireless-4':
            cf = CARD_FALLBACK[h]
            rec['in_pcc'] = True
            rec['price_pcc'] = cf['price']
            rec['source_pcc'] = cf['src']
            rec['url_pcc'] = 'https://www.pccomponentes.com/' + cf['path']
            rec['title_pcc'] = 'Sennheiser Momentum True Wireless 4 Auriculares Bluetooth con Cancelación de Ruido Grafito Negro'
            rec['pcc_flags'] = {'envio_gratis': True}
            rec['note_pcc'] = 'Precio del índice (ficha no accesible en directo por protección reforzada); violeta 243,90 vendido por PCC'
            continue
        if h == 'sennheiser-hd-550':
            cf = CARD_FALLBACK[h]
            rec['in_pcc'] = True
            rec['price_pcc'] = cf['price']
            rec['source_pcc'] = cf['src']
            rec['url_pcc'] = 'https://www.pccomponentes.com/' + cf['path']
            rec['title_pcc'] = 'Auriculares Sennheiser con cable, circumaurales abiertos, alta fidelidad, 150 Ohm, negro'
            rec['pcc_flags'] = {'envio_gratis': True}
            rec['note_pcc'] = '«Precio mínimo histórico» en la tarjeta del buscador; SKU/stock no visible en la tarjeta'
            continue
        v = live.get(h)
        if not v or not (v.get('lds') or []):
            continue
        chosen, crit = pick(v['lds'])
        if not chosen:
            continue
        off = chosen['off']
        rec['in_pcc'] = True
        rec['price_pcc'] = chosen['price']
        rec['code_pcc'] = chosen['ld'].get('sku')
        rec['title_pcc'] = chosen['ld'].get('name')
        rec['url_pcc'] = v.get('url') or rec['url_pcc']
        rec['source_pcc'] = f'Ficha PCC en directo · {NOW}' + (f' ({ts})' if ts else '')
        rec['seller_pcc'] = chosen['seller']
        rec['pcc_crit'] = crit
        av = chosen['av']
        own = [x for x in v['lds'] if 'pccomponentes' in seller_of(x.get('offers') or {}).lower()]
        own_av = avail_of(own[0]['offers']) if own else ''
        flags = {}
        if av == 'InStock':
            flags['vendido_pcc'] = 'pccomponentes' in chosen['seller'].lower()
            flags['envio_gratis'] = True
        rec['pcc_flags'] = flags
        rec['note_pcc'] = None
        rec['pcc_avail'] = av
        rec['pcc_own_avail'] = own_av
        # EAN en directo (gtin) para verificación cruzada
        if chosen['ld'].get('gtin'):
            rec['ean_pcc'] = str(chosen['ld'].get('gtin'))
        updated += 1
    # notas puntuales tras la fusión
    byh = {r['url_zoco'].replace('https://zococity.es/products/', ''): r for r in base}
    byh['audio-technica-ath-twx7']['note_pcc'] = 'La ficha en directo corresponde a la variante blanca (la URL del índice ya no existe)'
    byh['yamaha-rx-v6a']['note_pcc'] = 'Única oferta publicada en la ficha (marketplace, PVP anterior); el índice citaba 853,23 € el 07/09/2026'
    for h in ('edifier-r1855db', 'fiio-dm13'):
        r = byh.get(h)
        if r and (r.get('source_pcc') or '').startswith('agregador'):
            r['source_pcc'] = 'Índice de búsqueda (agregador que cita PCC) · 14/11/2026'
    json.dump(base, open(OUT, 'w'), ensure_ascii=False, indent=1)
    n_pcc = sum(1 for r in base if r['in_pcc'])
    n_price = sum(1 for r in base if r['price_pcc'])
    print(f'OK v2: {len(base)} productos | en PCC: {n_pcc} | con precio: {n_price} | actualizados en directo: {updated}')


if __name__ == '__main__':
    main()
