import unittest
import harness
from db import connect

class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = harness.fresh_db()
        self.port = harness.ensure_server()

    def tearDown(self):
        self.tmp.cleanup()

    def test_uid_format_and_pending_cannot_order(self):
        client = harness.Client(self.port)
        st, data, _ = client.request('POST', '/api/b2b/register', json_body={
            'company_name': 'Falsche UID', 'uid': 'CHE-123456789',
            'email': 'falsch@example.com', 'password': 'dealer-password-1'})
        self.assertEqual(st, 422)
        self.assertEqual(data['error'], 'invalid_uid')
        st, data, _ = client.request('POST', '/api/b2b/register', json_body={
            'company_name': 'Warten GmbH', 'uid': 'che-111.222.333',
            'email': 'warten@example.com', 'password': 'dealer-password-1', 'language': 'fr'})
        self.assertEqual(st, 201, data)
        from auth import totp_code
        st, data, _ = client.request('POST', '/api/b2b/totp/confirm', json_body={'code': totp_code(data['totp_secret'])})
        self.assertEqual(data['status'], 'pending')
        st, data, _ = client.request('POST', '/api/b2b/orders', json_body={
            'items': [{'sku': 'lemon-pie', 'qty': 1}]})
        self.assertEqual(st, 403)
        self.assertEqual(data['error'], 'not_approved')
        c = connect()
        row = c.execute("select uid,status,company_verified_at from dealer_accounts where email='warten@example.com'").fetchone()
        cust = c.execute("select customer_type,language from customers where email='warten@example.com'").fetchone()
        c.close()
        self.assertEqual(row['uid'], 'CHE-111.222.333')
        self.assertEqual(row['status'], 'pending')
        self.assertIsNone(row['company_verified_at'])
        self.assertEqual(cust['customer_type'], 'Interessent')
        self.assertEqual(cust['language'], 'fr')
        admin = harness.admin_login(self.port)
        c = connect()
        did = c.execute("select id from dealer_accounts where email='warten@example.com'").fetchone()[0]
        c.close()
        st, _, _ = admin.request('POST', f'/haendler/{did}/aktion', form={'a': 'reject'})
        self.assertEqual(st, 303)
        st, data, _ = client.request('POST', '/api/b2b/orders', json_body={'items': [{'sku': 'lemon-pie', 'qty': 1}]})
        self.assertEqual(st, 403)
        c = connect()
        self.assertEqual(c.execute('select count(*) from orders').fetchone()[0], 0)
        c.close()

if __name__ == '__main__':
    unittest.main()
