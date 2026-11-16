#!/usr/bin/env python3
"""Importa las ofertas desde product feeds autorizados de Awin.

Las URLs privadas se configuran como secretos AWIN_CARREFOUR_FEED_URL y
AWIN_FNAC_FEED_URL en GitHub Actions. Nunca se imprimen ni se guardan en el repo.
"""
import csv
import gzip
import io
import os
import re
import urllib.request
import zipfile
from datetime import datetime
from urllib.parse import urlparse
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

FEED_ENV = {
    "carrefour": "AWIN_CARREFOUR_FEED_URL",
    "fnac": "AWIN_FNAC_FEED_URL",
}
TIMEOUT_SECONDS = 60
USER_AGENT = "zocopcc-price-monitor/1.0 (+https://zocopcc.vercel.app)"


def _request(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read()


def _csv_records(data):
    text = data.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;|\\t")
    except csv.Error:
        dialect = csv.excel
    return list(csv.DictReader(io.StringIO(text), dialect=dialect))


def _feed_rows(data):
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            if not names:
                return []
            data = archive.read(names[0])
    elif data[:2] == b"\\x1f\\x8b":
        data = gzip.decompress(data)

    text = data.decode("utf-8-sig", errors="replace")
    if text.lstrip().startswith("<"):
        root = ElementTree.fromstring(text)
        rows = []
        for product in root.iter():
            if product.tag.split("}")[-1].lower() != "product":
                continue
            rows.append({
                child.tag.split("}")[-1].lower(): (child.text or "").strip()
                for child in list(product)
            })
        return rows

    rows = _csv_records(data)
    return [
        {re.sub(r"[^a-z0-9]+", "", str(key or "").lower()): str(value or "").strip()
         for key, value in row.items()}
        for row in rows
    ]


def _normal_gtin(value):
    return re.sub(r"\\D", "", str(value or ""))


def _value(row, *names):
    for name in names:
        key = re.sub(r"[^a-z0-9]+", "", name.lower())
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _price(value):
    value = str(value or "").strip().replace(" ", "")
    if not value:
        return None
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".") if value.rfind(",") > value.rfind(".") else value.replace(",", "")
    else:
        value = value.replace(",", ".")
    try:
        parsed = float(value)
        return parsed if parsed > 0 else None
    except ValueError:
        return None


def _availability(row):
    value = _value(row, "in_stock", "stock_status", "is_for_sale").lower()
    if value in ("1", "yes", "true", "in stock", "instock", "available", "disponible"):
        return True
    if value in ("0", "no", "false", "out of stock", "outofstock", "agotado", "no disponible"):
        return False
    return None


def _offers_from_rows(products, rows, store, observed):
    by_ean = {}
    for row in rows:
        ean = _normal_gtin(_value(row, "ean", "product_GTIN", "gtin", "upc"))
        if not ean:
            continue
        currency = (_value(row, "currency") or "EUR").upper()
        price = _price(_value(row, "price"))
        if currency == "EUR" and price is not None:
            by_ean.setdefault(ean, []).append((row, price, _availability(row)))

    results = {}
    for product in products:
        handle = product["handle"]
        expected = _normal_gtin(product.get("ean"))
        candidates = by_ean.get(expected, [])
        if not candidates:
            results[handle] = {
                "status": "unresolved",
                "live": False,
                "error": "EAN exacto no encontrado en el feed Awin disponible.",
            }
            continue

        # Prioriza stock confirmado; dentro del mismo estado escoge el menor precio.
        row, price, stock = min(
            candidates,
            key=lambda item: (
                0 if item[2] is True else 1 if item[2] is None else 2,
                item[1],
            ),
        )
        results[handle] = {
            "status": "matched",
            "live": True,
            "title": _value(row, "product_name", "name"),
            "price": price,
            "seller": store.title() + " (anunciante Awin; vendedor no indicado)",
            "availability": stock,
            "sku": _value(row, "product_id", "sku", "mpn"),
            "ean": expected,
            # Es el enlace de afiliación oficial: debe conservarse sin modificar.
            "url": _value(row, "deep_link", "purl"),
            "source": "Feed de producto Awin",
            "observed_at": observed,
        }
    return results


def fetch_awin_offers(products, on_progress=None, cancel=None):
    """Devuelve {tienda: ofertas} solo para feeds configurados; None indica usar scraper previo."""
    cancel = cancel or {}
    results = {}
    observed = datetime.now(ZoneInfo("Europe/Madrid")).isoformat(timespec="seconds")

    for store, env_name in FEED_ENV.items():
        url = os.environ.get(env_name, "").strip()
        if not url:
            results[store] = None
            continue
        if urlparse(url).hostname != "productdata.awin.com":
            results[store] = {
                p["handle"]: {
                    "status": "error",
                    "live": False,
                    "error": "La URL del feed Awin no pertenece al dominio oficial productdata.awin.com.",
                }
                for p in products
            }
            continue
        if cancel.get("stop"):
            results[store] = {
                p["handle"]: {"status": "cancelled", "live": False} for p in products
            }
            continue
        try:
            rows = _feed_rows(_request(url))
            if not rows:
                raise ValueError("empty feed")
            store_results = _offers_from_rows(products, rows, store, observed)
        except Exception as exc:
            # No incluir URL ni texto de la excepción: la URL contiene la clave privada.
            error = f"No se pudo leer el feed Awin ({type(exc).__name__})."
            store_results = {
                p["handle"]: {"status": "error", "live": False, "error": error}
                for p in products
            }
        results[store] = store_results
        if on_progress:
            for index, product in enumerate(products, 1):
                on_progress(f"awin_{store}", index, len(products), product["handle"])
                if cancel.get("stop"):
                    break
    return results
