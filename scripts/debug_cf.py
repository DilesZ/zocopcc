#!/usr/bin/env python3
"""Diagnóstico: 1 ficha PCC con nodriver, título cada 2s y texto final."""
import asyncio, sys

URL = 'https://www.pccomponentes.com/audio-technica-ath-m50x-auriculares-de-estudio-cerrados'


async def main():
    import nodriver as uc
    browser = await uc.start(
        browser_executable_path='/home/z/.cache/puppeteer/chrome/linux-157.0.8103.50/chrome-linux64/chrome',
        headless=False, xvfb_display=':99',
        browser_args=['--lang=es-ES', '--window-size=1400,900'],
    )
    tab = await browser.get(URL)
    for i in range(30):
        await tab.sleep(2)
        try:
            t = await tab.evaluate('document.title')
            body = await tab.evaluate('document.body.innerText.slice(0,300)')
        except Exception as e:
            print(i, 'EVAL ERR', str(e)[:80], flush=True)
            continue
        print(i, repr(t)[:80], '|', repr(body)[:150], flush=True)
        if t and 'moment' not in t.lower():
            print('PASADO en', i * 2, 's', flush=True)
            break
    try:
        await browser.stop()
    except Exception:
        pass


asyncio.run(main())
