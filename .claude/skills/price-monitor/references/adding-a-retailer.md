# Adding a retailer

Use this reference before implementing another store integration. First inspect
the target site's public catalog, product pages, terms, and any documented API. Do
not assume the current Zococity or PCComponentes transport applies to another shop.

## Integration shape

Keep the canonical product catalog separate from retailer offers. The current
catalog is Zococity-based and each product has a `handle`, `query`, optional `brand`,
and store-specific product URL. A new retailer should contribute one normalized
offer per matched canonical product, for example:

```json
{
  "price": 123.45,
  "currency": "EUR",
  "availability": true,
  "seller": "Retailer name",
  "sku": "store SKU",
  "ean": "1234567890123",
  "product_url": "https://store.example/product",
  "source": "official product JSON-LD",
  "observed_at": "2026-11-15T17:00:00+01:00",
  "live": true
}
```

Keep the actual schema consistent with the current code until a coordinated schema
migration is explicitly chosen. Prefer a focused `*_fetcher.py` adapter and a clear
normalization boundary. Keep retry, rate-limit, session and parsing behavior inside
that adapter; keep product matching and snapshot policy in the pipeline.

## Matching products safely

1. Prefer exact EAN/GTIN, then exact manufacturer part number/SKU, then model and
   brand plus attributes that define the variant.
2. Check variant attributes such as color, capacity, impedance, generation, region,
   and included accessories when they affect the actual item.
3. Treat text similarity as a candidate generator, not proof. Store confidence or
   a review state if ambiguity remains.
4. Never turn an unmatched search result into a price for the canonical product.
5. Keep not-found, out-of-stock, temporarily blocked, parse failure, and unknown
   as distinct states wherever the source allows it.

## Reading and normalizing offers

- Prefer a documented public API or structured data on the official product page.
- Preserve currency and seller/marketplace identity. Do not assume every offer is
  sold by the retailer itself.
- Convert price to a numeric decimal in EUR only when the source currency and
  conversion are known. Keep shipping, tax inclusion, and price type explicit if
  they differ across stores.
- Attach the official product URL and the exact evidence source (API, JSON-LD, or
  product page) with each offer.
- Use bounded concurrency and human-scale request spacing. Cache successful reads.
  Respect terms and robots policy; stop on CAPTCHA, login, access denial, or an
  explicit anti-automation restriction rather than trying to evade it.

## Failure and snapshot policy

- A retailer failure must not erase that retailer's last good offer or alter the
  other retailers' offers.
- Store `last_success_at` / observation time per offer or store. Do not update a
  timestamp merely because the overall pipeline ran.
- If a source fails, keep the last known price but mark it stale and show the
  source status clearly in the UI.
- Publish a snapshot atomically after parsing and validation. Do not publish a
  partial run as if every store had succeeded.

## Review checklist

- Confirm that representative product fixtures parse without a network call.
- Cover a normal product, a missing product, out of stock, a marketplace seller,
  malformed or missing price, and a variant mismatch.
- Compare the normalized result with the official source manually for a small
  sample before enabling scheduled reads.
- Confirm the new store appears in comparison, filtering, freshness indicators,
  and any export without changing existing store labels or dates.
- Keep the README and operator guide aligned with the actual workflow and secret
  locations. Never put live credentials or cookie data in fixtures.
