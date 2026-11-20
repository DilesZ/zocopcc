import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import retailer_common as rc
from awin_fetcher import _feed_rows, _offers_from_rows, _price
from pipeline import merge_store_offer

CARREFOUR_URL = (
    'https://www.carrefour.es/auriculares-magneticos-planos-abiertos-de-90-mm-fiio-ft5/'
    '6953175741060/p'
)
EAN = '6953175741060'


def carrefour_jsonld(price='796.49'):
    return {
        'title': 'Auriculares Magnéticos Planos Abiertos De 90 Mm Fiio Ft5',
        'text': '',
        'products': [{
            'name': 'Auriculares Magnéticos Planos Abiertos De 90 Mm Fiio Ft5',
            'sku': EAN,
            'gtin': '',
            'offers': {
                'price': price,
                'priceCurrency': 'EUR',
                'availability': 'https://schema.org/InStock',
                'seller': {'name': 'Stock Network'},
            },
        }],
    }


class GtinTests(unittest.TestCase):
    def test_carrefour_sku_is_used_as_gtin(self):
        self.assertEqual(rc._gtin({'sku': EAN}), EAN)

    def test_internal_sku_is_not_a_gtin(self):
        self.assertEqual(rc._gtin({'sku': '9728616'}), '')

    def test_exact_match_uses_sku_without_gtin(self):
        result = rc._exact_product(carrefour_jsonld(), EAN, 'carrefour', 'FiiO FT5')
        self.assertIsNotNone(result)
        self.assertEqual(result['price'], 796.49)
        self.assertEqual(result['ean'], EAN)

    def test_gtin_match_with_leading_zero(self):
        self.assertTrue(rc._gtin_match('0747192138479', '747192138479'))
        self.assertTrue(rc._gtin_match('747192138479', '0747192138479'))
        self.assertFalse(rc._gtin_match('1234567890123', '9876543210987'))


class CooldownTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(ZoneInfo('Europe/Madrid'))
        self.product = {'handle': 'p1', 'url_carrefour': CARREFOUR_URL, 'ean': EAN}
        self.other = {'handle': 'p2', 'ean': '1234567890123'}

    def _run(self, products, previous, fake):
        original = rc._run_fetch_pages
        rc._run_fetch_pages = fake
        try:
            return rc.fetch_store_offers(products, previous, 'carrefour.es', 'carrefour')
        finally:
            rc._run_fetch_pages = original

    def test_recent_block_pauses_only_products_with_url(self):
        previous = {
            'p1': {
                'carrefour_blocked_at': self.now.isoformat(timespec='seconds'),
                'url_carrefour': CARREFOUR_URL,
            }
        }

        def no_fetch(*args, **kwargs):
            raise AssertionError('no debería abrir el navegador durante la pausa')

        out = self._run([self.product, self.other], previous, no_fetch)
        self.assertEqual(out['p1']['status'], 'blocked')
        self.assertEqual(out['p1']['url'], CARREFOUR_URL)
        self.assertEqual(out['p2']['status'], 'unresolved')
        self.assertNotIn('url_carrefour', out['p2'])

    def test_expired_block_retries(self):
        old = self.now - timedelta(hours=rc.BLOCK_COOLDOWN_HOURS + 1)
        previous = {
            'p1': {
                'carrefour_blocked_at': old.isoformat(timespec='seconds'),
                'url_carrefour': CARREFOUR_URL,
            }
        }

        def matched_fetch(url_map, products, retailer, on_progress, cancel):
            return {
                'p1': {
                    'status': 'matched', 'live': True, 'title': 'FiiO FT5',
                    'price': 796.49, 'seller': 'Stock Network', 'availability': True,
                    'sku': EAN, 'ean': EAN, 'url': CARREFOUR_URL,
                    'source': 'test',
                    'observed_at': self.now.isoformat(timespec='seconds'),
                }
            }

        out = self._run([self.product, self.other], previous, matched_fetch)
        self.assertEqual(out['p1']['status'], 'matched')
        self.assertEqual(out['p1']['price'], 796.49)
        self.assertEqual(out['p2']['status'], 'unresolved')

    def test_changed_url_bypasses_cooldown(self):
        previous = {
            'p1': {
                'carrefour_blocked_at': self.now.isoformat(timespec='seconds'),
                'url_carrefour': 'https://www.carrefour.es/otro-producto/123/p',
            }
        }

        def matched_fetch(*args, **kwargs):
            return {'p1': {'status': 'matched', 'live': True}}

        out = self._run([self.product, self.other], previous, matched_fetch)
        self.assertEqual(out['p1']['status'], 'matched')

    def test_legacy_block_uses_snapshot_timestamp(self):
        previous = {
            'p1': {
                'carrefour_status': 'blocked',
                'url_carrefour': CARREFOUR_URL,
                '_snapshot_generated_at': self.now.isoformat(timespec='seconds'),
            }
        }

        def no_fetch(*args, **kwargs):
            raise AssertionError('no debería abrir el navegador durante la pausa')

        out = self._run([self.product, self.other], previous, no_fetch)
        self.assertEqual(out['p1']['status'], 'blocked')
        self.assertEqual(out['p1']['url'], CARREFOUR_URL)


