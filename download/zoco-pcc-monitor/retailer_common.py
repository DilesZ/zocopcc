#!/usr/bin/env python3
"""Resolución conservadora de productos en sitemaps y lectura de ofertas JSON-LD.

Solo se visitan páginas de producto publicadas en los sitemaps oficiales. No se
usan páginas de búsqueda, endpoints privados ni retos anti-bot. Una oferta se
asigna al catálogo únicamente si la ficha declara el mismo EAN/GTIN.
"""
import asyncio
import json
import re
import unicodedata
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from zoco_fetcher import start_browser

PAGE_GAP_SECONDS = 2.0
PAGE_TIMEOUT_SECONDS = 25

PRODUCTS_JS = r"""
(() => {
  const out = [];
  const visit = (x) => {
    if (Array.isArray(x)) { x.forEach(visit); return; }
    if (!x || typeof x !== 'object') return;
    const t = Array.isArray(x['@type']) ? x['@type'] : [x['@type']];
    if (t.includes('Product')) {
      out.push({
        name: x.name || '',
        sku: x.sku || '',
        gtin: x.gtin13 || x.gtin12 || x.gtin14 || x.gtin8 || x.gtin || x.ean || '',
        offers: x.offers || null
      });
    }
    Object.values(x).forEach(v => {
      if (v && typeof v === 'object') visit(v);
    });
  };
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    try { visit(JSON.parse(s.textContent)); } catch (_) {}
  }
  return JSON.stringify({title: document.title, products: out});
})()
"""

STOP = {
    'audio', 'auriculares', 'inalambricos', 'inalambricas', 'bluetooth',
    'wireless', 'con', 'para', 'the', 'new', 'negro', 'negra', 'blanco',
    'blanca', 'silver', 'black', 'white', 'pro', 'mk', 'ii', 'iii', 'de',
}


def _gtin(product):
    value = str(product.get('gtin') or '').strip()
    return re.sub(r'\D', '', value)


def _seller(offer):
    value = offer.get('seller') or offer.get('offeredBy') or ''
    if isinstance(value, dict):
        return str(value.get('name') or '')
    return str(value)


def _availability(offer):
    value = str(offer.get('availability') or '').lower()
    if 'instock' in value or 'limitedavailability' in value:
        return True
    if 'outofstock' in value or 'soldout' in value:
        return False
    return None


def _offers(product):
    raw = product.get('offers')
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        nested = raw.get('offers')
        items = nested if isinstance(nested, list) else [raw]
    else:
        items = []
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        currency = str(item.get('priceCurrency') or 'EUR').upper()
        price = item.get('price') or item.get('lowPrice')
        try:
            price = float(str(price).replace(',', '.'))
        except (TypeError, ValueError):
            price = None
        if currency != 'EUR':
            price = None
        out.append({
            'price': price,
            'currency': currency,
            'seller': _seller(item),
            'availability': _availability(item),
        })
    return out


def _choose_offer(product, retailer):
    offers = [x for x in _offers(product) if x['price'] is not None and x['price'] > 0]
    if not offers:
        return None
    own = [x for x in offers if retailer in x['seller'].lower()]
    own_in = [x for x in own if x['availability'] is True]
    in_stock = [x for x in offers if x['availability'] is True]
    if own_in:
        return min(own_in, key=lambda x: x['price'])
    if own:
        return min(own, key=lambda x: x['price'])
    if in_stock:
        return min(in_stock, key=lambda x: x['price'])
    return min(offers, key=lambda x: x['price'])


def _exact_product(data, expected_ean, retailer):
    expected = re.sub(r'\D', '', str(expected_ean or ''))
    if not expected:
        return None
    for product in data.get('products') or []:
        if _gtin(product) != expected:
            continue
        offer = _choose_offer(product, retailer)
        return {
            'matched': True,
            'title': product.get('name') or '',
            'sku': product.get('sku') or '',
            'ean': expected,
            'price': offer.get('price') if offer else None,
            'seller': offer.get('seller') if offer else '',
            'availability': offer.get('availability') if offer else None,
        }
    return None


