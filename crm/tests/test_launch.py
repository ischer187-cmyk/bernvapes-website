"""Launch checks: test flag, VAT refusal, SMTP, age notice, legal pages, shop order."""
import base64
import json
import os
import socket
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import harness
import bexio_sync
import mailer
import postfinance
import serve_local
from db import connect

SECRET_B64 = base64.b64encode(b'unit-test-secret-key!!').decode('ascii')


def _birth():
    import datetime
    day = datetime.date.today().replace(year=datetime.date.today().year - 30)
    return day.strftime('%d.%m.%Y')


class _Fake:
    status = 200

    def __init__(self, raw):
        self._raw = raw

    def read(self):
        return self._raw

    def close(self):
        pass


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
            raw = json.dumps({'id': self.tx_id, 'state': 'PENDING', 'merchantReference': self.ref}).encode()
        elif path.endswith('/payment-page-url'):
            raw = json.dumps('https://checkout.postfinance.ch/pay/%s' % self.tx_id).encode()
        elif path.endswith('/api/transaction/read'):
            raw = json.dumps({
                'id': self.tx_id, 'state': self.state, 'merchantReference': self.ref,
            }).encode()
        else:
            raise AssertionError(path)
        return _Fake(raw)


class FlagTests(unittest.TestCase):
    def setUp(self):
        self.tmp = harness.fresh_db()
        self.port = harness.ensure_server()
        postfinance.set_transport(None)
        os.environ['POSTFINANCE_SPACE_ID'] = '102832'
        os.environ['POSTFINANCE_USER_ID'] = '555'
        os.environ['POSTFINANCE_SPACE_KEY'] = SECRET_B64
        os.environ['BEXIO_SYNC_ENABLED'] = '0'

    def tearDown(self):
        postfinance.set_transport(None)
        self.tmp.cleanup()

    def _place(self, mode):
        if mode is None:
            os.environ.pop('POSTFINANCE_MODE', None)
        else:
            os.environ['POSTFINANCE_MODE'] = mode
        gate = Gateway()
        postfinance.set_transport(gate)
        client = harness.Client(self.port)
        st, _, _ = client.request('POST', '/api/b2b/customer/register', json_body={
            'name': 'Lea Muster', 'email': 'lea-%s@example.com' % (mode or 'default'),
            'password': 'kunden-passwort-1', 'address': 'Fährstrasse 29',
            'zip': '3004', 'city': 'Bern', 'age_18': True})
        self.assertEqual(st, 201)
        st, placed, _ = client.request('POST', '/api/b2b/customer/checkout', json_body={
            'items': [{'sku': 'lemon-pie', 'qty': 1}],
            'birthdate': _birth(), 'age_confirmed': True, 'terms_accepted': True})
        self.assertEqual(st, 200, placed)
        db = connect()
        order = db.execute('select is_test from orders where id=?', (placed['order_id'],)).fetchone()
        note = db.execute(
            "select body from notes where channel='website' order by id desc limit 1").fetchone()[0]
        db.close()
        return placed, order['is_test'], note

    def test_default_and_test_mode_mark_the_order_as_test(self):
        self.assertTrue(postfinance.is_test_mode())
        placed, flag, note = self._place(None)
        self.assertEqual(flag, 1)
        self.assertTrue(placed['test'])
        self.assertIn('[TEST]', note)
        placed, flag, note = self._place('test')
        self.assertEqual(flag, 1)
        self.assertTrue(placed['test'])
        self.assertTrue(postfinance.is_test_mode())
        os.environ['POSTFINANCE_MODE'] = 'maybe'
        self.assertTrue(postfinance.is_test_mode())

    def test_live_mode_marks_a_real_order(self):
        placed, flag, note = self._place('live')
        self.assertEqual(flag, 0)
        self.assertFalse(placed['test'])
        self.assertNotIn('[TEST]', note)
        self.assertFalse(postfinance.is_test_mode())


class TaxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = harness.fresh_db()
        bexio_sync.set_transport(None)
        os.environ['BEXIO_SYNC_ENABLED'] = '1'
        os.environ['BEXIO_DELIVERY_ENABLED'] = '0'
        os.environ['BEXIO_API_TOKEN'] = 'bexio-token-do-not-log'
        os.environ['BEXIO_USER_ID'] = '7'
        os.environ.pop('BEXIO_TAX_ID', None)

    def tearDown(self):
        bexio_sync.set_transport(None)
        self.tmp.cleanup()

    def _order(self):
        conn = connect()
        cid = conn.execute(
            """insert into customers(name,email,address,city,customer_type)
               values('Lea Muster','lea-tax@example.com','Fährstrasse 29','Bern','Endkunde')"""
        ).lastrowid
        oid = conn.execute(
            """insert into orders(customer_id,channel,status,total_chf,shipping_chf,external_ref,payment_status,currency)
               values(?,?,?,?,?,?,?,?)""",
            (cid, 'website', 'bezahlt', 21.90, 9, 'bv-tax', 'bezahlt', 'CHF')).lastrowid
        conn.execute(
            'insert into order_items(order_id,article,qty,unit_chf,preorder,sku) values(?,?,?,?,?,?)',
            (oid, 'Lemon Pie', 1, 12.90, 1, 'lemon-pie'))
        conn.commit()
        return conn, oid

    def test_missing_tax_id_refuses_and_logs(self):
        conn, oid = self._order()
        called = []
        bexio_sync.set_transport(lambda req, timeout=30: called.append(req))
        with self.assertLogs('bernvapes.bexio', level='ERROR') as logs:
            result = bexio_sync.sync_paid_order(conn, oid)
        conn.close()
        self.assertEqual(result['status'], 'missing_tax')
        self.assertFalse(result['created'])
        self.assertIn('BEXIO_TAX_ID', result['detail'])
        self.assertIn('abgelehnt', result['detail'])
        self.assertEqual(called, [])
        self.assertTrue(any('BEXIO_TAX_ID' in line for line in logs.output))


class MailTests(unittest.TestCase):
    def tearDown(self):
        os.environ['EMAIL_DRIVER'] = 'log'
        for key in ('SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASS', 'SMTP_FROM', 'SMTP_TLS'):
            os.environ.pop(key, None)

    def test_smtp_server_receives_the_message(self):
        box = {'payload': b''}
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        sock.listen(1)
        port = sock.getsockname()[1]

        def serve():
            conn, _ = sock.accept()
            conn.settimeout(5)
            reader = conn.makefile('rb')
            conn.sendall(b'220 bernvapes test\r\n')
            while True:
                line = reader.readline()
                if not line:
                    break
                cmd = line.split()[0].upper() if line.strip() else b''
                if cmd in (b'EHLO', b'HELO'):
                    conn.sendall(b'250-hello\r\n250 OK\r\n')
                elif cmd == b'DATA':
                    conn.sendall(b'354 go\r\n')
                    chunks = []
                    while True:
                        row = reader.readline()
                        if row in (b'.\r\n', b'.\n', b''):
                            break
                        chunks.append(row)
                    box['payload'] = b''.join(chunks)
                    conn.sendall(b'250 queued\r\n')
                elif cmd == b'QUIT':
                    conn.sendall(b'221 bye\r\n')
                    break
                else:
                    conn.sendall(b'250 OK\r\n')
            conn.close()

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        os.environ['EMAIL_DRIVER'] = 'smtp'
        os.environ['SMTP_HOST'] = '127.0.0.1'
        os.environ['SMTP_PORT'] = str(port)
        os.environ['SMTP_FROM'] = 'shop@bernvapes.ch'
        os.environ['SMTP_TLS'] = '0'
        os.environ.pop('SMTP_USER', None)
        mailer.get_mailer().send('lea@example.com', 'Bernvapes Konto', 'Guten Tag Lea\nFreundliche Grüsse')
        thread.join(5)
        sock.close()
        text = box['payload'].decode('utf-8')
        self.assertIn('shop@bernvapes.ch', text)
        self.assertIn('lea@example.com', text)
        self.assertIn('Bernvapes Konto', text)
        self.assertIn('Freundliche Grüsse', text)
        self.assertNotIn('ß', text)

    def test_starttls_and_login_when_tls_is_on(self):
        os.environ['EMAIL_DRIVER'] = 'smtp'
        os.environ['SMTP_HOST'] = 'smtp.test'
        os.environ['SMTP_PORT'] = '587'
        os.environ['SMTP_FROM'] = 'shop@bernvapes.ch'
        os.environ['SMTP_USER'] = 'shop@bernvapes.ch'
        os.environ['SMTP_PASS'] = 'secret-not-logged'
        os.environ['SMTP_TLS'] = '1'
        with mock.patch('mailer.smtplib.SMTP') as smtp:
            mailer.get_mailer().send('lea@example.com', 'Hi', 'Text')
        smtp.return_value.starttls.assert_called()
        smtp.return_value.login.assert_called_with('shop@bernvapes.ch', 'secret-not-logged')
        smtp.return_value.send_message.assert_called()

    def test_log_driver_stays_the_default(self):
        os.environ['EMAIL_DRIVER'] = 'log'
        self.assertIsInstance(mailer.get_mailer(), mailer.LogMailer)


