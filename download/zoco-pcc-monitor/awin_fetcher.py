#!/usr/bin/env python3
"""Importa ofertas de Fnac y Carrefour desde los product feeds autorizados de Awin.

AWIN_FEED_LIST_URL debe ser el enlace feedList privado de Awin guardado como
secreto en GitHub Actions. El código nunca registra esa URL ni los enlaces de
descarga que incluyen la clave.
"""
import csv
import gzip
import io
import json
import os
import re
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from xml.etree import ElementTree

from zoneinfo import ZoneInfo

ADVERTISERS = {
    "carrefour": "25399",
    "fnac": "77630",
}
TIMEOUT_SECONDS = 60
USER_AGENT = "zocopcc-price-monitor/1.0 (+https://zocopcc.vercel.app)"


def _request(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read(), response.headers.get("Last-Modified")


def _parse_csv_bytes(data):
    text = data.decode("utf-8-sig", errors="replace")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
    except csv.Error:
        dialect = csv.excel
    return list(csv.reader(io.StringIO(text), dialect))


def _feed_rows(data):
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = [n for n in archive.namelist() if not n.endswith("/")]
            if not names:
                return []
            data = archive.read(names[0])
    elif data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)

    text = data.decode("utf-8-sig", errors="replace")
    if text.lstrip().startswith("<"):
        root = ElementTree.fromstring(text)
        rows = []
        for product in root.iter():
            if product.tag.split("}")[-1].lower() != "product":
                continue
            row = {}
            for child in list(product):
                row[child.tag.split("}")[-1].lower()] = (child.text or "").strip()
            if row:
                rows.append(row)
        return rows

    records = _parse_csv_bytes(data)
    if not records:
        return []
    headers = [re.sub(r"[^a-z0-9]+", "", h.strip().lower()) for h in records[0]]
    rows = []
    for values in records[1:]:
        if len(values) != len(headers):
            continue
        rows.append(dict(zip(headers, (v.strip() for v in values)))
    return rows


def _feed_list(data):
    rows = _parse_csv_bytes(data)
    feeds = {store: [] for store in ADVERTISERS}
    for row in rows:
        if len(row) < 13 or not row[0].strip().isdigit():
            continue
        advertiser_id = row[0].strip()
        store = next((s for s, aid in ADVERTISERS.items() if aid == advertiser_id), None)
        if not store:
            continue
        region = row[2].strip().upper()
        language = row[7].strip().lower()
        if region not in ("ES", "") and not language.startswith(("spanish", "es")):
            continue
        url = row[12].strip()
        if urlparse(url).hostname != "productdata.awin.com":
            continue
        feeds[store].append({
            "id": row[5].strip(),
            "name": row[6].strip(),
            "language": row[7].strip(),
            "last_imported": row[9].strip(),
            "url": url,
        })
    return feeds


def _normal_gtin(value):
    return re.sub(r"\D", "", str(value or ""))


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
        result = float(value)
        return result if result > 0 else None
    except ValueError:
        return None


def _in_stock(value):
    value = str(value or "").strip().lower()
    if value in ("1", "yes", "true", "in stock", "instock", "available", "disponible"):
        return True
    if value in ("0", "no", "false", "out of stock", "outofstock", "agotado", "no disponible"):
        return False
    return None


def _rows_for_store(feed, store):
    data, _ = _request(feed["url"])
    return _feed_rows(data)


def _match_store(products, previous, feed_rows, store, on_progress=None):
    by_ean = {}
    for row in feed_rows:
        ean = _normal_gtin(_value(row, "ean", "product_GTIN", "gtin", "upc"))
        if not ean:
            continue
        currency = (_value(row, "currency") or "EUR").upper()
        price = _price(_value(row, "price"))
        if currency != "EUR" or price is None:
            continue
        by_ean.setdefault(ean, []).append(row)

    results = {}
    total = len(products)
    observed = datetime.now(ZoneInfo("Europe/Madrid")).isoformat(timespec="seconds")
    for index, product in enumerate(products, 1):
        handle = product.get("handle")
        expected = _normal_gtin(product.get("ean"))
        candidates = by_ean.get(expected, [])
        if candidates:
            ranked = []
            for row in candidates:
                price = _price(_value(row, "price"))
                stock = _in_stock(_value(row, "in_stock", "stock_status", "is_for_sale"))
                ranked.append((0 if stock is True else 1 if stock is None else 2, price, row, stock))
            _, price, row, stock = min(ranked, key=lambda item: (item[0], item[1]))
            results[handle] = {
                "status": "matched",
                "live": True,
                "title": _value(row, "product_name", "name"),
                "price": price,
                "seller": store.title() + " (feed Awin; vendedor no indicado)",
                "availability": stock,
                "sku": _value(row, "product_id", "sku", "mpn"),
                "ean": expected,
                "url": _value(row, "deep_link", "purl"),
                "source": "Feed de producto Awin",
                "observed_at": observed,
            }
        else:
            old = (previous.get(handle) or {})
            had_feed_value = (old.get(f"source_{store}") or "").startswith("Feed de producto Awin")
            results[handle] = {
                "status": "unresolved",
                "live": False,
                "error": None if had_feed_value else "EAN exacto no encontrado en el feed Awin disponible.",
            }
        if on_progress:
            on_progress(f"awin_{store}", index, total, handle)
    return results


def fetch_awin_offers(products, previous, previous_versions=None, on_progress=None, cancel=None):
    """Devuelve ofertas por tienda y versiones de feed; no expone ni registra claves."""
    previous_versions = previous_versions or {}
    cancel = cancel or {}
    feed_list_url = os.environ.get("AWIN_FEED_LIST_URL", "").strip()
    if not feed_list_url:
        return None, previous_versions
    if urlparse(feed_list_url).hostname != "ui.awin.com":
        return None, previous_versions

    try:
        data, _ = _request(feed_list_url)
        feeds = _feed_list(data)
    except Exception as exc:
        # No incluir la URL ni el texto de la excepción: ambos podrían contener claves.
        error = f"No se pudo consultar el feed Awin ({type(exc).__name__})."
        return {
            store: {p["handle"]: {"status": "error", "live": False, "error": error}
                    for p in products}
            for store in ADVERTISERS
        }, previous_versions

    all_results = {}
    new_versions = dict(previous_versions)
    for store in ADVERTISERS:
        if cancel.get("stop"):
            all_results[store] = {
                p["handle"]: {"status": "cancelled", "live": False} for p in products
            }
            continue
        store_feeds = feeds.get(store) or []
        if not store_feeds:
            all_results[store] = {
                p["handle"]: {
                    "status": "feed_unavailable",
                    "live": False,
                    "error": "Awin no ofrece un feed de este anunciante para esta cuenta/idioma.",
                } for p in products
            }
            continue
        combined_rows = []
        versions = []
        store_error = None
        for feed in store_feeds:
            try:
                version = feed["last_imported"] or feed["id"]
                old_version = (previous_versions.get(store) or {}).get(feed["id"])
                if old_version == version:
                    # El feed no ha cambiado; se reutiliza la última lectura confirmada.
                    continue
                combined_rows.extend(_rows_for_store(feed, store))
                versions.append((feed["id"], version))
            except Exception as exc:
                store_error = f"No se pudo descargar el feed Awin ({type(exc).__name__})."
        if combined_rows:
            for feed_id, version in versions:
                new_versions.setdefault(store, {})[feed_id] = version
            all_results[store] = _match_store(
                products, previous, combined_rows, store, on_progress=on_progress
            )
        else:
            # Sin cambios: reutiliza solo las filas previamente verificadas en este feed.
            old_results = {}
            for p in products:
                old = previous.get(p["handle"]) or {}
                source = old.get(f"source_{store}") or ""
                if source.startswith("Feed de producto Awin") and old.get(f"price_{store}") is not None:
                    old_results[p["handle"]] = {
                        "status": "matched",
                        "live": True,
                        "title": old.get(f"title_{store}"),
                        "price": old.get(f"price_{store}"),
                        "seller": old.get(f"seller_{store}"),
                        "availability": old.get(f"stock_{store}"),
                        "sku": old.get(f"sku_{store}"),
                        "ean": old.get(f"ean_{store}"),
                        "url": old.get(f"url_{store}"),
                        "source": "Feed de producto Awin (sin cambios desde su última publicación)",
                        "observed_at": old.get("generated_at"),
                    }
            if old_results and not store_error:
                all_results[store] = old_results
            else:
                error = store_error or "Awin indica que el feed no ha cambiado, pero no hay lectura previa."
                all_results[store] = {
                    p["handle"]: {"status": "error", "live": False, "error": error}
                    for p in products
                }
    return all_results, new_versions
