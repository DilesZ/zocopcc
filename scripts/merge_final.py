#!/usr/bin/env python3
"""Fusiona datos de Zococity + PCComponentes (pasadas 3/4 + adjudicación manual) en final_dataset.json."""
import json, re, sys, time
sys.path.insert(0, '/home/z/my-project/scripts')
from pcc_pipeline import QUERIES, parse_price, search, collect_pcc, collect_aggregators

ZOCO = '/home/z/my-project/data/zoco_details.json'
POOL = '/home/z/my-project/data/zoco_pool_full.json'
P3 = '/home/z/my-project/data/pcc_pass3.json'
P4 = '/home/z/my-project/data/pcc_pass4.json'
OUT = '/home/z/my-project/data/final_dataset.json'

PCC_BASE = 'https://www.pccomponentes.com/'
ZOCO_BASE = 'https://zococity.es/products/'

# Adjudicación manual: handle -> dict(precio, fuente, slug_url, cod, nota)
# None en precio = sin dato fiable; 'NO' = no localizado en PCC.
ADJ = {
    'audio-technica-ath-m50x': dict(price=141.30, src='ficha-PCC', url='audio-technica-ath-m50x-auriculares-de-estudio-cerrados'),
    'sennheiser-momentum-true-wireless-4': dict(price=229.00, src='ficha-PCC (shopping)', url='sennheiser-momentum-true-wireless-4-auriculares-bluetooth-con-cancelacion-de-ruido-grafito-negro', vendido_pcc=True, envio_gratis=True, entrega=True, nota='Precio Grafito Negro; violeta 243,90 vendido por PCComponentes'),
    'sennheiser-accentum-wireless': dict(price=159.00, src='ficha-PCC', url='sennheiser-accentum-wireless-auriculares-inalambricos-bluetooth-con-cancelacion-de-ruido-negros', nota='Negros; otros vendedores en PCC desde 128,29'),
    'denon-ah-c630w': dict(price=67.99, src='ficha-PCC', url='denon-ah-c630w-auriculares-bluetooth-negros', nota='Precio con descuento actual'),
    'audio-technica-ath-twx7': dict(price=159.99, src='ficha-PCC (shopping)', url='audio-technica-ath-twx7-auriculares-inalambricos-con-estuche-de-carga-blanco', nota='Negro 159,99; blanco 149,06 (Cod. art. 10814116)'),
    'denon-pma-600ne': dict(price=395.00, src='ficha-PCC (shopping)', url='denon-pma-600ne-amplificador-integrado-bluetooth-70w-20-canales-negro', vendido_pcc=True, nota='Precio total con envío 402,16'),
    'yamaha-as301': dict(price=498.99, src='ficha-PCC (shopping)', url='yamaha-a-s301-amplificador-hibrido-stereo-negro', vendido_pcc=True, envio_gratis=True, entrega=True),
    'yamaha-as201': dict(price=205.99, src='ficha-PCC', url='yamaha-a-s201-amplificador-hi-fi-negro', vendido_pcc=True),
    'audio-technica-at-lp120x': dict(price=307.99, src='ficha-PCC (shopping)', url='audio-technica-lp120x-tocadiscos-usb-negro', vendido_pcc=True),
    'audio-technica-at-lp60xbt': dict(price=170.99, src='agregador (cita PCC)', url='audio-technica-lp60xbt-tocadiscos-bluetooth-negro', nota='Precio propio PCC 172,93'),
    'audio-technica-at-lp3xbt': dict(price=282.74, src='ficha-PCC (shopping)', url='audio-technica-at-lp3xbtbk-plato-dj-bluetooth-traccion-por-correa-negro', vendido_pcc=True, envio_gratis=True),
    'audio-technica-at-lpw30tk': dict(price=345.95, src='ficha-PCC', url='tocadiscos-audio-technica-at-lpw30tk-manual-madera-preamplificador-integrado', nota='Precio «desde»'),
    'denon-dp-400': dict(price=538.99, src='ficha-PCC', url='denon-dp-400-giradiscos-negro', nota='Tabla comparativa de la ficha PCC'),
    'edifier-s1000mkii': dict(price=299.31, src='ficha-PCC (marketplace)', url='edifier-s1000-mkii-altavoces-hifi-20-madera', nota='Vendido por MORELE dentro de PCComponentes'),
    'edifier-r1855db': dict(price=159.99, src='agregador (cita PCC)', url=None, vendido_pcc=True, nota='Oferta «Vendido y enviado por PCComponentes»; URL de ficha no indexada'),
    'edifier-r2000db': dict(price=229.98, src='ficha-PCC (shopping)', url='edifier-r2000db-altavoces-bluetooth-120w-rms-negro', vendido_pcc=True, envio_gratis=True, entrega=True),
    'edifier-qd35': dict(price=None, src=None, url='edifier-qd35-altavoz-inalambrico-bluetooth-de-mesa-40w-negro', in_pcc=True, nota='En catálogo de PCC; precio no verificado por el índice'),
    'edifier-g7000': dict(price=356.99, src='agregador (cita PCC)', url='edifier-g7000-barra-de-sonido-bluetooth-71', vendido_pcc=True, nota='Precio PCC muy superior a la oferta vigente de Zococity'),
    'sonos-beam-gen-2': dict(price=269.99, src='ficha-PCC (shopping)', url='sonos-beam-gen2-barra-de-sonido-multiroom-wi-fi-negra', vendido_pcc=True),
    'denon-dht-s217': dict(price=169.99, src='ficha-PCC', url='denon-dht-s217-barra-de-sonido-dolby-atmos-21'),
    'bose-tv-speaker': dict(price=196.59, src='ficha-PCC (shopping)', url='bose-tv-speaker-barra-de-sonido-con-conectividad-bluetooth', nota='«Precio total» según tarjeta de Google Shopping'),
    'sonos-era-100': dict(price=279.99, src='agregador (cita PCC)', url='sonos-era-100-altavoz-bluetooth-negro', nota='Blanco 279,99 vendido por PCC; negro 299; ofertas citadas desde 229'),
    'eversolo-dmp-a6-gen-2': dict(price=None, src=None, url=None, in_pcc=False, nota='En PCC solo la versión DMP-A6 Master Edition Gen 2 (1.299 €)'),
    'yamaha-rx-v6a': dict(price=853.23, src='agregador (cita PCC)', url='yamaha-rx-v6a-receptor-av-4k-72-canales-wifi-bluetooth-negro', nota='Precio rastreado por comparador el 07/09/2026'),
    'fiio-dm13': dict(price=163.02, src='agregador (cita PCC)', url=None, nota='Ofertas en la ficha PCC entre 163,02 y 200; versión BT transparente 181,99'),
    'denon-dcd-900ne': dict(price=408.99, src='ficha-PCC', url='denon-dcd900-reproductor-cd-hifi-negro', nota='Tabla de ofertas de la ficha PCC'),
    'sonos-ray': dict(price=299.00, src='agregador (cita PCC)', url='sonos-ray-barra-de-sonido-wifi-negra', nota='-18% frente a 369; ofertas de la ficha desde 289,99'),
    'sennheiser-hd-560s': dict(price=162.99, src='ficha-PCC', url='sennheiser-hd-560s-auriculares-gaming-con-cable-jack-3-5-negro', envio_gratis=True),
    'fiio-ft3': dict(price=None, src=None, url='fiio-ft3-32-ohm-auriculares-hifi-negros', in_pcc=True, nota='Existe ficha en PCC (versión 32 Ω) pero el índice no publica precio'),
    'denon-avr-x2800h': dict(price=None, src=None, url='denon-avr-x2800h-receptor-av-72-canales-dolby-atmos-8k-bluetooth', in_pcc=True, nota='En catálogo de PCC; precio no verificado por el índice'),
    'edifier-r1280db': dict(price=92.65, src='ficha-PCC (shopping)', url='edifier-r1280db-altavoces-bluetooth-21w-rms-negro', vendido_pcc=True, nota='PVPR PCC 109,99; -15% actualmente'),
}
# EAN conocidos fuera de las fichas consultadas
EAN_EXTRA = {'edifier-r1280db': '6923520265688'}

