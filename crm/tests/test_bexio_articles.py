"""Shop-SKU → bexio-Artikel. Kein SMTP, kein echtes bexio."""
import json, os, re, unittest
from pathlib import Path
from urllib.parse import urlsplit

import harness
import bexio_sync
from db import connect

ALLOWED_IDS = {
    227, 213, 218, 216, 219, 232, 209, 242, 243, 244, 245,
    226, 210, 220, 231, 222, 211, 235, 214,
    217, 212, 229, 233, 215, 230,
}


class _Fake:
    status = 200

    def __init__(self, raw):
        self._raw = raw

    def read(self):
        return self._raw

    def close(self):
        pass


class Api:
    def __init__(self):
        self.calls = []
        self.order = None

    def __call__(self, req, timeout=30):
        path = urlsplit(req.full_url).path
        self.calls.append(path)
        if path.endswith('/2.0/contact/search'):
            return _Fake(b'[]')
        if path.endswith('/2.0/contact'):
            return _Fake(b'{"id": 77}')
        if path.endswith('/2.0/kb_order'):
            self.order = json.loads(req.data.decode('utf-8'))
            return _Fake(b'{"id": 44, "document_nr": "AU-00044"}')
        if path.endswith('/invoice'):
            return _Fake(b'{"id": 88}')
        raise AssertionError(path)

    def count(self, suffix):
        return sum(1 for path in self.calls if path.endswith(suffix))


class ArticleMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = harness.fresh_db()
        bexio_sync.set_transport(None)
        bexio_sync.set_mail_transport(None)
        os.environ['BEXIO_SYNC_ENABLED'] = '1'
        os.environ['BEXIO_DELIVERY_ENABLED'] = '0'
        os.environ['BEXIO_API_TOKEN'] = 'bexio-token-do-not-log'
        os.environ['BEXIO_USER_ID'] = '7'
        os.environ.pop('SMTP_HOST', None)
        os.environ.pop('STOCK_ALERT_RECIPIENT', None)
        self.mails = []
        bexio_sync.set_mail_transport(self._mail)
        self.api = Api()
        bexio_sync.set_transport(self.api)

    def tearDown(self):
        bexio_sync.set_transport(None)
        bexio_sync.set_mail_transport(None)
        self.tmp.cleanup()

    def _mail(self, recipients, subject, body, attachment):
        self.mails.append({
            'to': list(recipients), 'subject': subject, 'body': body, 'attachment': attachment,
        })

    def _order(self, ref, sku, name, unit=12.9, preorder=1):
        conn = connect()
        cid = conn.execute(
            """insert into customers(name,email,address,city,customer_type)
               values(?,?,?,?,?)""",
            ('Anna Beispiel', 'anna-%s@example.com' % ref, 'Fährstrasse 1', 'Bern', 'Endkunde')).lastrowid
        conn.execute(
            """insert into customer_accounts(customer_id,email,password_hash,name,address,zip,city,age_confirmed)
               values(?,?,?,?,?,?,?,1)""",
            (cid, 'anna-%s@example.com' % ref, 'x', 'Anna Beispiel', 'Fährstrasse 1', '3004', 'Bern'))
        oid = conn.execute(
            """insert into orders(customer_id,channel,status,total_chf,shipping_chf,external_ref,payment_status,currency)
               values(?,?,?,?,?,?,?,?)""",
            (cid, 'website', 'bezahlt', float(unit) + 9, 9, ref, 'bezahlt', 'CHF')).lastrowid
        conn.execute(
            'insert into order_items(order_id,article,qty,unit_chf,preorder,sku) values(?,?,?,?,?,?)',
            (oid, name, 1, unit, preorder, sku))
        conn.commit()
        conn.close()
        return oid

    def _sync(self, oid):
        conn = connect()
        try:
            return bexio_sync.sync_paid_order(conn, oid)
        finally:
            conn.close()

    def test_mapping_contains_exactly_the_allowed_ids(self):
        raw = Path(bexio_sync.ARTICLES_PATH).read_text(encoding='utf-8')
        data = json.loads(raw)
        ids = {int(value) for key, value in data.items() if not str(key).startswith('_')}
        self.assertEqual(ids, ALLOWED_IDS)
        self.assertEqual(set(bexio_sync.ARTICLES.values()), ALLOWED_IDS)
        for banned in ('BA-6327', 'BA-6331', 'BA-6333'):
            self.assertNotIn(banned, raw)
        self.assertEqual(bexio_sync.article_id_for({'sku': 'steinschlag_bock_otr_100ml', 'article': 'x'})[0], 209)
        self.assertEqual(bexio_sync.article_id_for({'sku': 'laenggass-dachs', 'article': 'x'})[0], 227)
        self.assertEqual(bexio_sync.article_id_for({'article': 'Länggass Dachs'})[0], 227)
        self.assertEqual(bexio_sync.ARTICLES['bollwerk-koeter'], 215)
        self.assertEqual(bexio_sync.ARTICLES['bollwerk-koter'], 215)
        self.assertNotIn('breitsch-hirsch-uf-ys', bexio_sync.ARTICLES)
        self.assertNotIn('abgrund-gemse', bexio_sync.ARTICLES)
        self.assertNotIn('abgrund_gemse_100ml', bexio_sync.ARTICLES)
        self.assertNotIn(223, ids)

    def test_every_bergtiere_data_key_is_mapped(self):
        html = Path(__file__).resolve().parents[2].joinpath('index.html').read_text(encoding='utf-8')
        start = html.find('id="bergtiere"')
        self.assertGreater(start, 0)
        nxt = html.find('<section', start + 1)
        chunk = html[start:nxt if nxt > start else None]
        pairs = re.findall(r'<figure[^>]*data-key="([^"]+)"[\s\S]*?class="flavor">([^<]+)', chunk)
        self.assertGreaterEqual(len(pairs), 11)
        for data_key, flavor in pairs:
            sku = bexio_sync._catalog_sku(flavor)
            self.assertIn(data_key, bexio_sync.ARTICLES, data_key)
            self.assertIn(sku, bexio_sync.ARTICLES, sku)
            self.assertEqual(bexio_sync.ARTICLES[data_key], bexio_sync.ARTICLES[sku], data_key)

    def test_mapped_line_is_article_position(self):
        oid = self._order('bv-map-lemon', 'lemon-pie', 'Lemon Pie', 12.90, 1)
        result = self._sync(oid)
        self.assertEqual(result['status'], 'created', result)
        positions = self.api.order['positions']
        lemon = positions[0]
        self.assertEqual(lemon['type'], 'KbPositionArticle')
        self.assertEqual(lemon['article_id'], 242)
        self.assertEqual(lemon['amount'], '1')
        self.assertEqual(lemon['unit_price'], '12.90')
        self.assertEqual(lemon['text'], 'Lemon Pie (Vorbestellung)')
        ship = positions[-1]
        self.assertEqual(ship['type'], 'KbPositionCustom')
        self.assertEqual(ship['text'], 'Versand')
        self.assertNotIn('article_id', ship)
        self.assertEqual(self.mails, [])

    def test_unmapped_line_warns_once(self):
        oid = self._order('bv-map-frei', 'sonder-mix', 'Sonder Mix', 10, 0)
        result = self._sync(oid)
        self.assertEqual(result['status'], 'created', result)
        row = self.api.order['positions'][0]
        self.assertEqual(row['type'], 'KbPositionCustom')
        self.assertNotIn('article_id', row)
        self.assertEqual(row['text'], 'Sonder Mix')
        self.assertEqual(row['unit_price'], '10.00')
        self.assertEqual(len(self.mails), 1)
        self.assertEqual(self.mails[0]['to'], ['daniela@bernvapes.ch'])
        self.assertIn('bv-map-frei', self.mails[0]['body'])
        self.assertIn('Sonder Mix', self.mails[0]['body'])
        self.assertIn('sonder-mix', self.mails[0]['body'])
        self.assertIsNone(self.mails[0]['attachment'])
        conn = connect()
        status = conn.execute(
            'select bexio_unmapped_mail_status from orders where id=?', (oid,)).fetchone()[0]
        conn.close()
        self.assertEqual(status, 'sent')
        calls = len(self.api.calls)
        again = self._sync(oid)
        self.assertEqual(again['status'], 'exists')
        self.assertEqual(len(self.mails), 1)
        self.assertEqual(len(self.api.calls), calls)


if __name__ == '__main__':
    unittest.main()
