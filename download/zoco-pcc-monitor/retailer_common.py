#!/usr/bin/env python3
"""Lectura conservadora de páginas de producto directas y ofertas JSON-LD.

Las URLs se guardan en el catálogo y solo generan candidatos; la asociación
requiere que la ficha oficial publique el mismo EAN/GTIN. No se usan rutas de
búsqueda ni se sortean controles de acceso.
"""
import asyncio
import json
import re
import unicodedata
from datetime import datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from zoco_fetcher import start_browser

PAGE_GAP_SECONDS = 4.0
PAGE_TIMEOUT_SECONDS = 25
# Tras una denegacion no se insiste en cada actualizacion (cada 45 min).
# Se reintenta una sola vez pasadas 6 horas, o antes si cambia la URL.
BLOCK_COOLDOWN_HOURS = 6

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
  return JSON.stringify({title: document.title, url: location.href, text: (document.body && document.body.innerText || '').slice(0, 30000), products: out,
    challenge: !!document.querySelector('iframe[src*="captcha-delivery"], iframe[src*="datadome"], #datadome-captcha')});
})()
"""

STOP = {
    'audio', 'auriculares', 'inalambricos', 'inalambricas', 'bluetooth',
    'wireless', 'con', 'para', 'the', 'new', 'negro', 'negra', 'blanco',
    'blanca', 'silver', 'black', 'white', 'pro', 'mk', 'ii', 'iii', 'de',
}


GTIN_LENGTHS = (8, 12, 13, 14)


def _valid_gtin(value):
    """Valida el dígito de control de un GTIN/EAN (8, 12, 13 o 14 dígitos)."""
    if len(value) not in GTIN_LENGTHS or not value.isdigit():
        return False
    digits = [int(char) for char in value]
    check = digits.pop()
    total = sum(digit * (3 if index % 2 == 0 else 1)
                for index, digit in enumerate(reversed(digits)))
    return (10 - total % 10) % 10 == check


def _gtin(product):
    """EAN/GTIN del producto JSON-LD.

    Carrefour publica el EAN como `sku` (y no como `gtin13`). Solo se acepta un
    `sku` que tenga longitud de GTIN y digito de control valido para no
    confundirlo con un identificador interno de la tienda.
    """
    for key in ('gtin', 'ean'):
        value = re.sub(r'\D', '', str(product.get(key) or ''))
        if len(value) in GTIN_LENGTHS:
            return value
    for key in ('sku', 'productID'):
        value = re.sub(r'\D', '', str(product.get(key) or ''))
        if _valid_gtin(value):
            return value
    return ''


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


def _normalized_text(value):
    value = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', value).strip()


def _gtin_match(candidate, expected):
    c = re.sub(r'\D', '', str(candidate or ''))
    e = re.sub(r'\D', '', str(expected or ''))
    if not c or not e:
        return False
    if c == e:
        return True
    if len(c) in (12, 13, 14) and len(e) in (12, 13, 14):
        return c.zfill(14) == e.zfill(14)
    return False


def _exact_product(data, expected_ean, retailer, product_hint=''):
    expected = re.sub(r'\D', '', str(expected_ean or ''))
    if not expected:
        return None
    products = data.get('products') or []
    match = next((p for p in products if _gtin_match(_gtin(p), expected)), None)

    # Algunas fichas publican el EAN visible en la página, pero no en su JSON-LD.
    # Solo se usa esa evidencia si la etiqueta EAN/GTIN declara exactamente el
    # valor esperado y el Product JSON-LD concuerda con el título y el modelo.
    if match is None:
        visible_eans = re.findall(
            r'\b(?:EAN|GTIN(?:\s*\d+)?)\s*[:\r\n]*\s*([0-9][0-9 .-]{7,16})',
            str(data.get('text') or ''),
            re.IGNORECASE,
        )
        visible_eans = [re.sub(r'\D', '', value) for value in visible_eans]
        title = _normalized_text(data.get('title'))
        hint_tokens = [t for t in _normalized_text(product_hint).split() if len(t) >= 3 and t not in STOP]
        if any(_gtin_match(expected, v) for v in visible_eans) and hint_tokens and all(t in title for t in hint_tokens):
            named = [p for p in products if p.get('name')]
            title_matches = [p for p in named if _normalized_text(p.get('name')) in title]
            if len(title_matches) == 1:
                match = title_matches[0]
            elif len(products) == 1 and named:
                match = named[0]

    if match is None:
        return None
    offer = _choose_offer(match, retailer)
    return {
        'matched': True,
        'title': match.get('name') or '',
        'sku': match.get('sku') or '',
        'ean': expected,
        'price': offer.get('price') if offer else None,
        'seller': offer.get('seller') if offer else '',
        'availability': offer.get('availability') if offer else None,
    }


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
    blocked_at = None
    try:
        for item_index, (handle, urls) in enumerate(items):
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
                    challenge = bool(data.get('challenge')) or any(
                        word in low for word in (
                            'captcha', 'access denied', 'just a moment',
                            'verify you are human', 'request blocked',
                        )
                    )
                    if challenge:
                        blocked_at = datetime.now(ZoneInfo('Europe/Madrid')).isoformat(timespec='seconds')
                        result = {
                            'status': 'blocked',
                            'url': url,
                            'error': 'La página requiere verificación; se detuvo la lectura.',
                            'blocked_at': blocked_at,
                        }
                        stop_retailer = True
                        break
                    exact = _exact_product(data, expected_ean, retailer, product.get('query') or product.get('title_zoco'))
                    if exact:
                        has_price = exact.get('price') is not None and exact.get('price') > 0
                        result = {
                            **exact, 'status': 'matched' if has_price else 'matched_no_price', 'url': url,
                            'source': 'EAN visible y oferta JSON-LD en ficha oficial' if has_price else
                                      'Ficha oficial con EAN exacto; sin precio publicado',
                            'observed_at': datetime.now(ZoneInfo('Europe/Madrid')).isoformat(timespec='seconds'),
                            'live': has_price,
                        }
                        if has_price:
                            completed += 1
                            if on_progress:
                                on_progress(retailer, completed, count, handle)
                            break
                except Exception as exc:
                    if result is None:
                        result = {'status': 'error', 'url': url, 'error': str(exc)[:160]}
                completed += 1
                if on_progress:
                    on_progress(retailer, completed, count, handle)
                if len(urls) > 1:
                    await asyncio.sleep(PAGE_GAP_SECONDS)
            if result is None:
                result = {'status': 'unresolved', 'live': False}
            results[handle] = result
            # Espacia también productos distintos; una ráfaga de navegaciones
            # puede provocar denegaciones aunque cada ficha sea pública.
            if item_index + 1 < len(items) and not cancel.get('stop') and not stop_retailer:
                await asyncio.sleep(PAGE_GAP_SECONDS)
            if cancel.get('stop') or stop_retailer:
                break
        # Los productos que no llegaron a visitarse no son "sin coincidencia":
        # si la tienda denego el acceso, se marcan como bloqueados para que la
        # pausa sea explicita y no se confunda con ausencia de producto.
        for handle, urls in items:
            if handle in results:
                continue
            if cancel.get('stop'):
                results[handle] = {'status': 'cancelled', 'live': False}
            elif stop_retailer:
                results[handle] = {
                    'status': 'blocked',
                    'live': False,
                    'url': (urls or [None])[0],
                    'error': 'Lectura detenida tras una denegación en esta tienda.',
                    'blocked_at': blocked_at,
                }
            else:
                results[handle] = {'status': 'unresolved', 'live': False}
    finally:
        if browser is not None:
            try:
                await browser.stop()
            except Exception:
                pass
    return results


def _parse_timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo('Europe/Madrid'))
    return parsed


def _last_blocked_at(prev, handles, retailer):
    """Última denegación registrada para la tienda, si existe."""
    latest = None
    for handle in handles:
        record = prev.get(handle) or {}
        raw = record.get(f'{retailer}_blocked_at')
        if not raw and record.get(f'{retailer}_status') == 'blocked':
            raw = record.get('_snapshot_generated_at')
        when = _parse_timestamp(raw)
        if when and (latest is None or when > latest):
            latest = when
    return latest


def _allowed_product_url(url, allowed_host):
    parsed = urlparse(str(url or ''))
    host = (parsed.hostname or '').lower()
    return (
        parsed.scheme == 'https'
        and (host == allowed_host or host.endswith('.' + allowed_host))
        and parsed.path
    )


def _run_fetch_pages(targets, products, retailer, on_progress, cancel):
    return asyncio.run(_fetch_pages(targets, products, retailer, on_progress, cancel))


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
    changed_url = any(
        _allowed_product_url(product.get(f'url_{retailer}'), allowed_host)
        and product.get(f'url_{retailer}') != (prev.get(handle) or {}).get(f'url_{retailer}')
        for handle, product in by_handle.items()
    )
    last_blocked = _last_blocked_at(prev, by_handle, retailer)
    now = datetime.now(ZoneInfo('Europe/Madrid'))
    if last_blocked and not changed_url:
        retry_at = last_blocked + timedelta(hours=BLOCK_COOLDOWN_HOURS)
        if now < retry_at:
            when = retry_at.strftime('%d/%m/%Y %H:%M')
            paused = {}
            for handle, product in by_handle.items():
                record = prev.get(handle) or {}
                url = product.get(f'url_{retailer}') or record.get(f'url_{retailer}')
                if _allowed_product_url(url, allowed_host):
                    paused[handle] = {
                        'status': 'blocked',
                        'live': False,
                        'url': url,
                        'error': f'Lectura en pausa tras una denegación; se reintentará a partir de {when}.',
                        'blocked_at': record.get(f'{retailer}_blocked_at')
                        or last_blocked.isoformat(timespec='seconds'),
                    }
                else:
                    paused[handle] = {
                        'status': 'unresolved',
                        'live': False,
                        'error': 'Sin URL de producto confirmada en el catálogo para esta tienda.',
                    }
            return paused
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

    found = _run_fetch_pages(targets, by_handle, retailer, on_progress, cancel)
    for handle, result in found.items():
        if result.get('status') in ('blocked', 'cancelled') and not result.get('url'):
            result['url'] = (targets.get(handle) or [None])[0]
    for handle, product in by_handle.items():
        if handle not in found:
            found[handle] = {
                'status': 'cancelled' if cancel.get('stop') else 'unresolved',
                'live': False,
                'error': None if cancel.get('stop') else
                    'Sin URL de producto confirmada en el catalogo para esta tienda.',
                'url': product.get(f'url_{retailer}') or (prev.get(handle) or {}).get(f'url_{retailer}'),
            }
    return found
