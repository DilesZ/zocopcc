#!/usr/bin/env python3
"""Pasada 3: consulta '<modelo> pccomponentes precio', extractor priorizado y código de artículo PCC."""
import json, re, sys, time
sys.path.insert(0, '/home/z/my-project/scripts')
from pcc_pipeline import QUERIES, parse_price, search, collect_aggregators

PCC_SELF = re.compile(r'vendido y enviado por pc?componentes|precio total|PVPR|precio m[ií]nimo hist[oó]rico', re.I)
CODE_RE = re.compile(r'Cod\.\s*Art[ií]culo[:\s]*([A-Z0-9]{5,12})', re.I)


def extract(entry_candidates):
    """Devuelve (precio, fuente, url, nombre, cod_articulo, extra_flags)."""
    # 1) mejor snippet de la propia PCC
    for x in entry_candidates:
        if not PCC_SELF.search(x['snippet']):
            continue
        prs = parse_price(x['snippet'])
        if prs:
            m = CODE_RE.search(x['snippet'])
            flags = {
                'agotado': x.get('agotado'),
                'vendido_pcc': x.get('vendido_pcc'),
                'envio_gratis': x.get('envio_gratis'),
                'entrega': x.get('entrega'),
            }
            return prs[0], 'ficha-PCC (shopping)', x['url'], x['name'], (m.group(1) if m else None), flags
    # 2) primer snippet PCC con precio
    for x in entry_candidates:
        prs = parse_price(x['snippet'])
        if prs:
            m = CODE_RE.search(x['snippet'])
            flags = {
                'agotado': x.get('agotado'),
                'vendido_pcc': x.get('vendido_pcc'),
                'envio_gratis': x.get('envio_gratis'),
                'entrega': x.get('entrega'),
            }
            return prs[0], 'ficha-PCC', x['url'], x['name'], (m.group(1) if m else None), flags
    # 3) agregadores que citan pccomponentes
    return None, None, None, None, None, {}


def main():
    out_path = sys.argv[1]
    try:
        prev = json.load(open('/home/z/my-project/data/pcc_results.json'))
    except Exception:
        prev = {}
    out = {}
    for handle, model in QUERIES.items():
        q = model + ' pccomponentes precio'
        res = []
        for attempt in range(2):
            res = search(q, num=10, recency=90)
            if res:
                break
            time.sleep(12)
        from pcc_pipeline import collect_pcc
        cand = collect_pcc(res)
        agg = collect_aggregators(res)
        price, src, url, name, code, flags = extract(cand)
        if price is None and agg:
            # buscar en los agregadores el texto que cite pccomponentes con precio más cercano al PVP
            price, src, url, name, code = agg[0]['prices'][0], 'agregador (cita PCC)', agg[0]['url'], agg[0]['name'], None
        out[handle] = {
            'query': q, 'pcc': cand, 'agg': agg,
            'price': price, 'source': src, 'url': url, 'name': name,
            'pcc_code': code, 'flags': flags,
        }
        json.dump(out, open(out_path, 'w'), ensure_ascii=False, indent=1)
        print(f"{handle[:38]:38} | {model[:26]:26} | {str(price):9} | {str(src)[:20]:20} | cod:{code} | {'/'.join([str(len(cand)), str(len(agg))])}", flush=True)
        time.sleep(7)
    print('OK, total:', len(out))


if __name__ == '__main__':
    main()