# Productos sin presencia en PCC (varias rondas de búsqueda sin ficha con precio)
NO_PCC = {
    'hifiman-sundara', 'grado-sr80x', 'topping-l50', 'topping-dx1', 'smsl-a2',
    'ifi-audio-zen-air-dac-2', 'rekkord-audio-f110', 'dual-cs418',
    'klipsch-the-fives-v2', 'kef-lsx-ii', 'dali-oberon-1c', 'triangle-ln01a',
    'bluesound-powernode-edge', 'arylic-s50-pro', 'edifier-r1080bt',
    'fiio-ft5', 'sennheiser-hd800s', 'sennheiser-hd-550', 'marantz-pm6007',
    'marantz-nr1510', 'fosi-audio-merak-cd-player', 'nad-d3020-v2',
    'cambridge-audio-axa25', 'meze-audio-109-pro',
}

# Sustitución de producto (mejor comparable en ambas tiendas)
SWAP = {
    'edifier-r1080bt': 'edifier-r1280db',
}
SWAP_EXTRA = {
    'edifier-r1280db': dict(cat='Altavoces activos', brand='Edifier', title='Edifier R1280DB',
                            sku='R1280DB-Negro', ean='6923520265688', price=109.99, stock=True,
                            url=ZOCO_BASE + 'edifier-r1280db',
                            price_pcc=92.65, src='ficha-PCC (shopping)',
                            url_pcc=PCC_BASE + 'edifier-r1280db-altavoces-bluetooth-21w-rms-negro',
                            vendido_pcc=True, nota='PVPR PCC 109,99; -15% actualmente'),
}

