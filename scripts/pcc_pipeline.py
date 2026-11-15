#!/usr/bin/env python3
"""Busca cada producto en PCComponentes vía z-ai web_search y extrae precio/disponibilidad de los snippets.
Uso: python3 pcc_pipeline.py <salida.json> [handle1 handle2 ...]
"""
import json, re, subprocess, sys, time, os

# Consulta manual por handle (precisión de modelo)
QUERIES = {
    'fiio-ft5': 'FiiO FT5',
    'fiio-ft3': 'FiiO FT3',
    'sennheiser-hd800s': 'Sennheiser HD 800S',
    'sennheiser-hd-550': 'Sennheiser HD 550',
    'sennheiser-hd-560s': 'Sennheiser HD 560S',
    'hifiman-sundara': 'Hifiman Sundara',
    'meze-audio-109-pro': 'Meze 109 PRO',
    'grado-sr80x': 'Grado SR80x',
    'audio-technica-ath-m50x': 'Audio-Technica ATH-M50x',
    'sennheiser-momentum-true-wireless-4': 'Sennheiser Momentum True Wireless 4',
    'sennheiser-accentum-wireless': 'Sennheiser Accentum Wireless',
    'denon-ah-c630w': 'Denon AH-C630W',
    'audio-technica-ath-twx7': 'Audio-Technica ATH-TWX7',
    'topping-l50': 'Topping L50',
    'topping-dx1': 'Topping DX1',
    'smsl-a2': 'SMSL A2',
    'ifi-audio-zen-air-dac-2': 'iFi ZEN Air DAC 2',
    'marantz-pm6007': 'Marantz PM6007',
    'denon-pma-600ne': 'Denon PMA-600NE',
    'yamaha-as301': 'Yamaha A-S301',
    'yamaha-as201': 'Yamaha A-S201',
    'nad-d3020-v2': 'NAD D 3020 V2',
    'cambridge-audio-axa25': 'Cambridge Audio AXA25',
    'audio-technica-at-lp120x': 'Audio-Technica AT-LP120XUSB',
    'audio-technica-at-lp60xbt': 'Audio-Technica AT-LP60XBT',
    'audio-technica-at-lp3xbt': 'Audio-Technica AT-LP3XBT',
    'audio-technica-at-lpw30tk': 'Audio-Technica AT-LPW30TK',
    'denon-dp-400': 'Denon DP-400',
    'rekkord-audio-f110': 'Rekkord Audio F110',
    'dual-cs418': 'Dual CS 418',
    'edifier-s1000mkii': 'Edifier S1000MKII',
    'edifier-r1080bt': 'Edifier R1080BT',
    'edifier-r1855db': 'Edifier R1855DB',
    'edifier-r2000db': 'Edifier R2000DB',
    'edifier-qd35': 'Edifier QD35',
    'edifier-g7000': 'Edifier G7000',
    'klipsch-the-fives-v2': 'Klipsch The Fives V2',
    'kef-lsx-ii': 'KEF LSX II',
    'dali-oberon-1c': 'Dali Oberon 1C',
    'triangle-ln01a': 'Triangle LN01A',
    'sonos-ray': 'Sonos Ray',
    'sonos-beam-gen-2': 'Sonos Beam Gen 2',
    'denon-dht-s217': 'Denon DHT-S217',
    'bose-tv-speaker': 'Bose TV Speaker',
    'sonos-era-100': 'Sonos Era 100',
    'bluesound-powernode-edge': 'Bluesound Powernode Edge',
    'arylic-s50-pro': 'Arylic S50 Pro+',
    'eversolo-dmp-a6-gen-2': 'Eversolo DMP-A6 Gen 2',
    'denon-avr-x2800h': 'Denon AVR-X2800H',
    'yamaha-rx-v6a': 'Yamaha RX-V6A',
    'marantz-nr1510': 'Marantz NR1510',
    'fiio-dm13': 'FiiO DM13',
    'fosi-audio-merak-cd-player': 'Fosi Audio Merak CD',
    'denon-dcd-900ne': 'Denon DCD-900NE',
}

PRICE_RE = re.compile(r'(\d{1,4}(?:\.\d{3})*|\d{1,5})(?:[.,](\d{1,2}))?\s*(?:€|euros?)', re.I)


def parse_price(txt):
    """Extrae precios en € de un texto; devuelve lista de floats."""
    out = []
    for m in PRICE_RE.finditer(txt or ''):
        ent = m.group(1).replace('.', '')
        dec = m.group(2) or '0'
        try:
            v = float(ent + '.' + dec.ljust(2, '0')[:2])
        except ValueError:
            continue
        if 10 <= v <= 15000:
            out.append(v)
    return out


