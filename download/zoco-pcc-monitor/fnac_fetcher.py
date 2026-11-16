#!/usr/bin/env python3
"""Ofertas Fnac; visita URLs de producto confirmadas por EAN."""
from retailer_common import fetch_store_offers


def fetch_fnac(products, previous, on_progress=None, cancel=None):
    return fetch_store_offers(
        products, previous, 'fnac.es', 'fnac',
        on_progress=on_progress, cancel=cancel,
    )
