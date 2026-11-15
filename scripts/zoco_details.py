#!/usr/bin/env python3
"""Extrae EAN, precio y disponibilidad de fichas de producto de Zococity vía el navegador agent-browser."""
import json, re, subprocess, sys, time

CANDIDATES = [
    # (handle, categoría legible)
    ('fiio-ft5', 'Auriculares HiFi'),
    ('fiio-ft3', 'Auriculares HiFi'),
    ('sennheiser-hd800s', 'Auriculares HiFi'),
    ('sennheiser-hd-550', 'Auriculares HiFi'),
    ('sennheiser-hd-560s', 'Auriculares HiFi'),
    ('hifiman-sundara', 'Auriculares HiFi'),
    ('meze-audio-109-pro', 'Auriculares HiFi'),
    ('grado-sr80x', 'Auriculares HiFi'),
    ('audio-technica-ath-m50x', 'Auriculares HiFi'),
    ('sennheiser-momentum-true-wireless-4', 'Auriculares Bluetooth'),
    ('sennheiser-accentum-wireless', 'Auriculares Bluetooth'),
    ('denon-ah-c630w', 'Auriculares Bluetooth'),
    ('audio-technica-ath-twx7', 'Auriculares Bluetooth'),
    ('topping-l50', 'DAC / Amplificador'),
    ('topping-dx1', 'DAC / Amplificador'),
    ('smsl-a2', 'DAC / Amplificador'),
    ('ifi-audio-zen-air-dac-2', 'DAC / Amplificador'),
    ('marantz-pm6007', 'Amplificador integrado'),
    ('denon-pma-600ne', 'Amplificador integrado'),
    ('yamaha-as301', 'Amplificador integrado'),
    ('yamaha-as201', 'Amplificador integrado'),
    ('nad-d3020-v2', 'Amplificador integrado'),
    ('cambridge-audio-axa25', 'Amplificador integrado'),
    ('audio-technica-at-lp120x', 'Tocadiscos'),
    ('audio-technica-at-lp60xbt', 'Tocadiscos'),
    ('audio-technica-at-lp3xbt', 'Tocadiscos'),
    ('audio-technica-at-lpw30tk', 'Tocadiscos'),
    ('denon-dp-400', 'Tocadiscos'),
    ('rekkord-audio-f110', 'Tocadiscos'),
    ('dual-cs418', 'Tocadiscos'),
    ('edifier-s1000mkii', 'Altavoces activos'),
    ('edifier-r1080bt', 'Altavoces activos'),
    ('edifier-r1855db', 'Altavoces activos'),
    ('edifier-r2000db', 'Altavoces activos'),
    ('edifier-qd35', 'Altavoces activos'),
    ('edifier-g7000', 'Altavoces activos'),
    ('klipsch-the-fives-v2', 'Altavoces activos'),
    ('kef-lsx-ii', 'Altavoces activos'),
    ('dali-oberon-1c', 'Altavoces activos'),
    ('triangle-ln01a', 'Altavoces activos'),
    ('sonos-ray', 'Barra de sonido'),
    ('sonos-beam-gen-2', 'Barra de sonido'),
    ('denon-dht-s217', 'Barra de sonido'),
    ('bose-tv-speaker', 'Barra de sonido'),
    ('sonos-era-100', 'Altavoz Bluetooth'),
    ('bluesound-powernode-edge', 'Streamers / En red'),
    ('arylic-s50-pro', 'Streamers / En red'),
    ('eversolo-dmp-a6-gen-2', 'Streamers / En red'),
    ('denon-avr-x2800h', 'Receptor AV'),
    ('yamaha-rx-v6a', 'Receptor AV'),
    ('marantz-nr1510', 'Receptor AV'),
    ('fiio-dm13', 'Reproductor CD'),
    ('fosi-audio-merak-cd-player', 'Reproductor CD'),
    ('denon-dcd-900ne', 'Reproductor CD'),
]

JS = """
fetch('/products/HANDLE').then(r=>r.text()).then(t=>{
  const res={};
  let m=t.match(/"barcode"\\s*:\\s*"(\\d{8,14})"/); res.ean=m?m[1]:null;
  m=t.match(/"price"\\s*:\\s*(\\d+)/); res.priceCents=m?parseInt(m[1]):null;
  m=t.match(/"compare_at_price"\\s*:\\s*(\\d+)/); res.compareCents=m?parseInt(m[1]):null;
  m=t.match(/"sku"\\s*:\\s*"([^"]+)"/); res.sku=m?m[1]:null;
  m=t.match(/"title"\\s*:\\s*"([^"]{5,120})"/); res.title=m?m[1]:null;
  m=t.match(/"available"\\s*:\\s*(true|false)/); res.available=m?m[1]:null;
  return JSON.stringify(res);
}).catch(e=>JSON.stringify({err:String(e)}))
"""

def main():
    out = {}
    if len(sys.argv) > 1:
        try: out = json.load(open(sys.argv[1]))
        except Exception: out = {}
    for handle, cat in CANDIDATES:
        if handle in out:
            continue
        js = JS.replace('HANDLE', handle)
        r = subprocess.run(['agent-browser', 'eval', js], capture_output=True, text=True, timeout=60)
        txt = r.stdout.strip()
        try:
            data = json.loads(json.loads(txt))
        except Exception:
            data = {'err': 'parse: ' + txt[:80]}
        data['cat'] = cat
        data['handle'] = handle
        out[handle] = data
        print(f"{handle:40} | EAN:{data.get('ean')} | sku:{data.get('sku')} | {data.get('priceCents')} | comp:{data.get('compareCents')} | {data.get('available')}", flush=True)
        json.dump(out, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
        time.sleep(0.4)
    print('OK, total:', len(out))

if __name__ == '__main__':
    main()
