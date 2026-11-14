#!/usr/bin/env python3
"""Pasada 4: consultas dirigidas para los productos aún sin precio fiable."""
import json, re, sys, time
sys.path.insert(0, '/home/z/my-project/scripts')
from pcc_pipeline import parse_price, search, collect_pcc, collect_aggregators

TARGET = {
    'fiio-ft5': 'FiiO FT5 auriculares precio pccomponentes',
    'fiio-ft3': 'FiiO FT3 auriculares precio pccomponentes',
    'sennheiser-hd800s': 'Sennheiser HD 800 S precio pccomponentes',
    'sennheiser-hd-550': 'Sennheiser HD 550 auriculares precio',
    'sennheiser-hd-560s': 'Sennheiser HD 560S precio pccomponentes',
    'marantz-pm6007': 'Marantz PM6007 precio pccomponentes',
    'edifier-qd35': 'Edifier QD35 precio pccomponentes',
    'sonos-ray': 'Sonos Ray barra sonido precio pccomponentes',
    'denon-avr-x2800h': 'Denon AVR-X2800H precio pccomponentes',
    'marantz-nr1510': 'Marantz NR1510 precio pccomponentes',
    'fosi-audio-merak-cd-player': 'Fosi Audio Merak CD precio pccomponentes',
    'nad-d3020-v2': 'NAD D 3020 V2 precio pccomponentes',
    'cambridge-audio-axa25': 'Cambridge Audio AXA25 precio pccomponentes',
    'meze-audio-109-pro': 'Meze Audio 109 Pro precio pccomponentes',
}
PCC_SELF = re.compile(r'vendido y enviado por pc?componentes|precio total|PVPR|precio m[ií]nimo hist[oó]rico', re.I)
CODE_RE = re.compile(r'Cod\.\s*Art[ií]culo[:\s]*([A-Z0-9]{5,12})', re.I)


def extract(cand):
    for x in cand:
        if PCC_SELF.search(x['snippet']):
            prs = parse_price(x['snippet'])
            if prs:
                m = CODE_RE.search(x['snippet'])
                return prs[0], 'ficha-PCC (shopping)', x['url'], x['name'], (m.group(1) if m else None)
    for x in cand:
        prs = parse_price(x['snippet'])
        if prs:
            m = CODE_RE.search(x['snippet'])
            return prs[0], 'ficha-PCC', x['url'], x['name'], (m.group(1) if m else None)
    return None, None, None, None, None


def main():
    out_path = '/home/z/my-project/data/pcc_pass4.json'
    try:
        out = json.load(open(out_path))
    except Exception:
        out = {}
    for handle, q in TARGET.items():
        if handle in out:
            continue
        res = []
        for attempt in range(2):
            res = search(q, num=10, recency=365)
            if res:
                break
            time.sleep(15)
        cand = collect_pcc(res)
        agg = collect_aggregators(res)
        price, src, url, name, code = extract(cand)
        if price is None and agg:
            price, src, url, name, code = agg[0]['prices'][0], 'agregador (cita PCC)', agg[0]['url'], agg[0]['name'], None
        out[handle] = {'query': q, 'pcc': cand, 'agg': agg, 'price': price,
                       'source': src, 'url': url, 'name': name, 'pcc_code': code}
        json.dump(out, open(out_path, 'w'), ensure_ascii=False, indent=1)
        print(f"{handle[:40]:40} | {str(price):9} | {str(src)[:22]:22} | {len(cand)}/{len(agg)}", flush=True)
        time.sleep(30)
    print('OK pass4')


if __name__ == '__main__':
    main()