class MergeTests(unittest.TestCase):
    def test_blocked_offer_keeps_catalog_url_and_block_timestamp(self):
        rec = {}
        blocked_at = '2026-11-19T10:00:00+01:00'
        merge_store_offer(
            rec, 'carrefour',
            {'status': 'blocked', 'error': 'pausa', 'blocked_at': blocked_at},
            {}, catalog_url=CARREFOUR_URL,
        )
        self.assertEqual(rec['url_carrefour'], CARREFOUR_URL)
        self.assertEqual(rec['carrefour_status'], 'blocked')
        self.assertEqual(rec['carrefour_blocked_at'], blocked_at)

    def test_blocked_offer_preserves_previous_block_timestamp(self):
        rec = {}
        blocked_at = '2026-11-19T10:00:00+01:00'
        merge_store_offer(
            rec, 'carrefour',
            {'status': 'blocked', 'error': 'pausa'},
            {'carrefour_blocked_at': blocked_at},
            catalog_url=CARREFOUR_URL,
        )
        self.assertEqual(rec['carrefour_blocked_at'], blocked_at)
        self.assertEqual(rec['carrefour_status'], 'blocked')

    def test_matched_offer_clears_previous_block(self):
        rec = {'carrefour_blocked_at': '2026-11-19T10:00:00+01:00'}
        merge_store_offer(
            rec, 'carrefour',
            {
                'status': 'matched', 'title': 'FiiO FT5', 'price': 796.49,
                'seller': 'Stock Network', 'availability': True, 'sku': EAN,
                'ean': EAN, 'url': CARREFOUR_URL, 'source': 'test',
                'observed_at': '2026-11-19T11:00:00+01:00',
            },
            {}, catalog_url=CARREFOUR_URL,
        )
        self.assertEqual(rec['carrefour_status'], 'matched')
        self.assertNotIn('carrefour_blocked_at', rec)
        self.assertTrue(rec['carrefour_live'])


class AwinTests(unittest.TestCase):
    def test_price_formats(self):
        self.assertEqual(_price('1.234,56'), 1234.56)
        self.assertEqual(_price('1,234.56'), 1234.56)
        self.assertEqual(_price('796,49'), 796.49)

    def test_csv_feed_matches_exact_ean(self):
        data = (
            'ean;product_name;price;currency;in_stock;deep_link\n'
            '6953175741060;FiiO FT5;796,49;EUR;1;https://www.awin1.com/pclick.php?p=1\n'
        ).encode('utf-8')
        rows = _feed_rows(data)
        out = _offers_from_rows(
            [{'handle': 'fiio-ft5', 'ean': EAN}], rows, 'carrefour',
            '2026-11-19T10:00:00+01:00',
        )
        self.assertEqual(out['fiio-ft5']['status'], 'matched')
        self.assertEqual(out['fiio-ft5']['price'], 796.49)
        self.assertEqual(out['fiio-ft5']['url'], 'https://www.awin1.com/pclick.php?p=1')

    def test_xml_feed_matches_exact_ean(self):
        data = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<products>\n'
            '  <product>\n'
            '    <product_GTIN>6953175741060</product_GTIN>\n'
            '    <product_name>FiiO FT5</product_name>\n'
            '    <search_price>796.49</search_price>\n'
            '    <currency>EUR</currency>\n'
            '    <in_stock>1</in_stock>\n'
            '    <aw_deep_link>https://www.awin1.com/pclick.php?p=2</aw_deep_link>\n'
            '  </product>\n'
            '</products>\n'
        ).encode('utf-8')
        rows = _feed_rows(data)
        out = _offers_from_rows(
            [{'handle': 'fiio-ft5', 'ean': EAN}], rows, 'carrefour',
            '2026-11-19T10:00:00+01:00',
        )
        self.assertEqual(out['fiio-ft5']['status'], 'matched')
        self.assertEqual(out['fiio-ft5']['price'], 796.49)
        self.assertEqual(out['fiio-ft5']['url'], 'https://www.awin1.com/pclick.php?p=2')


if __name__ == '__main__':
    unittest.main()
