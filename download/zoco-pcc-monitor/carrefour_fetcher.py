#!/usr/bin/env python3
"""Ofertas Carrefour; visita URLs de producto confirmadas por EAN."""
from retailer_common import fetch_store_offers


def fetch_carrefour(products, previous, on_progress=None, cancel=None):
    return fetch_store_offers(
        products, previous, 'carrefour.es', 'carrefour',
        on_progress=on_progress, cancel=cancel,
    )
