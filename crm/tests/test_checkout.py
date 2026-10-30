"""PostFinance MAC, User-Agent, and the shop order flow. No live call, no space key in assertions' messages."""
import base64, datetime, hashlib, hmac, json, os, threading, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import harness
import bexio_sync
import checkout
import postfinance
import shipping
from db import connect


def _birth(years=-30, days=0):
    day = datetime.date.today()
    try:
        day = day.replace(year=day.year + years)
    except ValueError:
        day = day.replace(year=day.year + years, day=28)
    return (day + datetime.timedelta(days=days)).strftime('%d.%m.%Y')


def _checkout_body(items, **extra):
    body = {'items': items, 'birthdate': _birth(-30), 'age_confirmed': True}
    body.update(extra)
    return body

SECRET_RAW = b'unit-test-secret-key!!'
SECRET_B64 = base64.b64encode(SECRET_RAW).decode('ascii')


def _mac(method, path, user, ts, secret=SECRET_RAW):
    msg = '1|%s|%s|%s|%s' % (user, ts, method.upper(), path)
    return base64.b64encode(hmac.new(secret, msg.encode('utf-8'), hashlib.sha512).digest()).decode('ascii')


class MacTests(unittest.TestCase):
    def tearDown(self):
        postfinance.set_transport(None)

    def test_signature_uses_decoded_secret(self):
        path = '/api/transaction/create?spaceId=102832'
        headers = postfinance.mac_headers('post', path, '555', SECRET_B64, 1700000000)
        self.assertEqual(headers['x-mac-version'], '1')
        self.assertEqual(headers['x-mac-userid'], '555')
        self.assertEqual(headers['x-mac-timestamp'], '1700000000')
        self.assertEqual(headers['x-mac-value'], _mac('POST', path, '555', 1700000000))
        raw_key = base64.b64encode(hmac.new(SECRET_B64.encode('ascii'), b'1|555|1700000000|POST|' + path.encode(), hashlib.sha512).digest()).decode()
        self.assertNotEqual(headers['x-mac-value'], raw_key)
        self.assertNotIn(SECRET_B64, headers['x-mac-value'])

    def test_user_agent_on_verified_space_and_method_search(self):
        seen = []

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self._cap('GET'))
                body = b'{"id":102832,"name":"test"}'
                self._send(body)

            def do_POST(self):
                n = int(self.headers.get('Content-Length') or 0)
                self.rfile.read(n)
                seen.append(self._cap('POST'))
                self._send(b'[]')

            def _cap(self, method):
                uas = [v for k, v in self.headers.items() if k.lower() == 'user-agent']
                return {
                    'method': method,
                    'path': self.path,
                    'ua': self.headers.get('User-Agent'),
                    'uas': uas,
                    'version': self.headers.get('x-mac-version'),
                    'user': self.headers.get('x-mac-userid'),
                    'ts': self.headers.get('x-mac-timestamp'),
                    'mac': self.headers.get('x-mac-value'),
                    'blob': ' '.join('%s:%s' % (k, v) for k, v in self.headers.items()),
                }

            def _send(self, body):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        httpd = ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        os.environ['POSTFINANCE_API_BASE'] = 'http://127.0.0.1:%s' % httpd.server_address[1]
        os.environ['POSTFINANCE_SPACE_ID'] = '102832'
        os.environ['POSTFINANCE_USER_ID'] = '555'
        os.environ['POSTFINANCE_SPACE_KEY'] = SECRET_B64
        try:
            space = postfinance.read_space()
            methods = postfinance.search_payment_methods()
        finally:
            httpd.shutdown()
            httpd.server_close()
            postfinance.set_transport(None)
        self.assertEqual(space['id'], 102832)
        self.assertEqual(methods, [])
        self.assertEqual([c['path'] for c in seen], [
            '/api/space/read?spaceId=102832',
            '/api/payment-method-configuration/search?spaceId=102832',
        ])
        for cap in seen:
            self.assertEqual(cap['ua'], 'bernvapes-crm/1.0')
            self.assertEqual(cap['uas'], ['bernvapes-crm/1.0'])
            self.assertNotIn('Python-urllib', cap['blob'])
            self.assertNotIn(SECRET_B64, cap['blob'])
            self.assertEqual(cap['version'], '1')
            self.assertEqual(cap['user'], '555')
            self.assertEqual(cap['mac'], _mac(cap['method'], cap['path'], cap['user'], cap['ts']))


