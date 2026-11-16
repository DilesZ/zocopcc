#!/usr/bin/env python3
"""Ofertas Carrefour España; solo páginas publicadas en sus sitemaps oficiales."""
from retailer_common import fetch_store_offers

SITEMAPS = [
    'https://www.carrefour.es/tecno/dyn/MEDIA/siteindex.xml',
    'https://www.carrefour.es/_includes/sitemap.xml',
]


def fetch_carrefour(products, previous, on_progress=None, cancel=None):
    return fetch_store_offers(
        products, previous, SITEMAPS, 'carrefour.es', 'carrefour',
        on_progress=on_progress, cancel=cancel,
    )
