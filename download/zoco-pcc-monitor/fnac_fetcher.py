#!/usr/bin/env python3
"""Ofertas Fnac España; solo páginas publicadas en sus sitemaps oficiales."""
from retailer_common import fetch_store_offers

SITEMAPS = [
    'https://www.fnac.es/sitemapindex-master.xml',
    'https://www.fnac.es/sitemapindex-master-old.xml',
]


def fetch_fnac(products, previous, on_progress=None, cancel=None):
    return fetch_store_offers(
        products, previous, SITEMAPS, 'fnac.es', 'fnac',
        on_progress=on_progress, cancel=cancel,
    )
