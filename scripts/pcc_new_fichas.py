#!/usr/bin/env python3
"""Lee en directo las fichas nuevas de HD550 y TWX7 (descubiertas vía buscador) y reintenta Momentum desde el buscador."""
import asyncio, json

MOM_Q = 'https://www.pccomponentes.com/buscar/?query=Sennheiser+Momentum+True+Wireless+4'
NEW = {
    'sennheiser-hd-550': 'https://www.pccomponentes.com/auriculares-sennheiser-con-cable-circumaurales-abiertos-alta-fidelidad-150-ohm',
    'audio-technica-ath-twx7': 'https://www.pccomponentes.com/audio-technica-ath-twx7-auriculares-inalambricos-con-estuche-de-carga-blancos',
}
LDP_JS = """
(() => {
  const res = {lds: [], title: document.title};
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      const o = JSON.parse(s.textContent);
      const st = [o];
      while (st.length) {
        const x = st.pop();
        if (Array.isArray(x)) { st.push(...x); continue; }
        if (x && typeof x === 'object') {
          if (x['@type'] === 'Product') res.lds.push({name: x.name, sku: x.sku, gtin: x.gtin13 || x.ean || null, offers: x.offers});
          for (const v of Object.values(x)) if (v && typeof v === 'object') st.push(v);
        }
      }
    } catch(e) {}
  }
  return JSON.stringify(res);
})()
"""


async def wait_clear(tab, max_s=60):
    for _ in range(max_s // 2):
        await tab.sleep(2)
        try:
            t = await tab.evaluate('document.title')
        except Exception:
            continue
        if t and 'moment' not in t.lower():
            return True, t
    return False, ''


async def main():
    import nodriver as uc
    browser = await uc.start(
        browser_executable_path='/home/z/.cache/puppeteer/chrome/linux-157.0.8103.50/chrome-linux64/chrome',
        headless=False, xvfb_display=':99',
        browser_args=['--lang=es-ES', '--window-size=1400,900'],
    )
    results = json.load(open('/home/z/my-project/data/pcc_live.json'))
    tab = await browser.get(NEW['sennheiser-hd-550'])
    ok, t = await wait_clear(tab)
    print('HD550:', t[:60] if ok else 'RETO', flush=True)
    if ok:
        await tab.sleep(2)
        raw = await tab.evaluate(LDP_JS)
        data = json.loads(raw)
        if isinstance(data, str):
            data = json.loads(data)
        results['sennheiser-hd-550'] = {'url': NEW['sennheiser-hd-550'], **data}
        json.dump(results, open('/home/z/my-project/data/pcc_live.json', 'w'), ensure_ascii=False, indent=1)

    await tab.get(NEW['audio-technica-ath-twx7'])
    ok, t = await wait_clear(tab)
    print('TWX7:', t[:60] if ok else 'RETO', flush=True)
    if ok:
        await tab.sleep(2)
        raw = await tab.evaluate(LDP_JS)
        data = json.loads(raw)
        if isinstance(data, str):
            data = json.loads(data)
        results['audio-technica-ath-twx7'] = {'url': NEW['audio-technica-ath-twx7'], **data}
        json.dump(results, open('/home/z/my-project/data/pcc_live.json', 'w'), ensure_ascii=False, indent=1)

    # Momentum: desde el buscador → abrir ficha desde el resultado
    await tab.get(MOM_Q)
    ok, t = await wait_clear(tab)
    print('BUSCADOR momentum:', t[:50] if ok else 'RETO', flush=True)
    if ok:
        for _ in range(6):
            await tab.sleep(3)
            raw = await tab.evaluate("""
            (() => {
              const base='https://www.pccomponentes.com/';
              const out=[];
              document.querySelectorAll('a[href]').forEach(a=>{
                const h=a.href||'';
                if(h.startsWith(base) && h.includes('momentum-true-wireless-4') && !h.includes('buscar')) out.push(h);
              });
              return JSON.stringify([...new Set(out)].slice(0,3));
            })()
            """)
            try:
                links = json.loads(raw)
                if isinstance(links, str):
                    links = json.loads(links)
            except Exception:
                links = []
            if links:
                break
        print('MOMENTUM enlaces:', links, flush=True)
        if links:
            await tab.get(links[0])
            ok, t = await wait_clear(tab)
            print('MOMENTUM ficha:', t[:60] if ok else 'RETO', flush=True)
            if ok:
                await tab.sleep(2)
                raw = await tab.evaluate(LDP_JS)
                data = json.loads(raw)
                if isinstance(data, str):
                    data = json.loads(data)
                results['sennheiser-momentum-true-wireless-4'] = {'url': links[0], **data}
                json.dump(results, open('/home/z/my-project/data/pcc_live.json', 'w'), ensure_ascii=False, indent=1)
                print('MOMENTUM GUARDADO con', len(data.get('lds') or []), 'LDPs', flush=True)
    try:
        await browser.stop()
    except Exception:
        pass


asyncio.run(main())
