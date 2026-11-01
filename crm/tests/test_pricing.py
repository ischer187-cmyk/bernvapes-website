import unittest
import harness
from db import connect
from pricing import unit_price

class PricingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = harness.fresh_db()
        self.port = harness.ensure_server()

    def tearDown(self):
        self.tmp.cleanup()

    def _dealer(self, tier):
        c = connect()
        cid = c.execute(
            "insert into customers(name,email,customer_type,company_name) values(?,?, 'Interessent', ?)",
            ('Preis Shop', f'{tier}@example.com', 'Preis Shop')).lastrowid
        did = c.execute(
            """insert into dealer_accounts(customer_id,email,status,company_name,price_tier,totp_confirmed,company_verified_at,company_verify_method)
               values(?,?, 'approved', ?, ?, 1, datetime('now'), 'test')""",
            (cid, f'{tier}@example.com', 'Preis Shop', tier)).lastrowid
        c.commit()
        prod = c.execute("select * from products where sku='lemon-pie'").fetchone()
        c.close()
        return did, prod

    def test_tier_columns_and_override(self):
        for tier, expected in (('einstieg', 12.90), ('haendler', 10.40), ('grosshaendler', 8.20)):
            did, prod = self._dealer(tier)
            c = connect()
            price, over = unit_price(c, did, prod)
            c.close()
            self.assertFalse(over)
            self.assertAlmostEqual(price, expected, places=2)
        did, prod = self._dealer('extra')
        c = connect()
        c.execute("update dealer_accounts set price_tier='haendler' where id=?", (did,))
        c.execute('insert into price_overrides(dealer_id,product_id,unit_chf) values(?,?,?)', (did, prod['id'], 5))
        c.commit()
        price, over = unit_price(c, did, prod)
        c.close()
        self.assertTrue(over)
        self.assertAlmostEqual(price, 5.0, places=2)

    def test_catalog_hides_prices_until_approved_and_uses_server_price(self):
        anon = harness.Client(self.port)
        st, _, _ = anon.request('GET', '/api/b2b/catalog')
        self.assertEqual(st, 401)
        st, data, _ = anon.request('POST', '/api/b2b/register', json_body={
            'company_name': 'Preisblick GmbH', 'uid': 'CHE-100.200.300',
            'email': 'preisblick@example.com', 'password': 'dealer-password-1', 'language': 'de'})
        self.assertEqual(st, 201, data)
        from auth import totp_code
        st, data, _ = anon.request('POST', '/api/b2b/totp/confirm', json_body={'code': totp_code(data['totp_secret'])})
        self.assertEqual(st, 200)
        self.assertEqual(data['status'], 'pending')
        st, cat, _ = anon.request('GET', '/api/b2b/catalog')
        self.assertEqual(st, 200)
        self.assertFalse(cat['prices_visible'])
        self.assertTrue(all(p['unit_chf'] is None for p in cat['products']))
        self.assertTrue(any(p['name'] == 'Lemon Pie' for p in cat['products']))
        admin = harness.admin_login(self.port)
        c = connect()
        did = c.execute("select id from dealer_accounts where email='preisblick@example.com'").fetchone()[0]
        c.close()
        st, _, _ = admin.request('POST', f'/haendler/{did}/stufe', form={'tier': 'grosshaendler'})
        self.assertEqual(st, 303)
        st, _, _ = admin.request('POST', f'/haendler/{did}/aktion', form={'a': 'approve'})
        self.assertEqual(st, 303)
        st, cat, _ = anon.request('GET', '/api/b2b/catalog')
        self.assertTrue(cat['prices_visible'])
        self.assertEqual(cat['tier'], 'grosshaendler')
        lemon = next(p for p in cat['products'] if p['sku'] == 'lemon-pie')
        self.assertAlmostEqual(lemon['unit_chf'], 8.20, places=2)
        st, _, _ = admin.request('POST', f'/haendler/{did}/preis', form={'sku': 'lemon-pie', 'unit_chf': '5.50'})
        self.assertEqual(st, 303)
        st, cat, _ = anon.request('GET', '/api/b2b/catalog')
        lemon = next(p for p in cat['products'] if p['sku'] == 'lemon-pie')
        self.assertTrue(lemon['override'])
        self.assertAlmostEqual(lemon['unit_chf'], 5.50, places=2)
        mango = next(p for p in cat['products'] if p['sku'] == 'mango-lassi')
        self.assertFalse(mango['override'])
        self.assertAlmostEqual(mango['unit_chf'], 8.20, places=2)

if __name__ == '__main__':
    unittest.main()
