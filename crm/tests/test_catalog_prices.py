"""Consumer prices and the articles taken over from the old shop (approved 27 Nov 2026)."""
import sqlite3, tempfile, unittest
from pathlib import Path
import harness
from db import connect
import checkout
from migrate import migrate
from pricing import PRODUCT_INFO, RETAIL_CHF, SAMPLE_PRODUCTS

OLD_SHOP = ('whiskey-cherry-panda', 'apfel-tabak-rhino', 'erdbeer-creme-tiger', 'felsenau-fuchs',
            'breitsch-hirsch-uf-ys', 'schnee-hase', 'abgrund-gemse')


class CatalogPriceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = harness.fresh_db()

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_seeded_article_has_a_retail_price(self):
        skus = {p[0] for p in SAMPLE_PRODUCTS}
        self.assertEqual(skus, set(RETAIL_CHF))
        self.assertEqual(len(skus), 32)
        for sku, price in RETAIL_CHF.items():
            self.assertIn(price, (25.0, 34.0), sku)

    def test_public_catalog_prices_and_old_shop_articles(self):
        c = connect()
        cat = checkout.public_catalog(c)
        c.close()
        by = {p['sku']: p for p in cat['products']}
        for sku in ('lemon-pie', 'mango-lassi', 'mandarine-nuss', 'apple-pie'):
            self.assertAlmostEqual(by[sku]['price_chf'], 25.0)
            self.assertTrue(by[sku]['retail'])
        for sku in OLD_SHOP:
            self.assertIn(sku, by)
            self.assertEqual(by[sku]['line'], PRODUCT_INFO[sku]['line'])
            self.assertTrue(by[sku]['image'].startswith('assets/web/'))
            self.assertTrue(by[sku]['description'])
        self.assertAlmostEqual(by['schnee-hase']['price_chf'], 34.0)
        self.assertAlmostEqual(by['whiskey-cherry-panda']['price_chf'], 25.0)
        self.assertTrue(by['abgrund-gemse']['image_placeholder'])
        self.assertTrue(by['breitsch-hirsch-uf-ys']['image_placeholder'])
        self.assertFalse(by['felsenau-fuchs']['orderable'])
        self.assertTrue(by['felsenau-fuchs']['sold_out'])
        self.assertTrue(by['schnee-hase']['orderable'])
        self.assertTrue(all(p['price_chf'] > 0 for p in cat['products']))

    def test_sold_out_cannot_be_bought(self):
        c = connect()
        with self.assertRaises(checkout.CheckoutError) as ctx:
            checkout.price_items(c, [{'sku': 'felsenau-fuchs', 'qty': 1}])
        self.assertEqual(ctx.exception.code, 'sold_out')
        lines, _ = checkout.price_items(c, [{'sku': 'abgrund-gemse', 'qty': 2}])
        c.close()
        self.assertAlmostEqual(lines[0]['unit_chf'], 34.0)

    def test_migrate_keeps_a_price_set_in_the_crm(self):
        c = connect()
        c.execute("update products set price_retail=29.5, description='eigener Text' where sku='schnee-hase'")
        c.commit()
        migrate(c)
        c.commit()
        row = c.execute("select price_retail,description from products where sku='schnee-hase'").fetchone()
        c.close()
        self.assertAlmostEqual(row['price_retail'], 29.5)
        self.assertEqual(row['description'], 'eigener Text')

    def test_placeholder_image_exists(self):
        root = Path(__file__).resolve().parents[2]
        for sku, info in PRODUCT_INFO.items():
            self.assertTrue((root / info['image']).is_file(), sku)


if __name__ == '__main__':
    unittest.main()
