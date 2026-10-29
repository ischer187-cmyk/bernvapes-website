"""B2B dealer HTTP API. Mounted at /api/b2b on the CRM. The website proxies /b2b-api here."""
import json, os
from datetime import datetime, timedelta, timezone
from auth import (
    csrf_ok, create_session, delete_session, hash_password, login_limit, new_token, new_totp_secret,
    otpauth_uri, rate_clear, rate_ok, read_session, rotate_session, session_cookie, clear_cookie,
    token_hash, totp_ok, utcnow, verify_password,
)
from crmlib import enroll_prospects
from mailer import get_mailer
from orders import process_order
from pricing import TIER_LABEL, normalize_tier, normalize_uid, unit_price
from db import IntegrityError

DEALER_COOKIE = 'bv_dealer'

def _public_base():
    return (os.environ.get('WEBSITE_PUBLIC_URL') or 'http://127.0.0.1:8080').rstrip('/')

def _dealer(conn, session):
    if not session:
        return None
    return conn.execute('select * from dealer_accounts where id=?', (session['user_id'],)).fetchone()

def _session_payload(dealer, scope, csrf, secret=None):
    body = {
        'ok': True,
        'scope': scope,
        'status': dealer['status'],
        'email': dealer['email'],
        'company_name': dealer['company_name'],
        'uid': dealer['uid'],
        'tier': dealer['price_tier'],
        'tier_label': TIER_LABEL.get(dealer['price_tier'] or '', dealer['price_tier']),
        'totp_confirmed': bool(dealer['totp_confirmed']),
        'company_verified': bool(dealer['company_verified_at']),
        'approved': dealer['status'] == 'approved',
        'csrf_token': csrf,
    }
    if secret:
        body['totp_secret'] = secret
        body['otpauth_uri'] = otpauth_uri(secret, dealer['email'])
    return body

def _issue(conn, dealer, scope):
    token, csrf = create_session(conn, 'dealer', dealer['id'], scope)
    secret = dealer['totp_secret'] if scope == 'totp_setup' else None
    return token, _session_payload(dealer, scope, csrf, secret)

def create_invite(conn, customer_id, email, tier):
    email = (email or '').strip().lower()
    if '@' not in email:
        raise ValueError('invalid email')
    tier = normalize_tier(tier or 'einstieg')
    cust = conn.execute('select * from customers where id=?', (customer_id,)).fetchone()
    if not cust:
        raise ValueError('customer missing')
    token = new_token()
    exp = (datetime.now(timezone.utc) + timedelta(days=int(os.environ.get('INVITE_TTL_DAYS', '14')))).strftime('%Y-%m-%d %H:%M:%S')
    existing = conn.execute('select id,status from dealer_accounts where customer_id=? or lower(email)=?', (customer_id, email)).fetchone()
    if existing and existing['status'] == 'approved':
        raise ValueError('dealer already approved')
    if existing and existing['status'] == 'disabled':
        raise ValueError('dealer disabled')
    if existing:
        conn.execute(
            """update dealer_accounts set email=?, price_tier=?, invite_token_hash=?, invite_expires_at=?,
               status=case when status='approved' then status else 'invited' end,
               company_name=coalesce(company_name,?), contact_person=coalesce(contact_person,?),
               updated_at=datetime('now') where id=?""",
            (email, tier, token_hash(token), exp, cust['company_name'] or cust['name'], cust['contact_person'], existing['id']))
        did = existing['id']
    else:
        did = conn.execute(
            """insert into dealer_accounts(customer_id,email,status,company_name,contact_person,price_tier,invite_token_hash,invite_expires_at)
               values(?,?, 'invited', ?, ?, ?, ?, ?)""",
            (customer_id, email, cust['company_name'] or cust['name'], cust['contact_person'], tier, token_hash(token), exp)).lastrowid
    link = f'{_public_base()}/haendler.html?token={token}'
    subject = 'Bernvapes Händlerportal – Einladung'
    body = (
        f"Guten Tag\n\n"
        f"für {cust['company_name'] or cust['name']} liegt ein Zugang zum Bernvapes-Händlerportal bereit.\n"
        f"Der Link ist einmalig und gilt {os.environ.get('INVITE_TTL_DAYS', '14')} Tage:\n\n{link}\n\n"
        f"Danach Passwort setzen und die Zwei-Faktor-Anmeldung (TOTP) aktivieren.\n"
        f"Preisstufe: {TIER_LABEL[tier]}.\n\nBernvapes\n"
    )
    get_mailer().send(email, subject, body)
    conn.execute('insert into mail_log(to_addr,subject,body) values(?,?,?)', (email, subject, body))
    conn.execute('insert into notes(customer_id,channel,body,author) values(?,?,?,?)',
                 (customer_id, 'notiz', f'Händler-Einladung an {email} ({TIER_LABEL[tier]}). Versand nicht konfiguriert, Link nur im Mail-Log.', 'CRM'))
    return {'dealer_id': did, 'link': link, 'email': email, 'tier': tier}

