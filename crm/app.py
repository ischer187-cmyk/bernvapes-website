"""Bernvapes Steuerzentrale.

Local: python3 app.py  ->  http://127.0.0.1:18734
SQLite unless DATABASE_URL is a postgres URL. Admin UI requires password + TOTP.
"""
import hmac, json, os, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pages
import portal
import shop_accounts
from auth import (
    clear_cookie, create_session, csrf_ok, delete_session, hash_password, login_limit,
    new_totp_secret, otpauth_uri, rate_clear, rate_ok, read_session, rotate_session,
    session_cookie, totp_ok, utcnow, verify_password,
)
from crmlib import convert, enroll_prospects, set_member_status
from db import IntegrityError, begin_request, connect, end_request
from migrate import migrate
import checkout
from orders import process_order
from portal import create_invite
from pricing import normalize_tier

ADMIN_COOKIE = 'bv_admin'
_DUMMY = hash_password('not-the-admin-password')

def _limit_body(handler):
    n = int(handler.headers.get('Content-Length') or 0)
    if n > 1_000_000:
        raise ValueError('body too large')
    return handler.rfile.read(n) if n else b''

class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):
        pass

    def db(self):
        return connect()

    def cookie(self, name):
        for part in (self.headers.get('Cookie') or '').split(';'):
            if '=' not in part:
                continue
            k, v = part.split('=', 1)
            if k.strip() == name:
                return v.strip()
        return ''

    def wants_json(self):
        ct = self.headers.get('Content-Type') or ''
        acc = self.headers.get('Accept') or ''
        return 'application/json' in ct or 'application/json' in acc

    def payload(self):
        raw = _limit_body(self)
        ct = self.headers.get('Content-Type') or ''
        if 'application/json' in ct:
            self._json = True
            try:
                data = json.loads(raw.decode() or '{}')
            except ValueError as e:
                raise ValueError('invalid json') from e
            if not isinstance(data, dict):
                raise ValueError('invalid json')
            return data
        self._json = False
        return {k: v[0] for k, v in parse_qs(raw.decode() or '', keep_blank_values=True).items()}

    def csrf_presented(self, data):
        return self.headers.get('X-CSRF-Token') or (data or {}).get('csrf') or ''

    def _cors(self):
        origin = (self.headers.get('Origin') or '').rstrip('/')
        allowed = (os.environ.get('WEBSITE_PUBLIC_URL') or 'http://127.0.0.1:8080').rstrip('/')
        if origin and origin == allowed:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Credentials', 'true')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-CSRF-Token')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Vary', 'Origin')

    def send(self, code, body, ct='text/html; charset=utf-8', cookie=None):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', str(len(b)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Cache-Control', 'no-store')
        self._cors()
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(b)
        return True

    def json(self, code, obj, cookie=None):
        return self.send(code, json.dumps(obj), 'application/json; charset=utf-8', cookie=cookie)

    def redirect(self, to, cookie=None):
        self.send_response(303)
        self.send_header('Location', to)
        self.send_header('Content-Length', '0')
        self.send_header('Cache-Control', 'no-store')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        return True

    def admin_session(self):
        c = self.db()
        try:
            return read_session(c, 'admin', self.cookie(ADMIN_COOKIE))
        finally:
            c.close()

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        token = begin_request()
        try:
            self._get()
        except Exception:
            traceback.print_exc()
            try:
                self.json(500, {'ok': False, 'error': 'server'})
            except Exception:
                pass
        finally:
            end_request(token)

    def do_POST(self):
        token = begin_request()
        try:
            self._json = False
            self._post()
        except ValueError as ex:
            self.json(400, {'ok': False, 'error': str(ex)})
        except Exception:
            traceback.print_exc()
            try:
                self.json(500, {'ok': False, 'error': 'server'})
            except Exception:
                pass
        finally:
            end_request(token)

    def _get(self):
        u = urlparse(self.path)
        path, q = u.path, parse_qs(u.query)
        if path == '/healthz':
            return self.json(200, {'ok': True, 'db': 'postgres' if os.environ.get('DATABASE_URL', '').startswith('postgres') else 'sqlite'})
        if path.startswith('/api/b2b/customer'):
            return shop_accounts.handle(self, 'GET', path)
        if path.startswith('/api/b2b'):
            return portal.handle(self, 'GET', path)
        if path == '/fox.png':
            return self.send(200, (pages.D / 'fox.png').read_bytes(), 'image/png')
        session = self.admin_session()
        if path == '/login':
            return self.send(200, self.login_html(session, q.get('e', [''])[0]))
        if not session or session['scope'] != 'full':
            if self.wants_json():
                return self.json(401, {'ok': False, 'error': 'login_required'})
            return self.redirect('/login')
        pages.CSRF.set(session['csrf_token'])
        if path in ('/kontakte', '/lieferanten', '/webhooks', '/bestellung'):
            dest = {'/kontakte': '/kunden', '/lieferanten': '/steuerung', '/webhooks': '/steuerung', '/bestellung': '/bestellungen'}[path]
            return self.redirect(dest + ('?' + u.query if u.query else ''))
        if path in pages.GET:
            return self.send(200, pages.GET[path](q))
        m = __import__('re').fullmatch(r'/bestellung/(\d+)', path)
        if m and (html := pages.bestellung(int(m.group(1)))):
            return self.send(200, html)
        m = __import__('re').fullmatch(r'/kontakt/(\d+)', path)
        if m and (html := pages.kontakt(int(m.group(1)))):
            return self.send(200, html)
        return self.send(404, pages.page('Nicht gefunden', '<section><p class="mu">Seite nicht gefunden.</p></section>'))

    def login_html(self, session, err=''):
        msg = {'login': 'Anmeldung fehlgeschlagen.', 'totp': 'Code ungültig.', 'rate': 'Zu viele Versuche. Kurz warten.'}.get(err, '')
        if session and session['scope'] == 'totp_setup':
            c = self.db()
            user = c.execute('select * from admin_users where id=?', (session['user_id'],)).fetchone()
            c.close()
            pages.CSRF.set(session['csrf_token'])
            secret = user['totp_secret']
            uri = otpauth_uri(secret, user['email'])
            body = f'''<section><h2>Zwei-Faktor einrichten</h2>
            <p class="mu">In der Authenticator-App ein Konto von Hand anlegen (oder den Link öffnen). Danach den 6-stelligen Code eingeben. Ohne diesen Code kein Zugang.</p>
            <p><b>Konto</b> {pages.e(user["email"])}<br><b>Schlüssel</b> <code>{pages.e(secret)}</code></p>
            <p><a href="{pages.e(uri)}">otpauth-Link</a></p>
            <p class="mu">{pages.e(msg)}</p>
            <form method="post" action="/login/totp"><input name="code" inputmode="numeric" autocomplete="one-time-code" placeholder="123 456" required><button class="pri">Bestätigen</button></form></section>'''
            return pages.page('Anmeldung', body, '/login')
        c = self.db()
        n = c.execute('select count(*) from admin_users').fetchone()[0]
        c.close()
        hint = '' if n else '<p class="no">Kein Admin. <code>CRM_ADMIN_EMAIL</code> und <code>CRM_ADMIN_PASSWORD</code> setzen und den Prozess neu starten.</p>'
        body = f'''<section><h2>Anmeldung</h2>{hint}<p class="mu">{pages.e(msg)}</p>
        <form method="post" action="/login"><input name="email" type="email" placeholder="E-Mail" required>
        <input name="password" type="password" placeholder="Passwort" required>
        <input name="totp" inputmode="numeric" autocomplete="one-time-code" placeholder="TOTP-Code, falls schon aktiv">
        <button class="pri">Anmelden</button></form>
        <p class="mu">Lokal auf 127.0.0.1. Passwort und TOTP. Keine Secrets im Code.</p></section>'''
        pages.CSRF.set('')
        return pages.page('Anmeldung', body, '/login')

    def _post(self):
        path = urlparse(self.path).path
        if path.startswith('/webhook/'):
            return self.webhook(path[len('/webhook/'):])
        if path.startswith('/api/b2b/customer'):
            return shop_accounts.handle(self, 'POST', path)
        if path.startswith('/api/b2b'):
            return portal.handle(self, 'POST', path)
        data = self.payload()
        if path == '/login':
            return self.login_post(data)
        if path == '/login/totp':
            return self.totp_post(data)
        if path == '/logout':
            return self.logout(data)
        session = self.admin_session()
        if not session:
            return self.json(401, {'ok': False, 'error': 'login_required'}) if self._json else self.redirect('/login')
        if not csrf_ok(session, self.csrf_presented(data)):
            return self.json(403, {'ok': False, 'error': 'csrf'}) if self._json else self.send(403, pages.page('CSRF', '<section><p>CSRF-Token fehlt oder ist ungültig. Seite neu laden.</p></section>'))
        if session['scope'] != 'full':
            return self.json(403, {'ok': False, 'error': 'totp_required'}) if self._json else self.redirect('/login')
        return self.admin_post(path, data)

    def login_post(self, data):
        email = str(data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        limit, window = login_limit()
        bucket = f'admin-login:{self.client_address[0]}:{email}'
        c = self.db()
        if not rate_ok(c, bucket, limit, window):
            c.commit(); c.close()
            return self.json(429, {'ok': False, 'error': 'rate_limited'}) if self._json else self.redirect('/login?e=rate')
        user = c.execute('select * from admin_users where email=?', (email,)).fetchone()
        ok = bool(user and user['password_hash'] and verify_password(password, user['password_hash']))
        if not ok:
            verify_password(password, _DUMMY)
            c.commit(); c.close()
            return self.json(401, {'ok': False, 'error': 'login_failed'}) if self._json else self.redirect('/login?e=login')
        if not user['totp_confirmed']:
            secret = user['totp_secret'] or new_totp_secret()
            if not user['totp_secret']:
                c.execute('update admin_users set totp_secret=? where id=?', (secret, user['id']))
            token, csrf = create_session(c, 'admin', user['id'], 'totp_setup')
            rate_clear(c, bucket)
            c.commit(); c.close()
            body = {'ok': True, 'scope': 'totp_setup', 'csrf_token': csrf, 'totp_secret': secret, 'otpauth_uri': otpauth_uri(secret, email)}
            cook = session_cookie(ADMIN_COOKIE, token)
            return self.json(200, body, cookie=cook) if self._json else self.redirect('/login', cookie=cook)
        if not totp_ok(user['totp_secret'], data.get('totp') or data.get('code') or ''):
            c.commit(); c.close()
            return self.json(401, {'ok': False, 'error': 'totp_invalid'}) if self._json else self.redirect('/login?e=totp')
        token, csrf = create_session(c, 'admin', user['id'], 'full')
        c.execute("update admin_users set last_login_at=datetime('now') where id=?", (user['id'],))
        rate_clear(c, bucket)
        c.commit(); c.close()
        cook = session_cookie(ADMIN_COOKIE, token)
        return self.json(200, {'ok': True, 'scope': 'full', 'csrf_token': csrf}, cookie=cook) if self._json else self.redirect('/', cookie=cook)

    def totp_post(self, data):
        session = self.admin_session()
        if not session or session['scope'] != 'totp_setup':
            return self.json(401, {'ok': False, 'error': 'login_required'}) if self._json else self.redirect('/login')
        if not csrf_ok(session, self.csrf_presented(data)):
            return self.json(403, {'ok': False, 'error': 'csrf'}) if self._json else self.send(403, pages.page('CSRF', '<section><p>CSRF-Token fehlt.</p></section>'))
        c = self.db()
        user = c.execute('select * from admin_users where id=?', (session['user_id'],)).fetchone()
        bucket = f'admin-totp:{user["id"]}'
        limit, window = login_limit()
        if not rate_ok(c, bucket, limit, window):
            c.commit(); c.close()
            return self.json(429, {'ok': False, 'error': 'rate_limited'}) if self._json else self.redirect('/login?e=rate')
        if not totp_ok(user['totp_secret'], data.get('code') or data.get('totp') or ''):
            c.commit(); c.close()
            return self.json(401, {'ok': False, 'error': 'totp_invalid'}) if self._json else self.redirect('/login?e=totp')
        c.execute("update admin_users set totp_confirmed=1, last_login_at=datetime('now') where id=?", (user['id'],))
        token, csrf = rotate_session(c, 'admin', self.cookie(ADMIN_COOKIE), user['id'], 'full')
        rate_clear(c, bucket)
        c.commit(); c.close()
        cook = session_cookie(ADMIN_COOKIE, token)
        return self.json(200, {'ok': True, 'scope': 'full', 'csrf_token': csrf}, cookie=cook) if self._json else self.redirect('/', cookie=cook)

    def logout(self, data):
        session = self.admin_session()
        if session and not csrf_ok(session, self.csrf_presented(data)):
            return self.json(403, {'ok': False, 'error': 'csrf'}) if self._json else self.send(403, pages.page('CSRF', '<section><p>CSRF-Token fehlt.</p></section>'))
        c = self.db()
        delete_session(c, 'admin', self.cookie(ADMIN_COOKIE))
        c.commit(); c.close()
        cook = clear_cookie(ADMIN_COOKIE)
        return self.json(200, {'ok': True}, cookie=cook) if self._json else self.redirect('/login', cookie=cook)

    def admin_post(self, path, f):
        import re
        c = self.db()
        try:
            if m := re.fullmatch(r'/kontakt/(\d+)/notiz', path):
                c.execute('insert into notes(customer_id,channel,body,author) values(?,?,?,?)', (m[1], f.get('channel', 'notiz'), f.get('body') or '', 'CRM'))
                c.commit(); return self.redirect(f'/kontakt/{m[1]}')
            if m := re.fullmatch(r'/kontakt/(\d+)/umwandeln', path):
                convert(c, int(m[1]), 'manuell im CRM'); c.commit(); return self.redirect(f'/kontakt/{m[1]}')
            if m := re.fullmatch(r'/kontakt/(\d+)/einladung', path):
                try:
                    create_invite(c, int(m[1]), f.get('email'), f.get('tier') or 'einstieg')
                    c.commit()
                except ValueError:
                    c.rollback()
                return self.redirect(f'/kontakt/{m[1]}')
            if m := re.fullmatch(r'/kampagne/mitglied/(\d+)/status', path):
                r = c.execute('select cu.id,cu.customer_type from campaign_members m join customers cu on cu.id=m.customer_id where m.id=?', (m[1],)).fetchone()
                if r and r[1] == 'Interessent':
                    set_member_status(c, int(m[1]), f.get('status'), f.get('note') or None); c.commit()
                return self.redirect(f'/kontakt/{r[0]}' if r else '/kampagnen')
            if m := re.fullmatch(r'/bestellung/(\d+)/aktion', path):
                a = f.get('a')
                if a == 'bezahlt':
                    c.execute("update orders set payment_status='bezahlt',updated_at=datetime('now') where id=?", (m[1],))
                if a == 'versendet':
                    c.execute("update orders set status='versendet',updated_at=datetime('now') where id=?", (m[1],))
                c.commit(); return self.redirect(self.headers.get('Referer') or '/bestellungen')
            if path == '/kunden/neu':
                email = str(f.get('email') or '').strip().lower()
                company = str(f.get('company_name') or '').strip()
                if '@' not in email or len(company) < 2:
                    return self.redirect('/kunden?tab=neu')
                if c.execute('select 1 from customers where lower(email)=?', (email,)).fetchone():
                    return self.redirect('/kunden?tab=neu')
                cid = c.execute(
                    '''insert into customers(name,email,customer_type,company_name,contact_person,city,canton,priority,language,source,tags)
                       values(?,?, 'Interessent', ?, ?, ?, ?, ?, ?, 'crm', 'manuell')''',
                    (company, email, company, f.get('contact_person') or None, f.get('city') or None, f.get('canton') or None,
                     f.get('priority') or None, f.get('language') or None)).lastrowid
                enroll_prospects(c)
                c.commit(); return self.redirect(f'/kontakt/{cid}')
            if path == '/aufgaben/neu':
                c.execute('insert into tasks(title,customer_id,due_date,assignee) values(?,?,?,?)', (f.get('title') or '', f.get('customer_id') or None, f.get('due_date') or None, f.get('assignee') or None))
                c.commit()
                return self.redirect(f'/kontakt/{f["customer_id"]}' if f.get('customer_id') else '/aufgaben')
            if m := re.fullmatch(r'/aufgaben/(\d+)/erledigt', path):
                c.execute("update tasks set done=1,done_at=datetime('now') where id=?", (m[1],)); c.commit(); return self.redirect('/aufgaben')
            if path == '/pipeline/neu':
                co = None
                if f.get('company'):
                    co = c.execute("insert into companies(name,kind) values(?,'b2b')", (f['company'],)).lastrowid
                c.execute('insert into deals(title,company_id,value_chf,source) values(?,?,?,?)', (f.get('title') or '', co, f.get('value_chf') or None, 'manuell'))
                c.commit(); return self.redirect('/pipeline')
            if m := re.fullmatch(r'/pipeline/(\d+)/stufe', path):
                if f.get('stage') in dict(pages.STAGES):
                    c.execute("update deals set stage=?,updated_at=datetime('now') where id=?", (f['stage'], m[1])); c.commit()
                return self.redirect('/pipeline')
            if path == '/lieferanten/neu':
                c.execute('insert into suppliers(name,contact_person,email,assortment,lead_time_days) values(?,?,?,?,?)',
                          (f.get('name'), f.get('contact_person'), f.get('email'), f.get('assortment'), f.get('lead_time_days') or None))
                c.commit(); return self.redirect('/steuerung')
            if m := re.fullmatch(r'/haendler/(\d+)/aktion', path):
                row = c.execute('select * from dealer_accounts where id=?', (m[1],)).fetchone()
                if row and f.get('a') == 'approve':
                    tier = row['price_tier'] or 'einstieg'
                    try:
                        tier = normalize_tier(f.get('tier') or tier)
                    except ValueError:
                        pass
                    c.execute(
                        """update dealer_accounts set status='approved', price_tier=?, company_verified_at=coalesce(company_verified_at,?),
                           company_verify_method=coalesce(company_verify_method,'uid'), updated_at=datetime('now') where id=?""",
                        (tier, utcnow(), m[1]))
                    if row['customer_id']:
                        c.execute('insert into notes(customer_id,channel,body,author) values(?,?,?,?)',
                                  (row['customer_id'], 'notiz', 'Händlerkonto freigegeben. Firmenprüfung statt persönlicher Altersprüfung.', 'CRM'))
                    c.commit()
                elif row and f.get('a') == 'reject':
                    c.execute("update dealer_accounts set status='rejected', updated_at=datetime('now') where id=?", (m[1],))
                    c.commit()
                return self.redirect(f'/kontakt/{row["customer_id"]}' if row and row['customer_id'] else '/haendler')
            if m := re.fullmatch(r'/haendler/(\d+)/stufe', path):
                tier = normalize_tier(f.get('tier') or '')
                c.execute("update dealer_accounts set price_tier=?, updated_at=datetime('now') where id=?", (tier, m[1]))
                row = c.execute('select customer_id from dealer_accounts where id=?', (m[1],)).fetchone()
                c.commit()
                return self.redirect(f'/kontakt/{row[0]}' if row and row[0] else '/haendler')
            if m := re.fullmatch(r'/haendler/(\d+)/preis', path):
                prod = c.execute('select id from products where sku=?', (f.get('sku') or '',)).fetchone()
                unit = float(f.get('unit_chf'))
                if prod and unit >= 0:
                    ex = c.execute('select id from price_overrides where dealer_id=? and product_id=?', (m[1], prod[0])).fetchone()
                    if ex:
                        c.execute('update price_overrides set unit_chf=? where id=?', (unit, ex[0]))
                    else:
                        c.execute('insert into price_overrides(dealer_id,product_id,unit_chf) values(?,?,?)', (m[1], prod[0], unit))
                    c.commit()
                row = c.execute('select customer_id from dealer_accounts where id=?', (m[1],)).fetchone()
                return self.redirect(f'/kontakt/{row[0]}' if row and row[0] else '/haendler')
            if m := re.fullmatch(r'/preise/(\d+)', path):
                c.execute(
                    'update products set price_einstieg=?, price_haendler=?, price_grosshaendler=?, sample_price=0 where id=?',
                    (float(f['price_einstieg']), float(f['price_haendler']), float(f['price_grosshaendler']), m[1]))
                c.commit(); return self.redirect('/preise')
            return self.send(404, 'not found', 'text/plain')
        finally:
            c.close()

    def postfinance_webhook(self):
        try:
            data = json.loads(_limit_body(self).decode() or '{}')
        except ValueError:
            return self.json(400, {'ok': False, 'error': 'invalid json'})
        if not isinstance(data, dict):
            return self.json(400, {'ok': False, 'error': 'invalid json'})
        c = self.db()
        try:
            code, body = checkout.apply_webhook(c, data)
        except Exception:
            traceback.print_exc()
            try:
                c.rollback()
            except Exception:
                pass
            return self.json(500, {'ok': False, 'error': 'server'})
        finally:
            c.close()
        return self.json(code, body)

    def webhook(self, name):
        if name == 'postfinance':
            return self.postfinance_webhook()
        if name not in pages.WEBHOOKS:
            return self.json(404, {'error': 'unknown webhook'})
        secret = os.environ.get('CRM_WEBHOOK_SECRET') or ''
        if not secret:
            return self.json(503, {'error': 'webhooks disabled (CRM_WEBHOOK_SECRET not set)'})
        got = self.headers.get('X-Bernvapes-Secret', '')
        if len(got) != len(secret) or not hmac.compare_digest(got, secret):
            return self.json(401, {'error': 'invalid secret'})
        try:
            data = json.loads(_limit_body(self).decode() or '{}')
        except ValueError:
            return self.json(400, {'error': 'invalid json'})
        if not isinstance(data, dict):
            return self.json(400, {'error': 'invalid json'})
        miss = [k for k in pages.REQ[name] if k not in data]
        if miss:
            return self.json(422, {'error': 'missing fields', 'fields': miss})
        c = self.db()
        try:
            c.execute('insert into webhook_events(source,event_id,status) values(?,?,?)', (name, str(data['event_id']), 'received'))
            c.commit()
        except IntegrityError:
            c.rollback(); c.close()
            return self.json(200, {'status': 'duplicate', 'event_id': data['event_id']})
        if name != 'order':
            c.close()
            return self.json(202, {'status': 'accepted (stub, no data changed)', 'webhook': name})
        try:
            res = process_order(c, data)
            c.execute('update webhook_events set status=? where source=? and event_id=?', ('processed', name, str(data['event_id'])))
            c.commit()
        except (ValueError, TypeError, IntegrityError) as ex:
            c.rollback()
            try:
                c.execute('update webhook_events set status=? where source=? and event_id=?', ('error', name, str(data['event_id'])))
                c.commit()
            except Exception:
                c.rollback()
            c.close()
            return self.json(422, {'error': str(ex)})
        c.close()
        return self.json(202, {'status': 'processed', **res})


def make_server(host, port):
    migrate()
    return ThreadingHTTPServer((host, port), H)


def main():
    host = os.environ.get('CRM_BIND', '127.0.0.1')
    port = int(os.environ.get('CRM_PORT', '18734'))
    if host not in ('127.0.0.1', '::1', 'localhost') and os.environ.get('CRM_ALLOW_PUBLIC_BIND') != '1':
        raise SystemExit(f'Refusing to bind {host}. The local app listens on 127.0.0.1. Inside Docker set CRM_ALLOW_PUBLIC_BIND=1.')
    httpd = make_server(host, port)
    print(f'Bernvapes Steuerzentrale: http://{host}:{port}', flush=True)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
