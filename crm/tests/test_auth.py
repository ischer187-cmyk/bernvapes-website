import os, unittest
import harness
from auth import totp_code

class AuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = harness.fresh_db()
        self.port = harness.ensure_server()

    def tearDown(self):
        self.tmp.cleanup()

    def test_password_then_totp_then_session_and_csrf(self):
        anon = harness.Client(self.port)
        st, data, _ = anon.request('GET', '/', headers={'Accept': 'application/json'})
        self.assertEqual(st, 401)
        st, _, _ = anon.request('GET', '/')
        self.assertEqual(st, 303)
        st, data, _ = anon.request('POST', '/login', json_body={
            'email': os.environ['CRM_ADMIN_EMAIL'], 'password': 'wrong-password-xx'})
        self.assertEqual(st, 401)
        self.assertNotIn('bv_admin', anon.cookies)
        admin = harness.admin_login(self.port)
        st, _, text = admin.request('GET', '/')
        self.assertEqual(st, 200)
        self.assertIn('Steuerzentrale', text)
        saved = admin.csrf
        admin.csrf = None
        st, data, _ = admin.request('POST', '/aufgaben/neu', json_body={'title': 'Ohne Token'})
        self.assertEqual(st, 403)
        self.assertEqual(data['error'], 'csrf')
        admin.csrf = saved
        st, _, _ = admin.request('POST', '/aufgaben/neu', json_body={'title': 'Mit Token'})
        self.assertEqual(st, 303)
        st, _, _ = admin.request('POST', '/logout')
        self.assertIn(st, (200, 303))
        st, _, _ = admin.request('GET', '/', headers={'Accept': 'application/json'})
        self.assertEqual(st, 401)

    def test_totp_rejects_bad_code(self):
        client = harness.Client(self.port)
        st, data, _ = client.request('POST', '/login', json_body={
            'email': os.environ['CRM_ADMIN_EMAIL'], 'password': os.environ['CRM_ADMIN_PASSWORD']})
        self.assertEqual(data['scope'], 'totp_setup')
        st, data, _ = client.request('POST', '/login/totp', json_body={'code': '000000'})
        self.assertEqual(st, 401)
        st, _, text = client.request('GET', '/')
        self.assertEqual(st, 303)
        self.assertNotIn('Live-Leiste', text)

    def test_login_rate_limit(self):
        os.environ['CRM_LOGIN_LIMIT'] = '3'
        try:
            client = harness.Client(self.port)
            for _ in range(3):
                st, data, _ = client.request('POST', '/login', json_body={
                    'email': 'nobody@example.com', 'password': 'wrong-password-xx'})
                self.assertEqual(st, 401)
            st, data, _ = client.request('POST', '/login', json_body={
                'email': 'nobody@example.com', 'password': 'wrong-password-xx'})
            self.assertEqual(st, 429)
            self.assertEqual(data['error'], 'rate_limited')
        finally:
            os.environ['CRM_LOGIN_LIMIT'] = '8'

    def test_full_login_requires_current_totp(self):
        admin = harness.admin_login(self.port)
        admin.request('POST', '/logout')
        client = harness.Client(self.port)
        st, data, _ = client.request('POST', '/login', json_body={
            'email': os.environ['CRM_ADMIN_EMAIL'], 'password': os.environ['CRM_ADMIN_PASSWORD']})
        self.assertEqual(st, 401)
        self.assertEqual(data['error'], 'totp_invalid')
        from db import connect
        c = connect()
        secret = c.execute('select totp_secret from admin_users').fetchone()[0]
        c.close()
        st, data, _ = client.request('POST', '/login', json_body={
            'email': os.environ['CRM_ADMIN_EMAIL'],
            'password': os.environ['CRM_ADMIN_PASSWORD'],
            'totp': totp_code(secret)})
        self.assertEqual(st, 200)
        self.assertEqual(data['scope'], 'full')

if __name__ == '__main__':
    unittest.main()
