import os, unittest
import harness
from db import connect

class CustomerAccountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = harness.fresh_db()
        self.port = harness.ensure_server()

    def tearDown(self):
        self.tmp.cleanup()

    def test_register_requires_age_checkbox_and_is_active_immediately(self):
        c = harness.Client(self.port)
        body = {
            'name': 'Anna Beispiel', 'email': 'anna@example.com', 'password': 'kunden-passwort-1',
            'address': 'Fährstrasse 1', 'zip': '3004', 'city': 'Bern',
        }
        st, data, _ = c.request('POST', '/api/b2b/customer/register', json_body=body)
        self.assertEqual(st, 422)
        self.assertEqual(data['error'], 'age_required')
        body['age_18'] = True
        st, data, _ = c.request('POST', '/api/b2b/customer/register', json_body=body)
        self.assertEqual(st, 201, data)
        self.assertTrue(data['active'])
        self.assertEqual(data['age_method'], 'checkbox')
        self.assertEqual(data['kind'], 'b2c')
        st, me, _ = c.request('GET', '/api/b2b/customer/me')
        self.assertEqual(st, 200)
        self.assertEqual(me['email'], 'anna@example.com')
        self.assertEqual(me['city'], 'Bern')
        db = connect()
        acc = db.execute("select password_hash, age_confirmed from customer_accounts where email='anna@example.com'").fetchone()
        cust = db.execute("select customer_type, age_verify_method, age_verified_at from customers where email='anna@example.com'").fetchone()
        self.assertTrue(acc['password_hash'].startswith(('scrypt$', 'pbkdf2$')))
        self.assertNotIn('kunden-passwort-1', acc['password_hash'])
        self.assertEqual(acc['age_confirmed'], 1)
        self.assertEqual(cust['customer_type'], 'Endkunde')
        self.assertEqual(cust['age_verify_method'], 'checkbox')
        self.assertTrue(cust['age_verified_at'])
        self.assertIsNone(db.execute("select age_verify_ref from customers where email='anna@example.com'").fetchone()[0])
        db.close()
        saved = c.csrf
        c.csrf = None
        st, data, _ = c.request('POST', '/api/b2b/customer/logout', json_body={})
        self.assertEqual(st, 403)
        c.csrf = saved
        st, _, _ = c.request('POST', '/api/b2b/customer/logout', json_body={})
        self.assertEqual(st, 200)
        st, _, _ = c.request('GET', '/api/b2b/customer/me')
        self.assertEqual(st, 401)
        st, data, _ = c.request('POST', '/api/b2b/customer/login', json_body={
            'email': 'anna@example.com', 'password': 'falsch-falsch-1'})
        self.assertEqual(st, 401)
        st, data, _ = c.request('POST', '/api/b2b/customer/login', json_body={
            'email': 'anna@example.com', 'password': 'kunden-passwort-1'})
        self.assertEqual(st, 200)
        self.assertTrue(data['last_login_at'])

    def test_existing_endkunde_can_register_and_forgot_password_is_only_logged(self):
        db = connect()
        db.execute(
            "insert into customers(name,email,customer_type,city) values('Bestand','bestand@example.com','Endkunde','Thun')")
        db.commit()
        db.close()
        c = harness.Client(self.port)
        st, data, _ = c.request('POST', '/api/b2b/customer/register', json_body={
            'name': 'Bestand Kunde', 'email': 'bestand@example.com', 'password': 'kunden-passwort-1',
            'address': 'Hauptgasse 2', 'zip': '3600', 'city': 'Thun', 'age_18': True})
        self.assertEqual(st, 201, data)
        db = connect()
        n = db.execute("select count(*) from customers where lower(email)='bestand@example.com'").fetchone()[0]
        db.close()
        self.assertEqual(n, 1)
        c.csrf = None
        anon = harness.Client(self.port)
        st, data, _ = anon.request('POST', '/api/b2b/customer/forgot', json_body={'email': 'bestand@example.com'})
        self.assertEqual(st, 200)
        self.assertEqual(data['status'], 'logged')
        db = connect()
        mail = db.execute('select body from mail_log order by id desc limit 1').fetchone()[0]
        db.close()
        self.assertIn('konto.html?token=', mail)
        self.assertIn('verschickt', mail.lower())
        token = mail.split('token=', 1)[1].split()[0].strip()
        st, data, _ = anon.request('POST', '/api/b2b/customer/reset', json_body={
            'token': token, 'password': 'neues-passwort-2'})
        self.assertEqual(st, 200, data)
        st, _, _ = anon.request('POST', '/api/b2b/customer/logout', json_body={})
        self.assertEqual(st, 200)
        other = harness.Client(self.port)
        st, _, _ = other.request('POST', '/api/b2b/customer/login', json_body={
            'email': 'bestand@example.com', 'password': 'kunden-passwort-1'})
        self.assertEqual(st, 401)
        st, me, _ = other.request('POST', '/api/b2b/customer/login', json_body={
            'email': 'bestand@example.com', 'password': 'neues-passwort-2'})
        self.assertEqual(st, 200)
        self.assertEqual(me['name'], 'Bestand Kunde')
        import inspect, mailer
        self.assertNotIn('smtplib', inspect.getsource(mailer))

    def test_crm_list_shows_b2c_and_b2b(self):
        reg = harness.Client(self.port)
        st, _, _ = reg.request('POST', '/api/b2b/customer/register', json_body={
            'name': 'Lea Liste', 'email': 'lea@example.com', 'password': 'kunden-passwort-1',
            'address': 'Aareweg 3', 'zip': '3000', 'city': 'Bern', 'age_18': True})
        self.assertEqual(st, 201)
        db = connect()
        cid = db.execute(
            "insert into customers(name,email,customer_type,company_name) values('Shop Liste','shop@example.com','Interessent','Shop Liste')"
        ).lastrowid
        db.execute(
            """insert into dealer_accounts(customer_id,email,status,company_name,price_tier,created_at)
               values(?, 'shop@example.com', 'pending', 'Shop Liste', 'einstieg', datetime('now'))""",
            (cid,))
        db.commit()
        db.close()
        admin = harness.admin_login(self.port)
        st, _, html = admin.request('GET', '/konten')
        self.assertEqual(st, 200)
        self.assertIn('B2C', html)
        self.assertIn('B2B', html)
        self.assertIn('lea@example.com', html)
        self.assertIn('shop@example.com', html)
        self.assertIn('Letzter Login', html)
        self.assertIn('Registriert', html)

if __name__ == '__main__':
    unittest.main()
