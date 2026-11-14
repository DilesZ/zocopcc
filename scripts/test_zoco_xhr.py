#!/usr/bin/env python3
"""Test técnico: leer /products/<handle>.js de Zococity con nodriver usando XHR síncrono."""
import asyncio, json


async def main():
    import nodriver as uc
    browser = await uc.start(
        browser_executable_path='/home/z/.cache/puppeteer/chrome/linux-157.0.8103.50/chrome-linux64/chrome',
        headless=False, xvfb_display=':99',
        browser_args=['--lang=es-ES'],
    )
    tab = await browser.get('https://zococity.es/')
    ok = ''
    for i in range(20):
        await tab.sleep(2)
        try:
            ok = await tab.evaluate('document.title')
        except Exception:
            continue
        if ok:
            break
    print('ZOCO título:', ok)
    js = """
    (() => {
      const x = new XMLHttpRequest();
      x.open('GET', '/products/fiio-ft3.js', false);
      x.send();
      if (x.status !== 200) return JSON.stringify({st: x.status});
      const d = JSON.parse(x.responseText);
      const v = d.variants[0];
      return JSON.stringify({st: 200, title: d.title, vendor: d.vendor, price: v.price,
                             available: v.available, sku: v.sku, barcode: v.barcode,
                             nvar: d.variants.length});
    })()
    """
    for h in ['fiio-ft3', 'audio-technica-ath-m50x']:
        js2 = js.replace('/products/fiio-ft3.js', f'/products/{h}.js')
        try:
            raw = await tab.evaluate(js2)
            data = json.loads(raw)
            if isinstance(data, str):
                data = json.loads(data)
            print(h, '->', json.dumps(data, ensure_ascii=False)[:200])
        except Exception as e:
            print(h, 'ERR', str(e)[:120])
        await tab.sleep(1.5)
    try:
        await browser.stop()
    except Exception:
        pass


asyncio.run(main())
