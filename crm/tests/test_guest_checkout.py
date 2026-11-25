"""Gastbestellung ohne Kundenkonto: Vorschau, Bestellung, Mail, Status-Link, Grenzen. Kein Live-Aufruf."""
import os, unittest
from urllib.parse import parse_qs, urlsplit

import harness
import bexio_sync
import checkout
import postfinance
from db import connect
from test_checkout import Gateway, SECRET_B64, _birth

ITEMS = [{'sku': 'mango-lassi', 'qty': 1}, {'id': 'gipfel_adler_100ml', 'name': 'Gipfel Adler', 'qty': 3}]
GUEST = {'name': 'Gina Gast', 'email': 'Gina.Gast@example.com', 'address': 'Teststrasse 1',
         'zip': '3011', 'city': 'Bern', 'phone': ''}


def _body(**extra):
    body = {'items': ITEMS, 'guest': dict(GUEST), 'birthdate': _birth(-30),
            'age_confirmed': True, 'terms_accepted': True}
    body.update(extra)
    return body


class GuestCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = harness.fresh_db()
        self.port = harness.ensure_server()
        postfinance.set_transport(None)
        bexio_sync.set_transport(None)
        os.environ['BEXIO_SYNC_ENABLED'] = '0'
        os.environ['POSTFINANCE_SPACE_ID'] = '102832'
        os.environ['POSTFINANCE_USER_ID'] = '555'
        os.environ['POSTFINANCE_SPACE_KEY'] = SECRET_B64
        self.gate = Gateway()
        postfinance.set_transport(self.gate)
        self.mail_log = os.environ['CRM_MAIL_LOG']
        if os.path.exists(self.mail_log):
            os.remove(self.mail_log)

    def tearDown(self):
        postfinance.set_transport(None)
        bexio_sync.set_transport(None)
        for key in ('POSTFINANCE_SPACE_ID', 'POSTFINANCE_USER_ID', 'POSTFINANCE_SPACE_KEY',
                    'CRM_GUEST_LIMIT_PER_EMAIL'):
            os.environ.pop(key, None)
        self.tmp.cleanup()

    def post(self, body, client=None):
        c = client or harness.Client(self.port)
        return c.request('POST', '/api/b2b/customer/guest/checkout', json_body=body)

    def test_preview_without_login_and_without_address(self):
        st, data, _ = self.post({'items': ITEMS, 'preview': True})
        self.assertEqual(st, 200, data)
        self.assertTrue(data['guest'])
        self.assertTrue(data['needs_age_check'])
        self.assertNotIn('customer_id', data)
        self.assertEqual(len(self.gate.calls), 0)

    def test_guest_order_creates_contact_order_mail_and_status_link(self):
        st, placed, _ = self.post(_body())
        self.assertEqual(st, 200, placed)
        self.assertTrue(placed['guest'])
        self.assertTrue(placed['test'])
        self.assertTrue(placed['needs_age_check'])
        self.assertTrue(placed['paymentUrl'].startswith('https://checkout.postfinance.ch/pay/'))
        self.assertEqual(self.gate.body['customerEmailAddress'], 'gina.gast@example.com')
        self.assertEqual(self.gate.body['billingAddress']['postcode'], '3011')
        self.assertEqual(self.gate.body['billingAddress']['familyName'], 'Gast')
        token = parse_qs(urlsplit(self.gate.body['successUrl']).query)['g'][0]
        self.assertEqual(token, placed['guest_token'])
        self.assertIn('g=' + token, self.gate.body['failedUrl'])

        db = connect()
        order = db.execute('select * from orders where id=?', (placed['order_id'],)).fetchone()
        cust = db.execute('select * from customers where id=?', (order['customer_id'],)).fetchone()
        accounts = db.execute('select count(*) from customer_accounts').fetchone()[0]
        notes = [r['body'] for r in db.execute('select body from notes where customer_id=?', (cust['id'],))]
        db.close()
        self.assertEqual(order['channel'], checkout.GUEST_CHANNEL)
        self.assertIsNone(order['customer_account_id'])
        self.assertEqual(order['age_check_status'], checkout.AGE_OPEN)
        self.assertEqual(order['is_test'], 1)
        self.assertEqual(accounts, 0)
        self.assertEqual(cust['email'], 'gina.gast@example.com')
        self.assertEqual(cust['address'], 'Teststrasse 1')
        self.assertIn('Gast', cust['tags'])
        self.assertEqual(bexio_sync._extra_zip(cust), '3011')
        self.assertTrue(any('Gastbestellung' in n for n in notes))
        self.assertTrue(any('Altersprüfung offen' in n for n in notes))

        with open(self.mail_log, encoding='utf-8') as f:
            log = f.read()
        self.assertIn('gina.gast@example.com', log)
        self.assertIn(placed['ref'], log)
        self.assertIn('als Gast bestellt', log)

        c = harness.Client(self.port)
        st, status, text = c.request('GET', '/api/b2b/customer/guest/order?ref=%s&g=%s' % (placed['ref'], token))
        self.assertEqual(st, 200, status)
        self.assertEqual(status['payment_status'], 'offen')
        self.assertNotIn('Teststrasse', text)
        self.assertNotIn('gina.gast', text)
        self.assertNotIn('birthdate', status)
        st, _, _ = c.request('GET', '/api/b2b/customer/guest/order?ref=%s&g=%s' % (placed['ref'], '0' * 32))
        self.assertEqual(st, 404)
        st, _, _ = c.request('GET', '/api/b2b/customer/guest/order?ref=%s' % placed['ref'])
        self.assertEqual(st, 404)

        # Später ein Konto anlegen: gleicher CRM-Kontakt, Bestellung im Konto sichtbar.
        acc = harness.Client(self.port)
        st, reg, _ = acc.request('POST', '/api/b2b/customer/register', json_body={
            'name': 'Gina Gast', 'email': 'gina.gast@example.com', 'password': 'gast-passwort-1',
            'address': 'Teststrasse 1', 'zip': '3011', 'city': 'Bern', 'age_18': True})
        self.assertEqual(st, 201, reg)
        self.assertEqual(reg['customer_id'], cust['id'])
        st, mine, _ = acc.request('GET', '/api/b2b/customer/order?ref=%s' % placed['ref'])
        self.assertEqual(st, 200, mine)

    def test_guest_validation_age_terms_and_minors(self):
        st, data, _ = self.post(_body(guest=dict(GUEST, zip='30', email='kaputt', name='Gina')))
        self.assertEqual(st, 422, data)
        self.assertEqual(data['error'], 'guest_invalid')
        self.assertEqual(set(data['fields']), {'zip', 'email', 'name'})
        st, data, _ = self.post(_body(age_confirmed=False))
        self.assertEqual(data['error'], 'age_confirm_required')
        st, data, _ = self.post(_body(terms_accepted=False))
        self.assertEqual(data['error'], 'terms_required')
        st, data, _ = self.post(_body(birthdate=_birth(-17)))
        self.assertEqual(data['error'], 'underage')
        db = connect()
        self.assertEqual(db.execute('select count(*) from orders').fetchone()[0], 0)
        self.assertEqual(db.execute("select count(*) from customers where email='gina.gast@example.com'").fetchone()[0], 0)
        db.close()
        self.assertEqual(len(self.gate.calls), 0)

    def test_guest_requires_json_and_honeypot_and_rate_limit(self):
        c = harness.Client(self.port)
        st, data, _ = c.request('POST', '/api/b2b/customer/guest/checkout', form={'preview': '1'})
        self.assertEqual(st, 415, data)
        st, data, _ = self.post(_body(website='spam'))
        self.assertEqual(st, 422, data)
        os.environ['CRM_GUEST_LIMIT_PER_EMAIL'] = '2'
        for _ in range(2):
            st, data, _ = self.post(_body())
            self.assertEqual(st, 200, data)
        st, data, _ = self.post(_body())
        self.assertEqual(st, 429, data)

    def test_existing_account_contact_is_not_overwritten(self):
        acc = harness.Client(self.port)
        st, reg, _ = acc.request('POST', '/api/b2b/customer/register', json_body={
            'name': 'Konto Inhaberin', 'email': 'gina.gast@example.com', 'password': 'konto-passwort-1',
            'address': 'Kontoweg 9', 'zip': '3000', 'city': 'Bern', 'age_18': True})
        self.assertEqual(st, 201, reg)
        st, placed, _ = self.post(_body())
        self.assertEqual(st, 200, placed)
        db = connect()
        cust = db.execute('select * from customers where id=?', (reg['customer_id'],)).fetchone()
        order = db.execute('select * from orders where id=?', (placed['order_id'],)).fetchone()
        db.close()
        self.assertEqual(order['customer_id'], reg['customer_id'])
        self.assertIsNone(order['customer_account_id'])
        self.assertEqual(cust['address'], 'Kontoweg 9')
        self.assertEqual(cust['name'], 'Konto Inhaberin')

    def test_logged_in_checkout_unchanged(self):
        c = harness.Client(self.port)
        st, reg, _ = c.request('POST', '/api/b2b/customer/register', json_body={
            'name': 'Anna Beispiel', 'email': 'anna@example.com', 'password': 'kunden-passwort-1',
            'address': 'Fährstrasse 1', 'zip': '3004', 'city': 'Bern', 'age_18': True})
        self.assertEqual(st, 201, reg)
        st, data, _ = c.request('POST', '/api/b2b/customer/checkout', json_body={'items': ITEMS, 'preview': True},
                                headers={'X-CSRF-Token': 'falsch'})
        self.assertEqual(st, 403, data)  # CSRF-Pflicht wie bisher
        st, placed, _ = c.request('POST', '/api/b2b/customer/checkout', json_body=dict(_body(), guest=None),
                                  headers={'X-CSRF-Token': reg['csrf_token']})
        self.assertEqual(st, 200, placed)
        self.assertNotIn('guest', placed)
        self.assertNotIn('g=', self.gate.body['successUrl'])
        db = connect()
        order = db.execute('select channel, customer_account_id from orders where id=?', (placed['order_id'],)).fetchone()
        db.close()
        self.assertEqual(order['channel'], 'website')
        self.assertIsNotNone(order['customer_account_id'])


if __name__ == '__main__':
    unittest.main()
