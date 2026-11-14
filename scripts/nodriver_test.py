#!/usr/bin/env python3
"""Prueba nodriver contra Cloudflare de PCComponentes: abre ficha, espera reto, extrae JSON-LD."""
import asyncio, json, sys

URL = sys.argv[1] if len(sys.argv) > 1 else 'https://www.pccomponentes.com/audio-technica-ath-m50x-auriculares-de-estudio-cerrados'
OUT = sys.argv[2] if len(sys.argv) > 2 else '/home/z/my-project/data/nodriver_test.json'


async def main():
    import nodriver as uc
    browser = await uc.start(
        browser_executable_path='/home/z/.cache/puppeteer/chrome/linux-157.0.8103.50/chrome-linux64/chrome',
        headless=False,
        xvfb_display=':99',
        browser_args=['--lang=es-ES', '--window-size=1400,900'],
    )
    tab = await browser.get(URL)
    # esperar a que pase el reto CF (título deja de ser "Just a moment...")
    title = ''
    for i in range(30):
        await tab.sleep(2)
        try:
            title = await tab.evaluate('document.title')
        except Exception:
            title = '?'
        if title and 'moment' not in title.lower():
            break
    print('TITULO:', title, '| intentos:', i + 1)
    if 'moment' in (title or '').lower():
        json.dump({'ok': False, 'title': title}, open(OUT, 'w'))
        await browser.stop()
        return
    await tab.sleep(3)
    data = await tab.evaluate("""
    (() => {
      const res = {title: document.title, url: location.href};
      const lds = [...document.querySelectorAll('script[type="application/ld+json"]')];
      for (const s of lds) {
        try {
          const o = JSON.parse(s.textContent);
          if (o['@type'] === 'Product') {
            res.ld = {name: o.name, sku: o.sku, brand: (o.brand||{}).name, gtin: o.gtin13||o.gtin12||o.ean,
                      offers: o.offers};
          }
        } catch(e) {}
      }
      res.hasPriceTag = !!document.querySelector('[itemprop=price], .price, [data-price]');
      const m = document.body.innerText.match(/(\\d{1,4}[.,]\\d{2})\\s*€/);
      res.firstPriceInText = m ? m[1] : null;
      return JSON.stringify(res);
    })()
    """)
    try:
        data = json.loads(json.loads(data))
    except Exception:
        pass
    print(json.dumps(data, ensure_ascii=False, indent=1)[:1200])
    json.dump({'ok': True, **data}, open(OUT, 'w'), ensure_ascii=False)
    await browser.stop()


if __name__ == '__main__':
    asyncio.run(main())