async def _read_page(tab):
    raw = await tab.evaluate(PRODUCTS_JS)
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


async def _fetch_pages(url_map, products, retailer, on_progress, cancel):
    results = {}
    items = [(handle, urls) for handle, urls in url_map.items()]
    if not items:
        return results
    browser = None
    tab = None
    count = sum(len(urls) for _, urls in items)
    completed = 0
    stop_retailer = False
    try:
        for handle, urls in items:
            product = products[handle]
            expected_ean = product.get('ean')
            result = None
            for url in urls:
                if cancel.get('stop'):
                    break
                try:
                    if browser is None:
                        browser = await start_browser()
                        tab = await asyncio.wait_for(browser.get(url), timeout=PAGE_TIMEOUT_SECONDS)
                    else:
                        await asyncio.wait_for(tab.get(url), timeout=PAGE_TIMEOUT_SECONDS)
                    await tab.sleep(2)
                    data = await _read_page(tab)
                    title = str(data.get('title') or '')
                    low = title.lower()
                    if any(word in low for word in ('captcha', 'access denied', 'just a moment', 'verify you are human')):
                        result = {'status': 'blocked', 'url': url, 'error': 'La página requiere verificación; se detuvo la lectura.'}
                        stop_retailer = True
                        break
                    exact = _exact_product(data, expected_ean, retailer)
                    if exact:
                        result = {
                            **exact, 'status': 'matched', 'url': url,
                            'source': 'JSON-LD de ficha oficial',
                            'observed_at': datetime.now(ZoneInfo('Europe/Madrid')).isoformat(timespec='seconds'),
                            'live': True,
                        }
                        completed += 1
                        if on_progress:
                            on_progress(retailer, completed, count, handle)
                        break
                except Exception as exc:
                    result = {'status': 'error', 'url': url, 'error': str(exc)[:160]}
                completed += 1
                if on_progress:
                    on_progress(retailer, completed, count, handle)
                if len(urls) > 1:
                    await asyncio.sleep(PAGE_GAP_SECONDS)
            if result is None:
                result = {'status': 'unresolved', 'live': False}
            results[handle] = result
            if cancel.get('stop') or stop_retailer:
                break
        for handle, _ in items:
            results.setdefault(handle, {'status': 'cancelled', 'live': False})
    finally:
        if browser is not None:
            try:
                await browser.stop()
            except Exception:
                pass
    return results


def _allowed_product_url(url, allowed_host):
    parsed = urlparse(str(url or ''))
    host = (parsed.hostname or '').lower()
    return (
        parsed.scheme == 'https'
        and (host == allowed_host or host.endswith('.' + allowed_host))
        and parsed.path
    )


def fetch_store_offers(products, previous, allowed_host, retailer,
                       on_progress=None, cancel=None):
    """Lee URLs de producto sembradas en el catálogo o validadas previamente.

    La asociación nunca se basa solo en el texto del URL: la ficha debe exponer
    el EAN/GTIN exacto en JSON-LD. Si el catálogo no trae URL, queda sin resolver
    y no se consultan rutas de búsqueda ni sitemaps con acceso denegado.
    """
    cancel = cancel or {}
    by_handle = {p['handle']: dict(p) for p in products}
    prev = previous or {}
    targets = {}
    for handle, product in by_handle.items():
        old = prev.get(handle) or {}
        candidates = (old.get(f'url_{retailer}'), product.get(f'url_{retailer}'))
        urls = []
        for url in candidates:
            if _allowed_product_url(url, allowed_host) and url not in urls:
                urls.append(url)
        if urls:
            targets[handle] = urls

    found = asyncio.run(_fetch_pages(targets, by_handle, retailer, on_progress, cancel))
    for handle in by_handle:
        if handle not in found:
            found[handle] = {
                'status': 'cancelled' if cancel.get('stop') else 'unresolved',
                'live': False,
                'error': None if cancel.get('stop') else
                    'Sin URL de producto confirmada en el catálogo para esta tienda.',
            }
    return found