# Ruta P4 para productos pendientes de la pasada final
P4_HANDLES = {'fiio-ft5', 'fiio-ft3', 'sennheiser-hd800s', 'sennheiser-hd-550', 'sennheiser-hd-560s',
              'marantz-pm6007', 'edifier-qd35', 'sonos-ray', 'denon-avr-x2800h', 'marantz-nr1510',
              'fosi-audio-merak-cd-player', 'nad-d3020-v2', 'cambridge-audio-axa25', 'meze-audio-109-pro'}

CATS = {
    'fiio-ft5': 'Auriculares HiFi', 'fiio-ft3': 'Auriculares HiFi', 'sennheiser-hd800s': 'Auriculares HiFi',
    'sennheiser-hd-550': 'Auriculares HiFi', 'sennheiser-hd-560s': 'Auriculares HiFi',
    'hifiman-sundara': 'Auriculares HiFi', 'meze-audio-109-pro': 'Auriculares HiFi', 'grado-sr80x': 'Auriculares HiFi',
    'audio-technica-ath-m50x': 'Auriculares HiFi',
    'sennheiser-momentum-true-wireless-4': 'Auriculares Bluetooth', 'sennheiser-accentum-wireless': 'Auriculares Bluetooth',
    'denon-ah-c630w': 'Auriculares Bluetooth', 'audio-technica-ath-twx7': 'Auriculares Bluetooth',
    'topping-l50': 'DAC / Amplificador', 'topping-dx1': 'DAC / Amplificador', 'smsl-a2': 'DAC / Amplificador',
    'ifi-audio-zen-air-dac-2': 'DAC / Amplificador',
    'marantz-pm6007': 'Amplificador integrado', 'denon-pma-600ne': 'Amplificador integrado',
    'yamaha-as301': 'Amplificador integrado', 'yamaha-as201': 'Amplificador integrado',
    'nad-d3020-v2': 'Amplificador integrado', 'cambridge-audio-axa25': 'Amplificador integrado',
    'audio-technica-at-lp120x': 'Tocadiscos', 'audio-technica-at-lp60xbt': 'Tocadiscos',
    'audio-technica-at-lp3xbt': 'Tocadiscos', 'audio-technica-at-lpw30tk': 'Tocadiscos',
    'denon-dp-400': 'Tocadiscos', 'rekkord-audio-f110': 'Tocadiscos', 'dual-cs418': 'Tocadiscos',
    'edifier-s1000mkii': 'Altavoces activos', 'edifier-r1280db': 'Altavoces activos', 'edifier-r1855db': 'Altavoces activos',
    'edifier-r2000db': 'Altavoces activos', 'edifier-qd35': 'Altavoces activos', 'edifier-g7000': 'Altavoces activos',
    'klipsch-the-fives-v2': 'Altavoces activos', 'kef-lsx-ii': 'Altavoces activos', 'dali-oberon-1c': 'Altavoces activos',
    'triangle-ln01a': 'Altavoces activos',
    'sonos-ray': 'Barra de sonido', 'sonos-beam-gen-2': 'Barra de sonido', 'denon-dht-s217': 'Barra de sonido',
    'bose-tv-speaker': 'Barra de sonido',
    'sonos-era-100': 'Altavoz Bluetooth',
    'bluesound-powernode-edge': 'Streamers / En red', 'arylic-s50-pro': 'Streamers / En red', 'eversolo-dmp-a6-gen-2': 'Streamers / En red',
    'denon-avr-x2800h': 'Receptor AV', 'yamaha-rx-v6a': 'Receptor AV', 'marantz-nr1510': 'Receptor AV',
    'fiio-dm13': 'Reproductor CD', 'fosi-audio-merak-cd-player': 'Reproductor CD', 'denon-dcd-900ne': 'Reproductor CD',
}