def clean_url(u):
    u = re.sub(r'\?srsltid=[^&]+', '', u)
    u = re.sub(r'&srsltid=[^&]+', '', u)
    return u


def search(query, num=7, recency=120):
    args = json.dumps({'query': query, 'num': num, 'recency_days': recency})
    r = subprocess.run(['z-ai', 'function', '-n', 'web_search', '-a', args],
                       capture_output=True, text=True, timeout=60)
    raw = r.stdout
    i = raw.find('[')
    if i < 0:
        return []
    j = raw.rfind(']')
    try:
        return json.loads(raw[i:j + 1])
    except Exception:
        return []


def collect_pcc(results):
    pcc = []
    for r_ in results:
        url = clean_url(r_.get('url', ''))
        host = r_.get('host_name', '')
        if 'pccomponentes.com' not in host and 'pccomponentes.com' not in url:
            continue
        if '/opiniones/' in url or '/blog' in url or '/informacion' in url:
            continue
        snip = (r_.get('snippet') or '') + ' ' + (r_.get('name') or '')
        pcc.append({
            'url': url,
            'name': r_.get('name', '')[:120],
            'snippet': r_.get('snippet', '')[:400],
            'prices': parse_price(r_.get('snippet', '')),
            'agotado': bool(re.search(r'agotad|no disponible|sin stock', snip, re.I)),
            'vendido_pcc': bool(re.search(r'vendido y enviado por pc?componentes', snip, re.I)),
            'envio_gratis': bool(re.search(r'env[ií]o gratis', snip, re.I)),
            'entrega': bool(re.search(r'entrega (ma[ñn]ana|en \d)', snip, re.I)),
        })
    return pcc


def collect_aggregators(results):
    """Resultados de agregadores/shopping que citan pccomponentes con precio."""
    agg = []
    for r_ in results:
        url = clean_url(r_.get('url', ''))
        host = r_.get('host_name', '')
        if host in ('www.pccomponentes.com', 'pccomponentes.com') or 'pccomponentes.com/' in url:
            continue
        snip = (r_.get('snippet') or '') + ' ' + (r_.get('name') or '')
        if 'pccomponentes' not in snip.lower() and 'pccomponentes' not in url.lower():
            continue
        pr = parse_price(r_.get('snippet', ''))
        if not pr:
            continue
        agg.append({'url': url[:160], 'name': r_.get('name', '')[:120],
                    'snippet': r_.get('snippet', '')[:400], 'prices': pr})
    return agg


def run_one(handle, model):
    """Consulta única óptima estilo shopping, con validación de slug y reintento."""
    entry = {'query': model, 'pcc': [], 'agg': [], 'passes': []}
    q = model + ' pccomponentes precio €'
    for attempt in range(3):
        res = search(q, num=8, recency=180)
        if res:
            entry['passes'].append(f'intento{attempt}:{len(res)}')
            break
        entry['passes'].append(f'intento{attempt}:0')
        time.sleep(12)
    else:
        res = []
    # fichas pcc candidatas
    cand = collect_pcc(res)
    # validar slug contra tokens del modelo
    toks = [t for t in re.split(r'[\s\-]+', model.lower()) if len(t) >= 3 and t not in ('the', 'v2')]
    def slug_ok(url, name):
        s = url.lower()
        hit = sum(1 for t in toks if t in s)
        if hit >= min(2, len(toks)):
            return True
        n = name.lower()
        return sum(1 for t in toks if t in n) >= min(2, len(toks))
    entry['pcc'] = [x for x in cand if slug_ok(x['url'], x['name'])] or cand
    # poner primero las que tienen precio
    entry['pcc'].sort(key=lambda x: (0 if x['prices'] else 1, -len(x['prices'])))
    entry['agg'] = collect_aggregators(res)
    return entry


def main():
    out_path = sys.argv[1]
    only = set(sys.argv[2:])
    try:
        out = json.load(open(out_path))
    except Exception:
        out = {}
    for handle, model in QUERIES.items():
        if only and handle not in only:
            continue
        if handle in out and not only:
            continue
        entry = run_one(handle, model)
        out[handle] = entry
        json.dump(out, open(out_path, 'w'), ensure_ascii=False, indent=1)
        fp = [x['prices'] for x in entry['pcc'] if x['prices']]
        ap = entry['agg'][0]['prices'][:2] if entry['agg'] else []
        print(f"{handle[:38]:38} | {model[:28]:28} | pcc:{len(entry['pcc'])} precios:{(fp[0] if fp else [])} agg:{ap} | {'/'.join(entry['passes'])}", flush=True)
        time.sleep(6)
    print('OK, total:', len(out))


if __name__ == '__main__':
    main()