class Gateway:
    def __init__(self):
        self.calls = []
        self.ref = None
        self.body = None
        self.state = 'PENDING'
        self.tx_id = 4242

    def __call__(self, req, timeout=30):
        self.calls.append(req)
        path = urlsplit(req.full_url).path
        if path.endswith('/api/transaction/create'):
            self.body = json.loads(req.data.decode('utf-8'))
            self.ref = self.body['merchantReference']
            raw = json.dumps({'id': self.tx_id, 'state': 'PENDING', 'merchantReference': self.ref}).encode('utf-8')
        elif path.endswith('/payment-page-url'):
            raw = json.dumps('https://checkout.postfinance.ch/pay/%s' % self.tx_id).encode('utf-8')
        elif path.endswith('/api/transaction/read'):
            raw = json.dumps({
                'id': self.tx_id, 'state': self.state, 'merchantReference': self.ref, 'currency': 'CHF',
            }).encode('utf-8')
        else:
            raise AssertionError(path)
        return _Fake(raw)


class _Fake:
    status = 200

    def __init__(self, raw):
        self._raw = raw

    def read(self):
        return self._raw

    def close(self):
        pass


def _uas(req):
    return [v for k, v in req.header_items() if k.lower() == 'user-agent']


class OrderFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = harness.fresh_db()
        self.port = harness.ensure_server()
        postfinance.set_transport(None)
        bexio_sync.set_transport(None)
        os.environ['BEXIO_SYNC_ENABLED'] = '0'
        os.environ['BEXIO_API_TOKEN'] = 'bexio-token-do-not-log'
        os.environ.pop('POSTFINANCE_SPACE_ID', None)
        os.environ.pop('POSTFINANCE_USER_ID', None)
        os.environ.pop('POSTFINANCE_SPACE_KEY', None)

    def tearDown(self):
        postfinance.set_transport(None)
        bexio_sync.set_transport(None)
        self.tmp.cleanup()

    def _customer(self):
        c = harness.Client(self.port)
        st, data, _ = c.request('POST', '/api/b2b/customer/register', json_body={
            'name': 'Anna Beispiel', 'email': 'anna-kasse@example.com', 'password': 'kunden-passwort-1',
            'address': 'Fährstrasse 1', 'zip': '3004', 'city': 'Bern', 'age_18': True})
        self.assertEqual(st, 201, data)
        return c

    def test_checkout_webhook_marks_paid_and_keeps_preorder(self):
        client = self._customer()
        items = [
            {'id': 'lemon-pie', 'name': 'Lemon Pie', 'qty': 2, 'preorder': True, 'unit_chf': 0.01},
            {'id': 'gipfel_adler_100ml', 'name': 'Gipfel Adler', 'qty': 1, 'preorder': True, 'unit_chf': 0.01},
            {'sku': 'mango-lassi', 'name': 'Mango Lassi', 'qty': 1},
            {'sku': 'mandarine-nuss', 'qty': 1},
            {'sku': 'apple-pie', 'qty': 1},
        ]
        called = []

        def boom(req, timeout=30):
            called.append(req)
            raise AssertionError('network')

        postfinance.set_transport(boom)
        st, data, _ = client.request('POST', '/api/b2b/customer/checkout', json_body={'items': items})
        self.assertEqual(st, 503, data)
        self.assertEqual(data['error'], 'postfinance_not_configured')
        self.assertEqual(called, [])

        os.environ['POSTFINANCE_SPACE_ID'] = '102832'
        os.environ['POSTFINANCE_USER_ID'] = '555'
        os.environ['POSTFINANCE_SPACE_KEY'] = SECRET_B64
        postfinance.set_transport(boom)
        st, preview, _ = client.request('POST', '/api/b2b/customer/checkout', json_body={'items': items, 'preview': True})
        self.assertEqual(st, 200, preview)
        self.assertEqual(called, [])
        by_sku = {row['sku']: row for row in preview['items']}
        for sku in ('lemon-pie', 'mango-lassi', 'mandarine-nuss', 'apple-pie'):
            self.assertTrue(by_sku[sku]['preorder'], sku)
        self.assertFalse(by_sku['gipfel-adler']['preorder'])
        self.assertAlmostEqual(by_sku['lemon-pie']['unit_chf'], 12.90, places=2)
        self.assertNotEqual(by_sku['lemon-pie']['unit_chf'], 0.01)

        gate = Gateway()
        postfinance.set_transport(gate)
        st, placed, _ = client.request('POST', '/api/b2b/customer/checkout', json_body=_checkout_body(items))
        self.assertEqual(st, 200, placed)
        self.assertEqual(placed['integrationMode'], 'PaymentPage')
        self.assertTrue(placed['paymentUrl'].startswith('https://checkout.postfinance.ch/pay/'))
        self.assertTrue(placed['test'])
        paths = [urlsplit(req.full_url).path for req in gate.calls]
        self.assertIn('/api/transaction/create', paths[0])
        self.assertIn('payment-page-url', paths[1])
        self.assertNotIn('lightbox', ' '.join(paths))
        self.assertNotIn('iframe', ' '.join(paths))
        for req in gate.calls:
            self.assertEqual(_uas(req), ['bernvapes-crm/1.0'])
            blob = ' '.join('%s:%s' % pair for pair in req.header_items())
            self.assertNotIn('Python-urllib', blob)
            self.assertNotIn(SECRET_B64, req.full_url)
            self.assertNotIn(SECRET_B64, blob)
            path = urlsplit(req.full_url).path
            query = urlsplit(req.full_url).query
            signed = path + ('?' + query if query else '')
            ts = dict(req.header_items())
            # header spelling is preserved by MacRequest
            mac = None
            user = None
            stamp = None
            for key, val in req.header_items():
                if key.lower() == 'x-mac-value':
                    mac = val
                elif key.lower() == 'x-mac-userid':
                    user = val
                elif key.lower() == 'x-mac-timestamp':
                    stamp = val
            self.assertEqual(mac, _mac(req.get_method(), signed, user, stamp))
        body = gate.body
        self.assertEqual(body['successUrl'].split('?')[0].endswith('kasse-ok.html'), True)
        self.assertIn('kasse-fail.html', body['failedUrl'])
        lemon = next(i for i in body['lineItems'] if i['sku'] == 'lemon-pie')
        self.assertIn('Vorbestellung', lemon['name'])
        self.assertEqual(lemon['type'], 'PRODUCT')
        self.assertAlmostEqual(lemon['amountIncludingTax'], 25.80, places=2)
        adler = next(i for i in body['lineItems'] if i['sku'] == 'gipfel-adler')
        self.assertNotIn('Vorbestellung', adler['name'])
        self.assertEqual(body['metaData']['integrationMode'], 'PaymentPage')
        self.assertEqual(body['billingAddress']['postcode'], '3004')

        db = connect()
        order = db.execute('select * from orders where id=?', (placed['order_id'],)).fetchone()
        cust = db.execute('select id from customers where email=?', ('anna-kasse@example.com',)).fetchone()
        self.assertEqual(order['customer_id'], cust['id'])
        self.assertEqual(order['payment_status'], 'offen')
        self.assertEqual(order['postfinance_tx_id'], '4242')
        self.assertEqual(order['is_test'], 1)
        self.assertEqual(order['external_ref'], placed['ref'])
        flags = {r['article']: r['preorder'] for r in db.execute(
            'select article,preorder from order_items where order_id=?', (order['id'],))}
        db.close()
        self.assertEqual(flags['Lemon Pie'], 1)
        self.assertEqual(flags['Gipfel Adler'], 0)

        gate.state = 'PENDING'
        st, pending, _ = client.request('POST', '/webhook/postfinance', json_body={
            'eventId': 'pf-pending', 'entityId': 4242, 'listenerEntityTechnicalName': 'Transaction',
            'spaceId': 102832, 'state': 'FULFILL'})
        self.assertEqual(st, 200, pending)
        self.assertEqual(pending['status'], 'pending')
        db = connect()
        self.assertEqual(db.execute('select payment_status from orders where id=?', (order['id'],)).fetchone()[0], 'offen')
        db.close()

        gate.state = 'FULFILL'
        st, paid, text = client.request('POST', '/webhook/postfinance', json_body={
            'eventId': 'pf-paid', 'entityId': 4242, 'listenerEntityTechnicalName': 'Transaction',
            'spaceId': '102832'})
        self.assertEqual(st, 200, paid)
        self.assertEqual(paid['status'], 'paid')
        self.assertEqual(paid['bexio']['status'], 'disabled')
        self.assertFalse(paid['bexio']['created'])
        self.assertNotIn('bexio-token-do-not-log', text)
        db = connect()
        paid_row = db.execute('select payment_status,status,customer_id,bexio_order_id from orders where id=?', (order['id'],)).fetchone()
        note = db.execute("select body from notes where customer_id=? and body like '%bexio%'", (cust['id'],)).fetchone()[0]
        db.close()
        self.assertEqual(paid_row['payment_status'], 'bezahlt')
        self.assertEqual(paid_row['status'], 'bezahlt')
        self.assertEqual(paid_row['customer_id'], cust['id'])
        self.assertIsNone(paid_row['bexio_order_id'])
        self.assertIn('BEXIO_SYNC_ENABLED is off', note)
        self.assertNotIn('bexio-token-do-not-log', note)

        st, dup, _ = client.request('POST', '/webhook/postfinance', json_body={
            'eventId': 'pf-paid', 'entityId': 4242, 'spaceId': 102832})
        self.assertEqual(st, 200, dup)
        self.assertEqual(dup['status'], 'duplicate')

        st, mine, _ = client.request('GET', '/api/b2b/customer/order?ref=%s' % placed['ref'])
        self.assertEqual(st, 200, mine)
        self.assertEqual(mine['payment_status'], 'bezahlt')
        self.assertTrue(any(i['preorder'] and i['name'] == 'Lemon Pie' for i in mine['items']))

    def test_bexio_sync_on_creates_contact_and_invoice_once(self):
        client = self._customer()
        os.environ['POSTFINANCE_SPACE_ID'] = '102832'
        os.environ['POSTFINANCE_USER_ID'] = '555'
        os.environ['POSTFINANCE_SPACE_KEY'] = SECRET_B64
        os.environ['BEXIO_SYNC_ENABLED'] = '1'
        os.environ['BEXIO_API_TOKEN'] = 'bexio-token-do-not-log'
        os.environ['BEXIO_USER_ID'] = '7'
        gate = Gateway()
        postfinance.set_transport(gate)
        st, placed, _ = client.request('POST', '/api/b2b/customer/checkout', json_body=_checkout_body([
            {'sku': 'lemon-pie', 'qty': 1}]))
        self.assertEqual(st, 200, placed)
        bexio_calls = []

        def bexio(req, timeout=30):
            bexio_calls.append(req)
            path = urlsplit(req.full_url).path
            auth = dict((k.lower(), v) for k, v in req.header_items()).get('authorization')
            self.assertEqual(auth, 'Bearer bexio-token-do-not-log')
            if path.endswith('/2.0/contact'):
                return _Fake(b'{"id": 77}')
            if path.endswith('/2.0/kb_invoice'):
                payload = json.loads(req.data.decode('utf-8'))
                self.assertIn('Vorbestellung', payload['positions'][0]['text'])
                self.assertEqual(payload['api_reference'], placed['ref'])
                return _Fake(b'{"id": 88}')
            raise AssertionError(path)

        bexio_sync.set_transport(bexio)
        gate.state = 'FULFILL'
        st, paid, text = client.request('POST', '/webhook/postfinance', json_body={
            'eventId': 'pf-bexio', 'entityId': 4242, 'spaceId': 102832})
        self.assertEqual(st, 200, paid)
        self.assertEqual(paid['bexio']['status'], 'created')
        self.assertTrue(paid['bexio']['created'])
        self.assertNotIn('bexio-token-do-not-log', text)
        self.assertEqual(len(bexio_calls), 2)
        db = connect()
        cid = db.execute("select id from customers where email='anna-kasse@example.com'").fetchone()[0]
        self.assertEqual(db.execute('select bexio_contact_id from customers where id=?', (cid,)).fetchone()[0], 77)
        self.assertEqual(db.execute('select bexio_order_id from orders where id=?', (placed['order_id'],)).fetchone()[0], 88)
        note = db.execute("select body from notes where customer_id=? and body like '%bexio%'", (cid,)).fetchone()[0]
        db.close()
        self.assertNotIn('bexio-token-do-not-log', note)
        st, dup, _ = client.request('POST', '/webhook/postfinance', json_body={
            'eventId': 'pf-bexio', 'entityId': 4242, 'spaceId': 102832})
        self.assertEqual(dup['status'], 'duplicate')
        self.assertEqual(len(bexio_calls), 2)

    def _configured(self):
        os.environ['POSTFINANCE_SPACE_ID'] = '102832'
        os.environ['POSTFINANCE_USER_ID'] = '555'
        os.environ['POSTFINANCE_SPACE_KEY'] = SECRET_B64

    def _line_sum(self, body):
        return round(sum(float(row['amountIncludingTax']) for row in body['lineItems']), 2)

    def test_shipping_below_at_and_above_threshold(self):
        self.assertEqual(shipping.SHIPPING_FEE_CHF, 9.0)
        self.assertEqual(shipping.FREE_SHIPPING_THRESHOLD_CHF, 50.0)
        self.assertAlmostEqual(shipping.VAT_RATE, 8.1, places=2)
        raw = shipping.CONFIG.read_text(encoding='utf-8')
        self.assertIn('SHIPPING_FEE_CHF: 9.00', raw)
        self.assertIn('FREE_SHIPPING_THRESHOLD_CHF: 50.00', raw)
        self.assertEqual(shipping.shipping_for(49.99), 9.0)
        self.assertEqual(shipping.shipping_for(50), 0.0)
        self.assertEqual(shipping.shipping_for(50.01), 0.0)

        client = self._customer()
        st, cat, _ = client.request('GET', '/api/b2b/customer/catalog')
        self.assertEqual(st, 200, cat)
        self.assertAlmostEqual(cat['shipping_fee_chf'], 9, places=2)
        self.assertAlmostEqual(cat['free_shipping_threshold_chf'], 50, places=2)
        self.assertAlmostEqual(cat['vat_rate'], 8.1, places=2)

        self._configured()
        gate = Gateway()
        postfinance.set_transport(gate)

        def place(items, **extra):
            st, placed, _ = client.request(
                'POST', '/api/b2b/customer/checkout', json_body=_checkout_body(items, **extra))
            self.assertEqual(st, 200, placed)
            self.assertAlmostEqual(self._line_sum(gate.body), placed['total_chf'], places=2)
            db = connect()
            row = db.execute(
                'select total_chf,shipping_chf from orders where id=?', (placed['order_id'],)).fetchone()
            db.close()
            self.assertAlmostEqual(row['total_chf'], placed['total_chf'], places=2)
            self.assertAlmostEqual(row['shipping_chf'], placed['shipping_chf'], places=2)
            goods = round(sum(i['amountIncludingTax'] for i in gate.body['lineItems'] if i['type'] == 'PRODUCT'), 2)
            self.assertAlmostEqual(round(goods + row['shipping_chf'], 2), row['total_chf'], places=2)
            return placed

        low = place([{'sku': 'lemon-pie', 'qty': 1, 'shipping_chf': 0, 'total_chf': 1}])
        self.assertAlmostEqual(low['subtotal_chf'], 12.90, places=2)
        self.assertAlmostEqual(low['shipping_chf'], 9, places=2)
        self.assertAlmostEqual(low['total_chf'], 21.90, places=2)
        self.assertFalse(low['free_shipping'])
        self.assertAlmostEqual(low['remaining_to_free_chf'], 37.10, places=2)
        versand = next(i for i in gate.body['lineItems'] if i['name'] == 'Versand')
        self.assertEqual(versand['type'], 'SHIPPING')
        self.assertEqual(versand['sku'], 'versand')
        self.assertAlmostEqual(versand['amountIncludingTax'], 9, places=2)
        self.assertAlmostEqual(versand['aggregatedTaxRate'], 8.1, places=2)
        lemon = next(i for i in gate.body['lineItems'] if i['sku'] == 'lemon-pie')
        self.assertAlmostEqual(lemon['aggregatedTaxRate'], versand['aggregatedTaxRate'], places=2)

        os.environ['BEXIO_SYNC_ENABLED'] = '1'
        os.environ['BEXIO_API_TOKEN'] = 'bexio-token-do-not-log'
        os.environ['BEXIO_USER_ID'] = '7'
        os.environ['BEXIO_TAX_ID'] = '19'
        invoices = []

        def bexio(req, timeout=30):
            path = urlsplit(req.full_url).path
            if path.endswith('/2.0/contact'):
                return _Fake(b'{"id": 77}')
            if path.endswith('/2.0/kb_invoice'):
                invoices.append(json.loads(req.data.decode('utf-8')))
                return _Fake(json.dumps({'id': 90 + len(invoices)}).encode('utf-8'))
            raise AssertionError(path)

        bexio_sync.set_transport(bexio)
        conn = connect()
        synced = bexio_sync.sync_paid_order(conn, low['order_id'])
        conn.close()
        self.assertEqual(synced['status'], 'created')
        positions = invoices[-1]['positions']
        self.assertEqual(positions[-1]['text'], 'Versand')
        self.assertEqual(positions[-1]['unit_price'], '9.00')
        self.assertEqual(positions[-1]['tax_id'], positions[0]['tax_id'])
        self.assertFalse(invoices[-1]['mwst_is_net'])
        billed = round(sum(float(p['amount']) * float(p['unit_price']) for p in positions), 2)
        self.assertAlmostEqual(billed, low['total_chf'], places=2)

        db = connect()
        db.execute('update products set price_einstieg=? where sku=?', (50, 'lemon-pie'))
        db.commit()
        db.close()
        exact = place([{'sku': 'lemon-pie', 'qty': 1, 'shipping_chf': 99}])
        self.assertAlmostEqual(exact['subtotal_chf'], 50, places=2)
        self.assertEqual(exact['shipping_chf'], 0)
        self.assertTrue(exact['free_shipping'])
        self.assertEqual(exact['remaining_to_free_chf'], 0)
        self.assertFalse(any(i.get('type') == 'SHIPPING' for i in gate.body['lineItems']))
        conn = connect()
        bexio_sync.sync_paid_order(conn, exact['order_id'])
        conn.close()
        free_ship = invoices[-1]['positions'][-1]
        self.assertEqual(free_ship['text'], 'Versand')
        self.assertEqual(free_ship['unit_price'], '0.00')
        self.assertAlmostEqual(
            round(sum(float(p['amount']) * float(p['unit_price']) for p in invoices[-1]['positions']), 2),
            exact['total_chf'], places=2)

        above = place([{'sku': 'lemon-pie', 'qty': 2}])
        self.assertAlmostEqual(above['subtotal_chf'], 100, places=2)
        self.assertEqual(above['shipping_chf'], 0)
        self.assertTrue(above['free_shipping'])
        self.assertAlmostEqual(self._line_sum(gate.body), 100, places=2)

    def test_age_check_rejects_minors_and_blocks_new_customers(self):
        client = self._customer()
        self._configured()
        gate = Gateway()
        postfinance.set_transport(gate)
        calls = len(gate.calls)
        db = connect()
        before = db.execute('select count(*) from orders').fetchone()[0]
        db.close()

        st, minor, _ = client.request('POST', '/api/b2b/customer/checkout', json_body={
            'items': [{'sku': 'lemon-pie', 'qty': 1}],
            'birthdate': _birth(-18, 1), 'age_confirmed': True})
        self.assertEqual(st, 422, minor)
        self.assertEqual(minor['error'], 'underage')
        self.assertEqual(minor['message'], 'Du musst mindestens 18 Jahre alt sein.')
        self.assertEqual(len(gate.calls), calls)

        st, bare, _ = client.request('POST', '/api/b2b/customer/checkout', json_body={
            'items': [{'sku': 'lemon-pie', 'qty': 1}], 'birthdate': _birth(-30)})
        self.assertEqual(st, 422, bare)
        self.assertEqual(bare['error'], 'age_confirm_required')
        self.assertIn('18', bare['message'])

        st, bad, _ = client.request('POST', '/api/b2b/customer/checkout', json_body={
            'items': [{'sku': 'lemon-pie', 'qty': 1}],
            'birthdate': '31.02.2000', 'age_confirmed': True})
        self.assertEqual(st, 422, bad)
        self.assertEqual(bad['error'], 'birthdate_invalid')

        st, preview, _ = client.request('POST', '/api/b2b/customer/checkout', json_body={
            'items': [{'sku': 'lemon-pie', 'qty': 1}], 'preview': True})
        self.assertEqual(st, 200, preview)
        self.assertIn(checkout.NOTICE_ALL, preview['notices'])
        self.assertIn(checkout.NOTICE_NEW, preview['notices'])
        self.assertTrue(preview['needs_age_check'])

        born = _birth(-18)
        st, placed, _ = client.request('POST', '/api/b2b/customer/checkout', json_body={
            'items': [{'sku': 'lemon-pie', 'qty': 1}], 'birthdate': born, 'age_confirmed': True})
        self.assertEqual(st, 200, placed)
        self.assertEqual(placed['age_check_status'], 'Altersprüfung offen')
        self.assertIn(checkout.NOTICE_NEW, placed['notices'])
        self.assertIn(checkout.NOTICE_ALL, placed['notices'])
        db = connect()
        cust = db.execute(
            "select id,age_verified,birthdate from customers where email='anna-kasse@example.com'").fetchone()
        order = db.execute(
            'select status,age_check_status,birthdate from orders where id=?', (placed['order_id'],)).fetchone()
        after = db.execute('select count(*) from orders').fetchone()[0]
        db.close()
        self.assertEqual(cust['age_verified'], 0)
        self.assertEqual(cust['birthdate'], born)
        self.assertEqual(order['birthdate'], born)
        self.assertEqual(order['status'], 'offen')
        self.assertEqual(order['age_check_status'], 'Altersprüfung offen')
        self.assertEqual(after, before + 1)
        st, mine, _ = client.request('GET', '/api/b2b/customer/order?ref=%s' % placed['ref'])
        self.assertEqual(st, 200, mine)
        self.assertIn(checkout.NOTICE_NEW, mine['notices'])
        self.assertIn('Selfie mit deinem Ausweis', ' '.join(mine['notices']))

        admin = harness.admin_login(self.port)
        st, _, html = admin.request('GET', '/bestellung/%s' % placed['order_id'])
        self.assertEqual(st, 200)
        self.assertIn('Altersprüfung offen', html)
        self.assertIn('Versand gesperrt', html)
        self.assertIn('als verifiziert markieren', html)
        self.assertNotIn('type="file"', html)
        self.assertNotIn('type=file', html)
        st, _, _ = admin.request('POST', '/bestellung/%s/aktion' % placed['order_id'], form={'a': 'versendet'})
        self.assertEqual(st, 303)
        db = connect()
        self.assertEqual(db.execute('select status from orders where id=?', (placed['order_id'],)).fetchone()[0], 'offen')
        db.close()

        st, _, _ = admin.request('POST', '/kontakt/%s/alter' % cust['id'], form={'a': 'verifiziert'})
        self.assertEqual(st, 303)
        db = connect()
        marked = db.execute('select age_verified,age_verified_at,age_verify_method from customers where id=?', (cust['id'],)).fetchone()
        opened = db.execute('select age_check_status from orders where id=?', (placed['order_id'],)).fetchone()[0]
        note = db.execute(
            "select body from notes where customer_id=? and author='CRM' order by id desc limit 1", (cust['id'],)).fetchone()[0]
        db.close()
        self.assertEqual(marked['age_verified'], 1)
        self.assertTrue(marked['age_verified_at'])
        self.assertEqual(marked['age_verify_method'], 'manuell')
        self.assertEqual(opened, 'verifiziert')
        self.assertIn('Keine Ausweisbilder', note)

        st, again, _ = client.request('POST', '/api/b2b/customer/checkout', json_body={
            'items': [{'sku': 'lemon-pie', 'qty': 1}], 'birthdate': born, 'age_confirmed': True})
        self.assertEqual(st, 200, again)
        self.assertNotEqual(again['age_check_status'], 'Altersprüfung offen')
        self.assertNotIn(checkout.NOTICE_NEW, again['notices'])
        self.assertIn(checkout.NOTICE_ALL, again['notices'])

        st, _, _ = admin.request('POST', '/bestellung/%s/aktion' % placed['order_id'], form={'a': 'versendet'})
        self.assertEqual(st, 303)
        db = connect()
        self.assertEqual(db.execute('select status from orders where id=?', (placed['order_id'],)).fetchone()[0], 'versendet')
        db.close()


if __name__ == '__main__':
    unittest.main()