def handle(handler, method, path):
    """Return True when this request was a dealer API call."""
    if not path.startswith('/api/b2b'):
        return False
    conn = handler.db()
    ip = handler.client_address[0]
    rel = path[len('/api/b2b'):] or '/'
    public = rel in ('/health', '/login', '/register', '/invite/accept')
    try:
        session = None
        token = handler.cookie(DEALER_COOKIE)
        if token:
            session = read_session(conn, 'dealer', token)
        if method == 'GET' and rel == '/health':
            return handler.json(200, {'ok': True, 'service': 'b2b'})
        if method == 'GET' and rel == '/me':
            if not session:
                return handler.json(401, {'ok': False, 'error': 'login_required'})
            dealer = _dealer(conn, session)
            return handler.json(200, _session_payload(dealer, session['scope'], session['csrf_token']))
        if method == 'GET' and rel == '/catalog':
            if not session or session['scope'] != 'full':
                return handler.json(401, {'ok': False, 'error': 'login_required'})
            dealer = _dealer(conn, session)
            visible = dealer['status'] == 'approved' and bool(dealer['company_verified_at']) and bool(dealer['totp_confirmed'])
            rows = conn.execute('select * from products where coalesce(active,1)=1 order by bottle_ml, name').fetchall()
            products = []
            for p in rows:
                item = {'sku': p['sku'], 'name': p['name'], 'bottle_ml': p['bottle_ml'], 'sample_price': bool(p['sample_price'])}
                if visible:
                    unit, over = unit_price(conn, dealer['id'], p)
                    item['unit_chf'] = unit
                    item['override'] = over
                else:
                    item['unit_chf'] = None
                    item['override'] = False
                products.append(item)
            return handler.json(200, {
                'ok': True, 'prices_visible': visible, 'tier': dealer['price_tier'] if visible else None,
                'tier_label': TIER_LABEL.get(dealer['price_tier']) if visible else None,
                'status': dealer['status'], 'products': products,
            })
        if method == 'GET' and rel == '/orders':
            if not session or session['scope'] != 'full':
                return handler.json(401, {'ok': False, 'error': 'login_required'})
            dealer = _dealer(conn, session)
            if dealer['status'] != 'approved':
                return handler.json(403, {'ok': False, 'error': 'not_approved'})
            rows = conn.execute(
                'select id,status,payment_status,payment_method,total_chf,created_at from orders where dealer_account_id=? order by id desc',
                (dealer['id'],)).fetchall()
            return handler.json(200, {'ok': True, 'orders': [dict(zip(r.keys(), tuple(r))) for r in rows]})
        if method != 'POST':
            return handler.json(404, {'ok': False, 'error': 'not_found'})
        data = handler.payload()
        if rel == '/login':
            limit, window = login_limit()
            email = str(data.get('email') or '').strip().lower()
            bucket = f'dealer-login:{ip}:{email}'
            if not rate_ok(conn, bucket, limit, window):
                conn.commit()
                return handler.json(429, {'ok': False, 'error': 'rate_limited'})
            dealer = conn.execute('select * from dealer_accounts where lower(email)=?', (email,)).fetchone()
            pw_ok = bool(dealer and dealer['password_hash'] and verify_password(data.get('password') or '', dealer['password_hash']))
            if not pw_ok or dealer['status'] in ('rejected', 'disabled'):
                conn.commit()
                return handler.json(401, {'ok': False, 'error': 'login_failed'})
            if not dealer['totp_confirmed']:
                secret = dealer['totp_secret'] or new_totp_secret()
                if not dealer['totp_secret']:
                    conn.execute('update dealer_accounts set totp_secret=? where id=?', (secret, dealer['id']))
                dealer = conn.execute('select * from dealer_accounts where id=?', (dealer['id'],)).fetchone()
                tok, body = _issue(conn, dealer, 'totp_setup')
                rate_clear(conn, bucket)
                conn.commit()
                return handler.json(200, body, cookie=session_cookie(DEALER_COOKIE, tok))
            if not totp_ok(dealer['totp_secret'], data.get('totp') or data.get('code') or ''):
                conn.commit()
                return handler.json(401, {'ok': False, 'error': 'totp_invalid'})
            tok, body = _issue(conn, dealer, 'full')
            conn.execute("update dealer_accounts set last_login_at=datetime('now') where id=?", (dealer['id'],))
            rate_clear(conn, bucket)
            conn.commit()
            return handler.json(200, body, cookie=session_cookie(DEALER_COOKIE, tok))
        if rel == '/totp/confirm':
            if not session:
                return handler.json(401, {'ok': False, 'error': 'login_required'})
            if not csrf_ok(session, handler.csrf_presented(data)):
                return handler.json(403, {'ok': False, 'error': 'csrf'})
            dealer = _dealer(conn, session)
            bucket = f'dealer-totp:{dealer["id"]}'
            limit, window = login_limit()
            if not rate_ok(conn, bucket, limit, window):
                conn.commit()
                return handler.json(429, {'ok': False, 'error': 'rate_limited'})
            if not totp_ok(dealer['totp_secret'], data.get('code') or data.get('totp') or ''):
                conn.commit()
                return handler.json(401, {'ok': False, 'error': 'totp_invalid'})
            new_status = dealer['status']
            verified_at = dealer['company_verified_at']
            method = dealer['company_verify_method']
            if dealer['status'] == 'invited':
                new_status = 'approved'
                verified_at = utcnow()
                method = method or 'admin_invite'
            conn.execute(
                """update dealer_accounts set totp_confirmed=1, status=?, company_verified_at=coalesce(company_verified_at,?),
                   company_verify_method=coalesce(company_verify_method,?), updated_at=datetime('now') where id=?""",
                (new_status, verified_at, method, dealer['id']))
            if new_status == 'approved' and dealer['customer_id']:
                conn.execute(
                    'insert into notes(customer_id,channel,body,author) values(?,?,?,?)',
                    (dealer['customer_id'], 'notiz', 'Händlerkonto aktiv. Firmenprüfung über Einladung, keine persönliche Altersprüfung.', 'CRM'))
            conn.execute("update dealer_accounts set last_login_at=datetime('now') where id=?", (dealer['id'],))
            dealer = conn.execute('select * from dealer_accounts where id=?', (dealer['id'],)).fetchone()
            tok, csrf = rotate_session(conn, 'dealer', token, dealer['id'], 'full')
            rate_clear(conn, bucket)
            conn.commit()
            return handler.json(200, _session_payload(dealer, 'full', csrf), cookie=session_cookie(DEALER_COOKIE, tok))
        if rel == '/logout':
            if session and not csrf_ok(session, handler.csrf_presented(data)):
                return handler.json(403, {'ok': False, 'error': 'csrf'})
            delete_session(conn, 'dealer', token)
            conn.commit()
            return handler.json(200, {'ok': True}, cookie=clear_cookie(DEALER_COOKIE))
        if rel == '/register':
            limit, window = login_limit()
            if not rate_ok(conn, f'dealer-register:{ip}', max(5, limit // 2), max(window, 3600)):
                conn.commit()
                return handler.json(429, {'ok': False, 'error': 'rate_limited'})
            try:
                uid = normalize_uid(data.get('uid'))
            except ValueError as ex:
                conn.commit()
                return handler.json(422, {'ok': False, 'error': 'invalid_uid', 'detail': str(ex)})
            email = str(data.get('email') or '').strip().lower()
            company = str(data.get('company_name') or '').strip()
            password = data.get('password') or ''
            if '@' not in email or len(company) < 2 or len(password) < 10:
                conn.commit()
                return handler.json(422, {'ok': False, 'error': 'invalid_registration'})
            if conn.execute('select 1 from dealer_accounts where lower(email)=?', (email,)).fetchone():
                conn.commit()
                return handler.json(409, {'ok': False, 'error': 'email_taken'})
            if conn.execute('select 1 from customers where lower(email)=?', (email,)).fetchone():
                conn.commit()
                return handler.json(409, {'ok': False, 'error': 'email_taken'})
            person = (data.get('contact_person') or '').strip() or None
            city = (data.get('city') or '').strip() or None
            lang = (data.get('language') or '').strip() or None
            cid = conn.execute(
                '''insert into customers(name,email,customer_type,company_name,contact_person,city,language,source,tags)
                   values(?,?, 'Interessent', ?, ?, ?, ?, 'haendlerportal', 'Selbstregistrierung')''',
                (company, email, company, person, city, lang)).lastrowid
            secret = new_totp_secret()
            did = conn.execute(
                '''insert into dealer_accounts(customer_id,email,password_hash,totp_secret,totp_confirmed,status,company_name,uid,contact_person,price_tier)
                   values(?,?,?,?,0,'pending',?,?,?,'einstieg')''',
                (cid, email, hash_password(password), secret, company, uid, person)).lastrowid
            enroll_prospects(conn)
            conn.execute('insert into notes(customer_id,channel,body,author) values(?,?,?,?)',
                         (cid, 'notiz', f'Selbstregistrierung Händlerportal, UID {uid}, wartet auf Freigabe. Keine persönliche Altersprüfung vorgesehen.', 'Portal'))
            dealer = conn.execute('select * from dealer_accounts where id=?', (did,)).fetchone()
            tok, body = _issue(conn, dealer, 'totp_setup')
            conn.commit()
            return handler.json(201, body, cookie=session_cookie(DEALER_COOKIE, tok))
        if rel == '/invite/accept':
            limit, window = login_limit()
            if not rate_ok(conn, f'dealer-invite:{ip}', limit, window):
                conn.commit()
                return handler.json(429, {'ok': False, 'error': 'rate_limited'})
            raw = (data.get('token') or '').strip()
            password = data.get('password') or ''
            if not raw or len(password) < 10:
                conn.commit()
                return handler.json(422, {'ok': False, 'error': 'invalid_invite'})
            dealer = conn.execute(
                "select * from dealer_accounts where invite_token_hash=? and status='invited' and invite_expires_at > datetime('now')",
                (token_hash(raw),)).fetchone()
            if not dealer:
                conn.commit()
                return handler.json(401, {'ok': False, 'error': 'invite_invalid'})
            secret = dealer['totp_secret'] or new_totp_secret()
            conn.execute(
                """update dealer_accounts set password_hash=?, totp_secret=?, invite_token_hash=null, invite_expires_at=null,
                   updated_at=datetime('now') where id=?""",
                (hash_password(password), secret, dealer['id']))
            dealer = conn.execute('select * from dealer_accounts where id=?', (dealer['id'],)).fetchone()
            tok, body = _issue(conn, dealer, 'totp_setup')
            conn.commit()
            return handler.json(200, body, cookie=session_cookie(DEALER_COOKIE, tok))
        if rel == '/orders':
            if not session or session['scope'] != 'full':
                return handler.json(401, {'ok': False, 'error': 'login_required'})
            if not csrf_ok(session, handler.csrf_presented(data)):
                return handler.json(403, {'ok': False, 'error': 'csrf'})
            dealer = _dealer(conn, session)
            if dealer['status'] != 'approved' or not dealer['company_verified_at'] or not dealer['totp_confirmed']:
                return handler.json(403, {'ok': False, 'error': 'not_approved', 'status': dealer['status']})
            items = data.get('items')
            if not isinstance(items, list) or not items:
                return handler.json(422, {'ok': False, 'error': 'invalid_items'})
            event_id = str(data.get('event_id') or new_token())
            try:
                conn.execute('insert into webhook_events(source,event_id,status) values(?,?,?)', ('order', event_id, 'received'))
                conn.commit()
            except IntegrityError:
                conn.rollback()
                return handler.json(200, {'ok': True, 'status': 'duplicate', 'event_id': event_id})
            cust = conn.execute('select * from customers where id=?', (dealer['customer_id'],)).fetchone()
            payload = {
                'event_id': event_id,
                'email': dealer['email'],
                'name': cust['name'] if cust else dealer['company_name'],
                'company': dealer['company_name'],
                'city': cust['city'] if cust else None,
                'phone': cust['phone'] if cust else None,
                'channel': 'b2b',
                'payment_method': 'rechnung',
                'payment_status': 'offen',
                'items': items,
                'external_ref': data.get('external_ref') or f'b2b-{dealer["id"]}-{event_id[:12]}',
            }
            try:
                res = process_order(conn, payload, customer_id=dealer['customer_id'], dealer_id=dealer['id'])
                conn.execute('update webhook_events set status=? where source=? and event_id=?', ('processed', 'order', event_id))
                conn.commit()
            except (ValueError, TypeError) as ex:
                conn.rollback()
                c2 = handler.db()
                c2.execute('update webhook_events set status=? where source=? and event_id=?', ('error', 'order', event_id))
                c2.commit()
                c2.close()
                return handler.json(422, {'ok': False, 'error': str(ex)})
            res['ok'] = True
            res['status'] = 'processed'
            res['event_id'] = event_id
            return handler.json(202, res)
        return handler.json(404, {'ok': False, 'error': 'not_found'})
    finally:
        conn.close()
