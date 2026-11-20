"""CRM_REQUIRE_2FA switch: true (default) keeps TOTP; false grants full session on password."""
import os
import unittest

import harness
from auth import require_2fa, totp_code


class Require2FATests(unittest.TestCase):
    def setUp(self):
        self.tmp = harness.fresh_db()
        self.port = harness.ensure_server()
        self._prev = os.environ.get('CRM_REQUIRE_2FA')

    def tearDown(self):
        if self._prev is None:
            os.environ.pop('CRM_REQUIRE_2FA', None)
        else:
            os.environ['CRM_REQUIRE_2FA'] = self._prev
        self.tmp.cleanup()

    def test_require_2fa_defaults_true(self):
        os.environ.pop('CRM_REQUIRE_2FA', None)
        self.assertTrue(require_2fa())
        os.environ['CRM_REQUIRE_2FA'] = ''
        self.assertTrue(require_2fa())
        os.environ['CRM_REQUIRE_2FA'] = 'maybe'
        self.assertTrue(require_2fa())
        os.environ['CRM_REQUIRE_2FA'] = 'false'
        self.assertFalse(require_2fa())
        os.environ['CRM_REQUIRE_2FA'] = '0'
        self.assertFalse(require_2fa())

    def test_true_login_totp_setup_and_wrong_password(self):
        os.environ['CRM_REQUIRE_2FA'] = 'true'
        client = harness.Client(self.port)
        st, data, _ = client.request('POST', '/login', json_body={
            'email': os.environ['CRM_ADMIN_EMAIL'], 'password': 'wrong-password-xx'})
        self.assertEqual(st, 401)
        self.assertEqual(data['error'], 'login_failed')
        st, data, _ = client.request('POST', '/login', json_body={
            'email': os.environ['CRM_ADMIN_EMAIL'], 'password': os.environ['CRM_ADMIN_PASSWORD']})
        self.assertEqual(st, 200)
        self.assertEqual(data['scope'], 'totp_setup')
        st, data, _ = client.request('POST', '/login/totp', json_body={'code': '000000'})
        self.assertEqual(st, 401)
        self.assertEqual(data['error'], 'totp_invalid')

    def test_false_password_only_full_session(self):
        os.environ['CRM_REQUIRE_2FA'] = 'false'
        client = harness.Client(self.port)
        st, data, _ = client.request('POST', '/login', json_body={
            'email': os.environ['CRM_ADMIN_EMAIL'], 'password': 'wrong-password-xx'})
        self.assertEqual(st, 401)
        self.assertEqual(data['error'], 'login_failed')
        st, data, _ = client.request('POST', '/login', json_body={
            'email': os.environ['CRM_ADMIN_EMAIL'], 'password': os.environ['CRM_ADMIN_PASSWORD']})
        self.assertEqual(st, 200)
        self.assertEqual(data['scope'], 'full')
        self.assertNotIn('totp_secret', data)
        st, _, text = client.request('GET', '/')
        self.assertEqual(st, 200)
        self.assertIn('Steuerzentrale', text)
        # Login page hint mentions password-only mode
        anon = harness.Client(self.port)
        st, _, text = anon.request('GET', '/login')
        self.assertEqual(st, 200)
        self.assertIn('CRM_REQUIRE_2FA=false', text)
        self.assertNotIn('name="totp"', text)

    def test_missing_env_behaves_as_true(self):
        os.environ.pop('CRM_REQUIRE_2FA', None)
        client = harness.Client(self.port)
        st, data, _ = client.request('POST', '/login', json_body={
            'email': os.environ['CRM_ADMIN_EMAIL'], 'password': os.environ['CRM_ADMIN_PASSWORD']})
        self.assertEqual(st, 200)
        self.assertEqual(data['scope'], 'totp_setup')

    def test_false_still_rejects_after_confirmed_totp_without_code_when_reenabled(self):
        # Complete TOTP once under true, then switch false for password-only full login.
        os.environ['CRM_REQUIRE_2FA'] = 'true'
        admin = harness.admin_login(self.port)
        admin.request('POST', '/logout')
        os.environ['CRM_REQUIRE_2FA'] = 'false'
        client = harness.Client(self.port)
        st, data, _ = client.request('POST', '/login', json_body={
            'email': os.environ['CRM_ADMIN_EMAIL'], 'password': os.environ['CRM_ADMIN_PASSWORD']})
        self.assertEqual(st, 200)
        self.assertEqual(data['scope'], 'full')
        # Re-enable 2FA: confirmed user needs code
        client.request('POST', '/logout')
        os.environ['CRM_REQUIRE_2FA'] = 'true'
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