class PageTests(unittest.TestCase):
    def test_notice_legal_pages_and_no_google_fonts(self):
        hold = mailer.SHIP_NOTICE
        kasse = (ROOT / 'assets/js/kasse.js').read_text(encoding='utf-8')
        self.assertIn(hold, kasse)
        self.assertIn('Zahlungspflichtig bstelle', kasse)
        self.assertIn('terms_accepted', kasse)
        self.assertIn('data-qty', kasse)
        ok = (ROOT / 'kasse-ok.html').read_text(encoding='utf-8')
        self.assertIn('Eingangsbestätigung', ok)
        self.assertIn('Ausweis bereithalten', ok)
        self.assertIn('[BESTELLNUMMER]', ok)
        i18n = (ROOT / 'assets/js/i18n.js').read_text(encoding='utf-8')
        self.assertIn(hold, i18n)
        self.assertIn('Zahlungspflichtig bestellen', i18n)
        self.assertIn('Order with obligation to pay', i18n)
        self.assertIn('Commander avec obligation de payer', i18n)
        self.assertIn('Bist du 18 oder älter?', i18n)
        login = (ROOT / 'assets/js/login.js').read_text(encoding='utf-8')
        self.assertNotIn('Platzhalter', login)
        pages = (
            'index.html', 'werkstatt.html', 'haendler.html', 'kasse.html', 'kasse-ok.html',
            'kasse-fail.html', 'konto.html', 'impressum.html', 'datenschutz.html', 'agb.html',
        )
        for name in pages:
            text = (ROOT / name).read_text(encoding='utf-8')
            self.assertIn('href="impressum.html"', text, name)
            self.assertIn('href="datenschutz.html"', text, name)
            self.assertIn('href="agb.html"', text, name)
            self.assertNotIn('fonts.googleapis.com', text, name)
            self.assertNotIn('fonts.gstatic.com', text, name)
        for name in ('impressum.html', 'datenschutz.html', 'agb.html'):
            text = (ROOT / name).read_text(encoding='utf-8')
            self.assertIn('class="gap"', text, name)
            self.assertIn('[DATUM DER AUFSCHALTUNG]', text, name)
        impressum = (ROOT / 'impressum.html').read_text(encoding='utf-8')
        self.assertIn('dominic@bernvapes.ch', impressum)
        self.assertIn('Kontrast Kompositions GmbH', impressum)
        self.assertIn('CHE-235.690.038', impressum)
        self.assertIn('Dominic Ischer', impressum)
        agb = (ROOT / 'agb.html').read_text(encoding='utf-8')
        self.assertIn('TabPG', agb)
        self.assertIn('Art. 23 TabPG', agb)
        self.assertIn('Gerichtsstand ist Bern', agb)
        self.assertIn('Zahlungspflichtig bestellen', agb)
        self.assertIn('Videoanruf', agb)
        privacy = (ROOT / 'datenschutz.html').read_text(encoding='utf-8')
        self.assertIn('DSG', privacy)
        self.assertIn('PostFinance Checkout', privacy)
        self.assertIn('bexio', privacy)
        self.assertIn('keine Verbindung zu Google', privacy)
        self.assertIn('Art. 23 TabPG', (ROOT / 'index.html').read_text(encoding='utf-8'))
        example = (ROOT / 'crm/.env.example').read_text(encoding='utf-8')
        self.assertIn('BEXIO_TAX_ID=44', example)
        self.assertIn('POSTFINANCE_MODE=test', example)
        self.assertIn('SMTP_HOST', example)
        self.assertNotIn('ß', hold)


class WebsiteOrderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = harness.fresh_db()
        self.crm = harness.ensure_server()
        os.environ['POSTFINANCE_MODE'] = 'test'
        os.environ['POSTFINANCE_SPACE_ID'] = '102832'
        os.environ['POSTFINANCE_USER_ID'] = '555'
        os.environ['POSTFINANCE_SPACE_KEY'] = SECRET_B64
        os.environ['BEXIO_SYNC_ENABLED'] = '1'
        os.environ['BEXIO_DELIVERY_ENABLED'] = '0'
        os.environ['BEXIO_API_TOKEN'] = 'bexio-token-do-not-log'
        os.environ['BEXIO_USER_ID'] = '7'
        os.environ['BEXIO_TAX_ID'] = '44'
        os.environ['EMAIL_DRIVER'] = 'log'
        serve_local.UPSTREAM = 'http://127.0.0.1:%s' % self.crm
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), serve_local.H)
        self.web = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.gate = Gateway()
        postfinance.set_transport(self.gate)
        self.bexio_calls = []

        def bexio(req, timeout=30):
            self.bexio_calls.append(req)
            path = urlsplit(req.full_url).path
            if path.endswith('/2.0/contact/search'):
                return _Fake(b'[]')
            if path.endswith('/2.0/contact'):
                return _Fake(b'{"id": 77}')
            if path.endswith('/2.0/kb_order'):
                return _Fake(b'{"id": 61, "document_nr": "AU-00061"}')
            if path.endswith('/invoice'):
                return _Fake(b'{"id": 88}')
            raise AssertionError(path)

        bexio_sync.set_transport(bexio)
        bexio_sync.set_mail_transport(None)

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        postfinance.set_transport(None)
        bexio_sync.set_transport(None)
        bexio_sync.set_mail_transport(None)
        self.tmp.cleanup()

    def test_shop_checkout_creates_order_then_invoice_with_vat(self):
        client = harness.Client(self.web)
        st, reg, _ = client.request('POST', '/b2b-api/customer/register', json_body={
            'name': 'Lea Muster', 'email': 'lea-e2e@example.com', 'password': 'kunden-passwort-1',
            'address': 'Fährstrasse 29', 'zip': '3004', 'city': 'Bern', 'age_18': True})
        self.assertEqual(st, 201, reg)
        st, preview, _ = client.request('POST', '/b2b-api/customer/checkout', json_body={
            'items': [{'sku': 'lemon-pie', 'qty': 1}], 'preview': True})
        self.assertEqual(st, 200, preview)
        self.assertIn(mailer.SHIP_NOTICE, preview['notices'])
        st, placed, _ = client.request('POST', '/b2b-api/customer/checkout', json_body={
            'items': [{'sku': 'lemon-pie', 'qty': 1}],
            'birthdate': _birth(), 'age_confirmed': True, 'terms_accepted': True})
        self.assertEqual(st, 200, placed)
        self.assertTrue(placed['test'])
        self.assertIn(mailer.SHIP_NOTICE, placed['notices'])
        self.gate.state = 'FULFILL'
        st, paid, text = client.request('POST', '/webhook/postfinance', json_body={
            'eventId': 'pf-e2e', 'entityId': 4242, 'listenerEntityTechnicalName': 'Transaction',
            'spaceId': 102832})
        self.assertEqual(st, 200, paid)
        self.assertEqual(paid['status'], 'paid')
        self.assertEqual(paid['bexio']['status'], 'created')
        self.assertNotIn('bexio-token-do-not-log', text)
        paths = [urlsplit(req.full_url).path for req in self.bexio_calls]
        self.assertEqual(paths, [
            '/2.0/contact/search',
            '/2.0/contact',
            '/2.0/kb_order',
            '/2.0/kb_order/61/invoice',
        ])
        contact = json.loads(self.bexio_calls[1].data.decode('utf-8'))
        self.assertEqual(contact['street_name'], 'Fährstrasse')
        self.assertEqual(contact['house_number'], '29')
        self.assertEqual(contact['postcode'], '3004')
        self.assertEqual(contact['city'], 'Bern')
        self.assertEqual(contact['mail'], 'lea-e2e@example.com')
        self.assertEqual(contact['name_2'], 'Lea')
        self.assertEqual(contact['name_1'], 'Muster')
        order = json.loads(self.bexio_calls[2].data.decode('utf-8'))
        self.assertEqual(order['mwst_type'], 0)
        self.assertFalse(order['mwst_is_net'])
        self.assertTrue(order['positions'])
        self.assertTrue(all(row.get('tax_id') == 44 for row in order['positions']))
        db = connect()
        row = db.execute('select is_test,bexio_kb_order_id,bexio_order_id from orders where id=?', (placed['order_id'],)).fetchone()
        mail = db.execute(
            "select subject,body from mail_log where to_addr=? order by id desc limit 1",
            ('lea-e2e@example.com',)).fetchone()
        db.close()
        self.assertEqual(row['is_test'], 1)
        self.assertEqual(row['bexio_kb_order_id'], 61)
        self.assertEqual(row['bexio_order_id'], 88)
        self.assertIn(placed['ref'], mail['subject'])
        self.assertIn(mailer.SHIP_NOTICE, mail['body'])
        self.assertIn('Eingangsbestätigung', mail['body'])
        self.assertIn('Ausweis bereithalten', mail['body'])
        self.assertIn('Fährstrasse 29', mail['body'])


if __name__ == '__main__':
    unittest.main()
