#!/usr/bin/env python3
"""Genera products.json (config de los 54 productos) y data.json (instantánea) para la app portátil."""
import json
from datetime import datetime

SRC = '/home/z/my-project/data/final_dataset_v2.json'
OUT_DIR = '/home/z/my-project/download/zoco-pcc-monitor'

recs = json.load(open(SRC))

products = []
data_products = []
for r in recs:
    handle = r['url_zoco'].replace('https://zococity.es/products/', '')
    products.append({
        'handle': handle,
        'cat': r['cat'],
        'brand': r.get('brand') or '',
        'query': r.get('title_zoco') or handle,
        'url_pcc': r.get('url_pcc'),
        'verified_no_pcc': not r.get('in_pcc'),
        'note': r.get('note_pcc'),
    })
    data_products.append({
        'handle': handle,
        'cat': r['cat'],
        'brand': r.get('brand') or '',
        'title_zoco': r['title_zoco'],
        'sku_zoco': r.get('sku_zoco'),
        'ean': r.get('ean'),
        'price_zoco': r.get('price_zoco'),
        'stock_zoco': r.get('stock_zoco'),
        'url_zoco': r['url_zoco'],
        'in_pcc': bool(r.get('in_pcc')),
        'title_pcc': r.get('title_pcc'),
        'price_pcc': r.get('price_pcc'),
        'code_pcc': r.get('code_pcc'),
        'seller_pcc': r.get('seller_pcc'),
        'pcc_avail': r.get('pcc_avail'),
        'source_pcc': r.get('source_pcc'),
        'url_pcc': r.get('url_pcc'),
        'note_pcc': r.get('note_pcc'),
    })

import os
os.makedirs(OUT_DIR, exist_ok=True)
json.dump(products, open(f'{OUT_DIR}/products.json', 'w'), ensure_ascii=False, indent=1)

snapshot = {
    'generated_at': datetime.now().isoformat(timespec='seconds'),
    'meta': {
        'zoco_source': 'Catálogo Shopify de zococity.es leído en directo (XHR /products/<handle>.js)',
        'pcc_source': 'Fichas oficiales de pccomponentes.com leídas en directo con navegador automatizado que supera Cloudflare (nodriver)',
        'exceptions': 'Sennheiser Momentum TW4 por índice de búsqueda; Sennheiser HD 550 por tarjeta del buscador interno de PCC; R1855DB y DM13 por índice (agregador)',
    },
    'products': data_products,
}
json.dump(snapshot, open(f'{OUT_DIR}/data.json', 'w'), ensure_ascii=False, indent=1)
print('products.json:', len(products), '| data.json:', len(data_products), 'productos')