# Correcciones puntuales (título de la colección fuera del límite del JSON, nombres de ficha PCC)
PATCH_ZOCO = {
    'sennheiser-hd-550': dict(title_zoco='Sennheiser HD 550', brand='Sennheiser', sku_zoco='Sennheiser-HD-550-Black',
                              ean='4260752333498'),
}
PATCH_PCC_TITLE = {
    'audio-technica-at-lp120x': 'Audio-Technica LP120X Tocadiscos USB Negro',
    'audio-technica-at-lpw30tk': 'Tocadiscos Audio-Technica AT-LPW30TK manual madera preamplificador integrado',
    'edifier-r1280db': 'Edifier R1280DB Altavoces Bluetooth 21W RMS Negro',
}


def main():
    zoco = json.load(open(ZOCO))
    pool = {p['h']: p for p in json.load(open(POOL))}
    try:
        p4 = json.load(open(P4))
    except Exception:
        p4 = {}
    recs = []
    for handle, cat in CATS.items():
        if handle in SWAP and SWAP[handle] in SWAP_EXTRA:
            e = SWAP_EXTRA[SWAP[handle]]
            recs.append({
                'cat': e['cat'], 'brand': e['brand'], 'title_zoco': e['title'], 'sku_zoco': e['sku'],
                'ean': e['ean'], 'price_zoco': e['price'], 'stock_zoco': e['stock'],
                'url_zoco': e['url'], 'in_pcc': bool(e.get('price_pcc') or e.get('in_pcc')),
                'title_pcc': 'Edifier R1280DB Altavoces Bluetooth 21W RMS Negro',
                'code_pcc': None, 'price_pcc': e.get('price_pcc'), 'source_pcc': e.get('src'),
                'url_pcc': e.get('url_pcc'),
                'pcc_flags': {'vendido_pcc': e.get('vendido_pcc')}, 'note_pcc': e.get('nota'),
            })
            continue
        d = zoco.get(handle)
        if not d:
            p = pool.get(handle)
            v = p['pv'][0] if p and p['pv'] else {}
            d = {'handle': handle, 'title': p['t'] if p else handle, 'sku': v.get('s'),
                 'priceCents': (float(v['p']) * 100 if v.get('p') else None), 'available': str(v.get('a')).lower(),
                 'ean': None}
        pz = d.get('priceCents')
        pz = pz / 100 if pz else None
        rec = {
            'cat': cat, 'brand': (d.get('title') or '').split()[0] if d.get('title') else '',
            'title_zoco': d.get('title') or handle, 'sku_zoco': d.get('sku'),
            'ean': d.get('ean') or EAN_EXTRA.get(handle), 'price_zoco': pz,
            'stock_zoco': None if d.get('available') is None else str(d.get('available')).lower() == 'true',
            'url_zoco': ZOCO_BASE + handle,
            'in_pcc': False, 'title_pcc': None, 'code_pcc': None, 'price_pcc': None,
            'source_pcc': None, 'url_pcc': None, 'pcc_flags': {}, 'note_pcc': None,
        }
        # título y marca exactos del catálogo de Shopify (la ficha HTML puede traer texto de widgets)
        p = pool.get(handle)
        if p:
            rec['title_zoco'] = p['t']
            rec['brand'] = p['v']
            if not rec['sku_zoco'] and p['pv']:
                rec['sku_zoco'] = p['pv'][0].get('s')
            if rec['price_zoco'] is None and p['pv']:
                try:
                    rec['price_zoco'] = float(p['pv'][0]['p'])
                except Exception:
                    pass
            if rec['stock_zoco'] is None and p['pv']:
                rec['stock_zoco'] = bool(p['pv'][0].get('a'))
        adj = ADJ.get(handle)
        if adj:
            rec['in_pcc'] = adj.get('in_pcc', True)
            rec['price_pcc'] = adj.get('price')
            rec['source_pcc'] = adj.get('src')
            rec['url_pcc'] = PCC_BASE + adj['url'] if adj.get('url') else None
            rec['code_pcc'] = adj.get('code')
            rec['note_pcc'] = adj.get('nota')
            flags = {}
            for k in ('vendido_pcc', 'envio_gratis', 'entrega', 'agotado'):
                if adj.get(k):
                    flags[k] = True
            rec['pcc_flags'] = flags
        elif handle in NO_PCC:
            pass
        elif handle in P4_HANDLES and handle in p4:
            e = p4[handle]
            if e.get('price'):
                rec['in_pcc'] = True
                rec['price_pcc'] = e['price']
                rec['source_pcc'] = e['source']
                rec['url_pcc'] = e.get('url')
                rec['code_pcc'] = e.get('pcc_code')
            else:
                rec['note_pcc'] = 'No localizado con precio en PCComponentes tras varias búsquedas'
        # nombre del producto en la ficha de PCC (para verificar el emparejamiento)
        if rec['in_pcc']:
            try:
                p3 = json.load(open(P3))
            except Exception:
                p3 = {}
            name = None
            for src in (p4, p3):
                for x in (src.get(handle) or {}).get('pcc') or []:
                    if rec['url_pcc'] and x.get('url') and x['url'].rstrip('/') == rec['url_pcc'].rstrip('/'):
                        name = x.get('name')
                        break
                if not name and rec.get('price_pcc'):
                    cands = [x for x in (src.get(handle) or {}).get('pcc') or [] if x.get('prices')]
                    if cands:
                        name = cands[0].get('name')
                if name:
                    break
            if not name:
                for x in ((p4.get(handle) or {}).get('agg') or []) + ((p3.get(handle) or {}).get('agg') or []):
                    if x.get('prices'):
                        name = x.get('name')
                        break
            rec['title_pcc'] = (name or rec['title_pcc'])
        if handle in PATCH_ZOCO:
            for k, v in PATCH_ZOCO[handle].items():
                rec[k] = v
        if handle in PATCH_PCC_TITLE:
            rec['title_pcc'] = PATCH_PCC_TITLE[handle]
        recs.append(rec)
    json.dump(recs, open(OUT, 'w'), ensure_ascii=False, indent=1)
    n_pcc = sum(1 for r in recs if r['in_pcc'])
    n_price = sum(1 for r in recs if r['price_pcc'])
    print(f'OK: {len(recs)} productos | en PCC: {n_pcc} | con precio PCC: {n_price}')


if __name__ == '__main__':
    main()
