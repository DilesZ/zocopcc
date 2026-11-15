#!/usr/bin/env python3
"""Lectura EN DIRECTO del catálogo de Zococity (zococity.es) con navegador real.

Por qué un navegador: zococity.es bloquea peticiones HTTP planas con 429 (rate limit
anti-bot). Los endpoints estándar de Shopify (/products.json, /collections/.../products.json)
están desactivados. La vía que funciona: nodriver abre la web como Chrome real y, desde
dentro de la página, lanza XHR SÍNCRONOS a /products/<handle>.js (JSON oficial de Shopify
con título, marca, precio, stock, SKU y EAN por variante).

OJO (lección dura): tab.evaluate() de nodriver NO espera promesas — un fetch().then()
devuelve None. Usa XMLHttpRequest síncrono, que devuelve el texto directamente.
"""
import asyncio, glob, json, os, platform, shutil, subprocess, time

ZOCO_BASE = 'https://zococity.es/'


def find_chrome():
    """Localiza un binario de Chrome/Chromium en Linux, macOS o Windows."""
    env = os.environ.get('CHROME_PATH')
    if env and os.path.exists(env):
        return env
    for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'):
        p = shutil.which(name)
        if p:
            return p
    pats = [
        os.path.expanduser('~/.cache/puppeteer/chrome/*/chrome-linux64/chrome'),
        os.path.expanduser('~/.cache/puppeteer/chrome/*/chrome-linux/chrome'),
        os.path.expanduser('~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome'),
        '/opt/google/chrome/chrome',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        'C:/Program Files/Google/Chrome/Application/chrome.exe',
    ]
    for pat in pats:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    raise SystemExit('Chrome no encontrado. Instala Google Chrome o exporta CHROME_PATH=/ruta/a/chrome')


_XVFB_PROC = None


def chrome_sandbox():
    """¿Chrome puede arrancar con su sandbox?

    En CI (GitHub Actions) el sandbox de Chrome no arranca y nodriver falla con
    'Failed to connect to browser'. Se desactiva solo con ZOCO_NO_SANDBOX=1,
    que es lo que hace el workflow; en el uso local del PC el sandbox sigue
    activo (no conviene debilitarlo a mano).
    """
    return os.environ.get('ZOCO_NO_SANDBOX') != '1'


def chrome_extra_args():
    """Argumentos de Chrome que solo aplican en CI."""
    if os.environ.get('ZOCO_NO_SANDBOX') == '1':
        # nodriver captura stdout/stderr de Chrome en tuberias que nadie lee:
        # con el logging interno apagado la tuberia queda practically vacia.
        return ['--disable-logging']
    return []


def chrome_args():
    """browser_args comun a todas las sesiones de Chrome."""
    return ['--lang=es-ES', '--window-size=1300,850'] + chrome_extra_args()


def _kill_stray_chrome():
    """Mata los Chrome que hayan quedado vivos de un arranque fallido."""
    if platform.system() != 'Linux':
        return
    try:
        subprocess.run(['pkill', '-f', 'remote-debugging-port'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except Exception:
        pass


async def start_browser(attempts=4, backoff=5):
    """Arranca Chrome y devuelve la sesion de nodriver, con reintentos.

    nodriver solo espera ~2,75 s a que Chrome abra su puerto de depuracion
    (0,25 s + 5 intentos de 0,5 s). En un runner frio (primer arranque: binario
    en cache, perfil nuevo) se queda corto y aborta con
    'Failed to connect to browser'. El primer intento deja el sistema caliente,
    asi que reintentando arranca a tiempo.
    """
    import nodriver as uc
    last = None
    for i in range(1, attempts + 1):
        try:
            return await uc.start(browser_executable_path=find_chrome(), headless=False,
                                  browser_args=chrome_args(), sandbox=chrome_sandbox(),
                                  **ensure_display())
        except Exception as e:
            last = e
            print(f'[chrome] no se pudo arrancar (intento {i}/{attempts}): {e}', flush=True)
            if i < attempts:
                _kill_stray_chrome()
                time.sleep(backoff * i)
    raise last


def ensure_display():
    """En Linux sin pantalla gráfica, arranca Xvfb :99. Devuelve kwargs para nodriver."""
    global _XVFB_PROC
    if platform.system() != 'Linux' or os.environ.get('DISPLAY'):
        return {}
    try:
        _XVFB_PROC = subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1400x900x24'],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.environ['DISPLAY'] = ':99'
        time.sleep(1.5)
        return {'xvfb_display': ':99'}
    except FileNotFoundError:
        raise SystemExit('Sin DISPLAY y sin Xvfb. Instala xvfb (apt install xvfb) o exporta DISPLAY')


XHR_JS = """
(() => {
  const x = new XMLHttpRequest();
  x.open('GET', '/products/__HANDLE__.js', false);
  x.send();
  if (x.status !== 200) return JSON.stringify({st: x.status});
  let d;
  try { d = JSON.parse(x.responseText); } catch (e) { return JSON.stringify({st: -2, err: String(e)}); }
  const v = d.variants[0];
  return JSON.stringify({st: 200, title: d.title, vendor: d.vendor,
      price: v.price, available: v.available, sku: v.sku, barcode: v.barcode,
      compare_at: v.compare_at_price, nvar: d.variants.length});
})()
"""


async def _fetch(handles, out, on_progress, cancel):
    import nodriver as uc
    browser = await start_browser()
    tab = await browser.get(ZOCO_BASE)
    for _ in range(20):                       # espera a que la home cargue (hasta 40 s)
        await tab.sleep(2)
        try:
            t = await tab.evaluate('document.title')
        except Exception:
            continue
        if t:
            break
    total = len(handles)
    for n, h in enumerate(handles, 1):
        if cancel.get('stop'):
            break
        js = XHR_JS.replace('__HANDLE__', h)
        try:
            raw = await tab.evaluate(js)
            d = json.loads(raw)
            if isinstance(d, str):
                d = json.loads(d)
            if d.get('st') == 200:
                out[h] = {'title': d.get('title'), 'vendor': d.get('vendor'),
                          'price_cents': int(d.get('price') or 0) or None,
                          'available': bool(d.get('available')),
                          'sku': d.get('sku'), 'ean': (str(d.get('barcode')) if d.get('barcode') else None),
                          'compare_at_cents': int(d.get('compare_at') or 0) or None}
            else:
                out[h] = {'error': f'HTTP {d.get("st")}'}
        except Exception as e:
            out[h] = {'error': str(e)[:100]}
        if on_progress:
            on_progress('zoco', n, total, h)
        await tab.sleep(0.9)
    try:
        await browser.stop()
    except Exception:
        pass


def fetch_products(handles, on_progress=None, cancel=None):
    """Devuelve {handle: {...}} leyendo la web en directo. Bloquea hasta terminar."""
    cancel = cancel or {}
    out = {}
    asyncio.run(_fetch(list(handles), out, on_progress, cancel))
    return out


if __name__ == '__main__':
    import sys
    hs = sys.argv[1:] or ['fiio-ft3', 'audio-technica-ath-m50x']
    res = fetch_products(hs, on_progress=lambda ph, n, t, cur: print(f'[{n}/{t}] {cur}'))
    print(json.dumps(res, ensure_ascii=False, indent=1))
