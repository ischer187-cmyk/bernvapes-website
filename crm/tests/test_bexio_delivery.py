"""Lieferschein nach kb_order. Kein SMTP, kein echtes bexio."""
import base64, json, os, unittest
from urllib.parse import urlsplit

import harness
import bexio_sync
from db import connect


class _Fake:
    status = 200

    def __init__(self, raw):
        self._raw = raw

    def read(self):
        return self._raw

    def close(self):
        pass


class _Err:
    def __init__(self, code, raw):
        self.status = code
        self._raw = raw.encode('utf-8')

    def read(self):
        return self._raw

    def close(self):
        pass


class Api:
    def __init__(self, fail_stock=False):
        self.calls = []
        self.fail_stock = fail_stock
        self.contact = None
        self.order = None

    def __call__(self, req, timeout=30):
        path = urlsplit(req.full_url).path
        self.calls.append(path)
        if path.endswith('/2.0/contact/search'):
            return _Fake(b'[]')
        if path.endswith('/2.0/contact'):
            self.contact = json.loads(req.data.decode('utf-8'))
            return _Fake(b'{"id": 77}')
        if path.endswith('/2.0/kb_order'):
            self.order = json.loads(req.data.decode('utf-8'))
            return _Fake(b'{"id": 44, "document_nr": "AU-00044"}')
        if path.endswith('/delivery'):
            if self.fail_stock:
                return _Err(422, '{"message":"Zu wenig Lagerbestand: Lemon Pie"}')
            return _Fake(b'{"id": 55, "document_nr": "LS-00055"}')
        if path.endswith('/pdf'):
            content = base64.b64encode(b'%PDF-1.4 lieferschein').decode('ascii')
            return _Fake(json.dumps({
                'name': 'LS-00055.pdf', 'mime': 'application/pdf', 'content': content,
            }).encode('utf-8'))
        if path.endswith('/invoice'):
            return _Fake(b'{"id": 88, "document_nr": "RE-00088"}')
        raise AssertionError(path)

    def count(self, suffix):
        return sum(1 for path in self.calls if path.endswith(suffix))


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = harness.fresh_db()
        bexio_sync.set_transport(None)
        bexio_sync.set_mail_transport(None)
        os.environ['BEXIO_SYNC_ENABLED'] = '1'
        os.environ['BEXIO_DELIVERY_ENABLED'] = '1'
        os.environ['BEXIO_API_TOKEN'] = 'bexio-token-do-not-log'
        os.environ['BEXIO_USER_ID'] = '7'
        os.environ.pop('SMTP_HOST', None)
        self.mails = []
        bexio_sync.set_mail_transport(self._mail)

    def tearDown(self):
        bexio_sync.set_transport(None)
        bexio_sync.set_mail_transport(None)
        self.tmp.cleanup()

    def _mail(self, recipients, subject, body, attachment):
        self.mails.append({
            'to': list(recipients), 'subject': subject, 'body': body, 'attachment': attachment,
        })

    def _order(self):
        conn = connect()
        cid = conn.execute(
            """insert into customers(name,email,address,city,customer_type)
               values('Anna Beispiel','anna-lieferschein@example.com','Fährstrasse 1','Bern','Endkunde')"""
        ).lastrowid
        conn.execute(
            """insert into customer_accounts(customer_id,email,password_hash,name,address,zip,city,age_confirmed)
               values(?,?,?,?,?,?,?,1)""",
            (cid, 'anna-lieferschein@example.com', 'x', 'Anna Beispiel', 'Fährstrasse 1', '3004', 'Bern'))
        oid = conn.execute(
            """insert into orders(customer_id,channel,status,total_chf,shipping_chf,external_ref,payment_status,currency)
               values(?,?,?,?,?,?,?,?)""",
            (cid, 'website', 'bezahlt', 21.90, 9, 'bv-ls-1', 'bezahlt', 'CHF')).lastrowid
        conn.execute(
            'insert into order_items(order_id,article,qty,unit_chf,preorder) values(?,?,?,?,1)',
            (oid, 'Lemon Pie', 1, 12.90))
        conn.commit()
        conn.close()
        return oid

    def _sync(self, oid):
        conn = connect()
        try:
            return bexio_sync.sync_paid_order(conn, oid)
        finally:
            conn.close()

    def test_delivery_pdf_goes_to_both_recipients_once(self):
        api = Api()
        bexio_sync.set_transport(api)
        oid = self._order()
        result = self._sync(oid)
        self.assertEqual(result['status'], 'created', result)
        self.assertEqual(result['invoice_id'], 88)
        self.assertEqual(result['delivery_id'], 55)
        self.assertEqual(result['delivery_mail_status'], 'sent')
        self.assertNotIn('bexio-token-do-not-log', json.dumps(result))
        self.assertEqual(api.contact['street_name'], 'Fährstrasse')
        self.assertEqual(api.contact['house_number'], '1')
        self.assertEqual(api.contact['postcode'], '3004')
        self.assertEqual(api.contact['city'], 'Bern')
        self.assertEqual(api.order['api_reference'], 'bv-ls-1')
        self.assertEqual(api.count('/delivery'), 1)
        self.assertEqual(api.count('/pdf'), 1)
        self.assertEqual(api.count('/invoice'), 1)
        self.assertEqual(len(self.mails), 1)
        self.assertEqual(self.mails[0]['to'], ['mail@vapelounge.ch', 'daniela@bernvapes.ch'])
        filename, pdf, mime = self.mails[0]['attachment']
        self.assertEqual(filename, 'LS-00055.pdf')
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(mime, 'application/pdf')
        self.assertIn('AU-00044', self.mails[0]['body'])
        self.assertIn('Anna Beispiel', self.mails[0]['body'])
        conn = connect()
        row = conn.execute(
            'select bexio_order_id,bexio_kb_order_id,bexio_delivery_id,bexio_delivery_nr,delivery_mail_status from orders where id=?',
            (oid,)).fetchone()
        conn.close()
        self.assertEqual(row['bexio_order_id'], 88)
        self.assertEqual(row['bexio_kb_order_id'], 44)
        self.assertEqual(row['bexio_delivery_id'], 55)
        self.assertEqual(row['bexio_delivery_nr'], 'LS-00055')
        self.assertEqual(row['delivery_mail_status'], 'sent')

        again = self._sync(oid)
        self.assertEqual(again['status'], 'exists')
        self.assertEqual(len(self.mails), 1)
        self.assertEqual(api.count('/delivery'), 1)
        self.assertEqual(api.count('/pdf'), 1)
        self.assertEqual(api.count('/invoice'), 1)

    def test_stock_failure_alerts_daniela_and_still_invoices(self):
        api = Api(fail_stock=True)
        bexio_sync.set_transport(api)
        oid = self._order()
        result = self._sync(oid)
        self.assertEqual(result['status'], 'created', result)
        self.assertEqual(result['invoice_id'], 88)
        self.assertIsNone(result['delivery_id'])
        self.assertEqual(result['delivery_mail_status'], 'stock_alert_sent')
        self.assertEqual(api.count('/delivery'), 1)
        self.assertEqual(api.count('/pdf'), 0)
        self.assertEqual(api.count('/invoice'), 1)
        self.assertEqual(len(self.mails), 1)
        self.assertEqual(self.mails[0]['to'], ['daniela@bernvapes.ch'])
        self.assertIsNone(self.mails[0]['attachment'])
        text = self.mails[0]['subject'] + '\n' + self.mails[0]['body']
        self.assertIn(bexio_sync.STOCK_HINT, text)
        self.assertIn('AU-00044', text)
        self.assertIn('Anna Beispiel', text)
        self.assertIn('Lemon Pie', text)
        self.assertIn('Lagerbestand', text)
        self.assertNotIn('mail@vapelounge.ch', text)
        conn = connect()
        row = conn.execute(
            'select bexio_order_id,bexio_delivery_id,delivery_mail_status,delivery_error from orders where id=?',
            (oid,)).fetchone()
        conn.close()
        self.assertEqual(row['bexio_order_id'], 88)
        self.assertIsNone(row['bexio_delivery_id'])
        self.assertEqual(row['delivery_mail_status'], 'stock_alert_sent')
        self.assertIn('Lagerbestand', row['delivery_error'])

        again = self._sync(oid)
        self.assertEqual(again['status'], 'exists')
        self.assertEqual(len(self.mails), 1)
        self.assertEqual(api.count('/delivery'), 1)
        self.assertEqual(api.count('/invoice'), 1)


if __name__ == '__main__':
    unittest.main()
