import json, unittest
import harness
from db import connect
from crmlib import set_member_status

class OrderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = harness.fresh_db()
        self.port = harness.ensure_server()

    def tearDown(self):
        self.tmp.cleanup()

    def test_webhook_converts_prospect_and_keeps_campaign_history(self):
        c = connect()
        cid = c.execute(
            """insert into customers(name,email,customer_type,company_name,city,priority,language)
               values('Dampfkiosk','kiosk@example.com','Interessent','Dampfkiosk','Bern','A','de')""").lastrowid
        from crmlib import enroll_prospects
        enroll_prospects(c)
        mid = c.execute('select id,status from campaign_members where customer_id=?', (cid,)).fetchone()
        self.assertEqual(mid['status'], 'bereit')
        set_member_status(c, mid['id'], 'mail_gesendet', 'Testverlauf', 'CRM')
        c.commit()
        c.close()
        client = harness.Client(self.port)
        payload = {
            'event_id': 'evt-shop-1', 'email': 'kiosk@example.com', 'name': 'Dampfkiosk',
            'company': 'Dampfkiosk', 'items': [{'article': 'Lemon Pie', 'qty': 1, 'unit_chf': 12.9}],
        }
        st, data, _ = client.request('POST', '/webhook/order', json_body=payload, headers={'X-Bernvapes-Secret': 'nope'})
        self.assertEqual(st, 401)
        st, data, _ = client.request('POST', '/webhook/order', json_body=payload, headers={'X-Bernvapes-Secret': 'whsec-test'})
        self.assertEqual(st, 202, data)
        self.assertTrue(data['converted_to_business'])
        st, dup, _ = client.request('POST', '/webhook/order', json_body=payload, headers={'X-Bernvapes-Secret': 'whsec-test'})
        self.assertEqual(st, 200)
        self.assertEqual(dup['status'], 'duplicate')
        c = connect()
        cust = c.execute('select customer_type,converted_at,age_verified_at from customers where id=?', (cid,)).fetchone()
        member = c.execute('select status from campaign_members where customer_id=?', (cid,)).fetchone()
        events = [r['new_status'] for r in c.execute('select new_status from campaign_events where customer_id=? order by id', (cid,))]
        n_orders = c.execute('select count(*) from orders').fetchone()[0]
        c.close()
        self.assertEqual(cust['customer_type'], 'Businesskunde')
        self.assertTrue(cust['converted_at'])
        self.assertIsNone(cust['age_verified_at'])
        self.assertEqual(member['status'], 'bestellt')
        self.assertIn('bereit', events)
        self.assertIn('mail_gesendet', events)
        self.assertIn('bestellt', events)
        self.assertEqual(n_orders, 1)

    def test_portal_order_uses_tier_price_rechnung_and_converts(self):
        admin = harness.admin_login(self.port)
        st, _, _ = admin.request('POST', '/kunden/neu', form={
            'company_name': 'Dampfwerk Test', 'email': 'dampfwerk@example.com',
            'city': 'Bern', 'priority': 'A', 'language': 'de', 'contact_person': 'Test Person'})
        self.assertEqual(st, 303)
        c = connect()
        cid = c.execute("select id from customers where email='dampfwerk@example.com'").fetchone()[0]
        c.close()
        st, _, text = admin.request('POST', f'/kontakt/{cid}/einladung', form={
            'email': 'dampfwerk@example.com', 'tier': 'haendler'})
        self.assertEqual(st, 303)
        c = connect()
        body = c.execute('select body from mail_log order by id desc limit 1').fetchone()[0]
        c.close()
        self.assertIn('haendler.html?token=', body)
        token = body.split('token=', 1)[1].split()[0].strip()
        shop = harness.Client(self.port)
        from auth import totp_code
        st, data, _ = shop.request('POST', '/api/b2b/invite/accept', json_body={'token': token, 'password': 'dealer-password-1'})
        self.assertEqual(st, 200, data)
        secret = data['totp_secret']
        st, data, _ = shop.request('POST', '/api/b2b/totp/confirm', json_body={'code': totp_code(secret)})
        self.assertEqual(st, 200, data)
        self.assertEqual(data['status'], 'approved')
        self.assertTrue(data['company_verified'])
        st, cat, _ = shop.request('GET', '/api/b2b/catalog')
        lemon = next(p for p in cat['products'] if p['sku'] == 'lemon-pie')
        self.assertAlmostEqual(lemon['unit_chf'], 10.40, places=2)
        st, res, _ = shop.request('POST', '/api/b2b/orders', json_body={
            'event_id': 'b2b-evt-1',
            'items': [{'sku': 'lemon-pie', 'qty': 2, 'unit_chf': 0.01}, {'sku': 'mango-lassi', 'qty': 1, 'unit_chf': 0.01}],
        })
        self.assertEqual(st, 202, res)
        self.assertEqual(res['payment_method'], 'rechnung')
        self.assertTrue(res['converted_to_business'])
        self.assertTrue(res['company_verified'])
        self.assertEqual(res['bexio']['status'], 'disabled')
        self.assertFalse(res['bexio']['created'])
        c = connect()
        cust = c.execute('select customer_type,age_verified_at from customers where id=?', (cid,)).fetchone()
        order = c.execute('select total_chf,payment_method,channel from orders where id=?', (res['order_id'],)).fetchone()
        items = c.execute('select article,qty,unit_chf from order_items where order_id=?', (res['order_id'],)).fetchall()
        member = c.execute('select status from campaign_members where customer_id=?', (cid,)).fetchone()
        events = c.execute('select count(*) from campaign_events where customer_id=?', (cid,)).fetchone()[0]
        note = c.execute("select body from notes where customer_id=? and body like '%bexio%'", (cid,)).fetchone()[0]
        c.close()
        self.assertEqual(cust['customer_type'], 'Businesskunde')
        self.assertIsNone(cust['age_verified_at'])
        self.assertEqual(order['payment_method'], 'rechnung')
        self.assertEqual(order['channel'], 'b2b')
        self.assertAlmostEqual(order['total_chf'], 10.40 * 2 + 10.40, places=2)
        units = sorted(i['unit_chf'] for i in items)
        self.assertTrue(all(abs(u - 10.40) < 0.001 for u in units))
        self.assertNotIn(0.01, units)
        self.assertEqual(member['status'], 'bestellt')
        self.assertGreaterEqual(events, 2)
        self.assertIn('disabled', note)
        self.assertIn('No bexio request', note)

    def test_postgres_placeholder_translation(self):
        from db import translate
        sql = translate("insert or ignore into products(sku) values(?)", True)
        self.assertIn('ON CONFLICT DO NOTHING', sql)
        self.assertIn('RETURNING id', sql)
        self.assertIn('%s', sql)
        self.assertNotIn('?', sql)
        self.assertIn('clock_timestamp()', translate("update orders set updated_at=datetime('now') where id=?", True))

    def test_bexio_stub_has_no_http_client(self):
        import inspect, bexio_billing
        src = inspect.getsource(bexio_billing)
        self.assertNotIn('urlopen', src)
        self.assertNotIn('api.bexio.com', src)
        self.assertNotIn('requests', src)
        import mailer
        self.assertNotIn('smtplib', inspect.getsource(mailer))
        result = bexio_billing.BexioBilling().create_invoice({'order_id': 1})
        self.assertEqual(result['status'], 'disabled')
        self.assertFalse(result['created'])

if __name__ == '__main__':
    unittest.main()
