#!/usr/bin/env python3
"""Resolución conservadora de productos en sitemaps y lectura de ofertas JSON-LD.

Solo se visitan páginas de producto publicadas en los sitemaps oficiales. No se
usan páginas de búsqueda, endpoints privados ni retos anti-bot. Una oferta se
asigna al catálogo únicamente si la ficha declara el mismo EAN/GTIN.
"""
import asyncio
import gzip
import json
import re
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import unquote, urlparse
from zoneinfo import ZoneInfo

from zoco_fetcher import start_browser

SITEMAP_MAX_FILES = 60
SITEMAP_MAX_BYTES = 30 * 1024 * 1024
PRODUCTS_PER_ITEM = 2
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


def _tag(tag):
    return tag.rsplit('}', 1)[-1].lower()


def _read_url(url):
    req = urllib.request.Request(
        url, headers={'User-Agent': 'zocopcc-price-monitor/1.0 (+public sitemap reader)'}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read(SITEMAP_MAX_BYTES + 1)
        if len(data) > SITEMAP_MAX_BYTES:
            raise ValueError('sitemap supera el límite de tamaño')
        if url.lower().endswith('.gz') or resp.headers.get('Content-Encoding') == 'gzip':
            data = gzip.decompress(data)
        return data


def sitemap_product_urls(sitemap_roots, allowed_host):
    """Lee sitemaps declarados por robots.txt; devuelve URLs de páginas de producto."""
    pending = list(sitemap_roots)
    visited = set()
    product_urls = []
    complete = True
    while pending and len(visited) < SITEMAP_MAX_FILES:
        sitemap = pending.pop(0)
        if sitemap in visited:
            continue
        visited.add(sitemap)
        try:
            root = ET.fromstring(_read_url(sitemap))
        except Exception:
            complete = False
            continue
        locs = [el.text.strip() for el in root.iter() if _tag(el.tag) == 'loc' and el.text]
        if _tag(root.tag) == 'sitemapindex':
            pending.extend(u for u in locs if u.startswith('https://') and (urlparse(u).hostname or '').lower().endswith(allowed_host))
        else:
            for url in locs:
                parsed = urlparse(url)
                if parsed.scheme == 'https' and parsed.hostname and parsed.hostname.lower().endswith(allowed_host):
                    product_urls.append(url)
    if pending:
        complete = False
    return list(dict.fromkeys(product_urls)), complete


def _tokens(value):
    normalized = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().lower()
    return [t for t in re.findall(r'[a-z0-9]+', normalized) if len(t) >= 3 and t not in STOP]


def candidate_urls(urls, product, limit=PRODUCTS_PER_ITEM):
    query = product.get('query') or product.get('title_zoco') or ''
    brand = product.get('brand') or ''
    brand_tokens = _tokens(brand)
    query_tokens = _tokens(query)
    model_tokens = [t for t in query_tokens if t not in brand_tokens]
    if not model_tokens:
        model_tokens = query_tokens
    if not model_tokens:
        return []
    ranked = []
    for url in urls:
        slug = unquote(urlparse(url).path).lower()
        if all(token in slug for token in model_tokens):
            brand_hits = sum(1 for token in brand_tokens if token in slug)
            ranked.append((brand_hits, len(model_tokens), url))
    ranked.sort(key=lambda row: (-row[0], -row[1], row[2]))
    return [url for _, _, url in ranked[:limit]]


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


def fetch_store_offers(products, previous, sitemap_roots, allowed_host, retailer,
                       on_progress=None, cancel=None):
    """Fetch exact-EAN offers; prior successful URLs bypass sitemap discovery."""
    cancel = cancel or {}
    by_handle = {p['handle']: dict(p) for p in products}
    prev = previous or {}
    saved_urls = {}
    missing = []
    for handle, product in by_handle.items():
        old = prev.get(handle) or {}
        url = old.get(f'url_{retailer}')
        if url and (urlparse(url).hostname or '').lower().endswith(allowed_host):
            saved_urls[handle] = [url]
        else:
            missing.append(handle)
    sitemap_urls = []
    sitemap_complete = True
    if missing and not cancel.get('stop'):
        try:
            sitemap_urls, sitemap_complete = sitemap_product_urls(sitemap_roots, allowed_host)
        except Exception:
            sitemap_complete = False
    for handle in missing:
        product = by_handle[handle]
        candidates = candidate_urls(sitemap_urls, product)
        saved_urls[handle] = candidates
        ean = product.get('ean')
        if not ean:
            saved_urls[handle] = []
    targets = {h: urls for h, urls in saved_urls.items() if urls}
    found = asyncio.run(_fetch_pages(targets, by_handle, retailer, on_progress, cancel))
    for handle in by_handle:
        if handle not in found:
            found[handle] = {
                'status': 'unresolved' if sitemap_complete else 'error',
                'live': False,
                'error': None if sitemap_complete else 'No se pudo leer el sitemap oficial completo.',
            }
    return found
