"""B2C customer accounts. Same CRM, same proxy (/api/b2b/customer → /b2b-api/customer).

End customers are active immediately. Age is a checkbox, never an ID document.
Password reset is written to the mail log. Nothing is sent.
"""
import os
from auth import (
    clear_cookie, create_session, csrf_ok, delete_session, hash_password, login_limit,
    new_token, rate_clear, rate_ok, read_session, session_cookie, token_hash, utc_plus, utcnow,
    verify_password,
)
import checkout
from db import IntegrityError
from mailer import deliver, registration_mail, reset_mail

COOKIE = 'bv_customer'

def _truthy(v):
    return v in (True, 1, '1', 'true', 'True', 'on', 'ja', 'yes', 'oui')

def _public():
    return (os.environ.get('WEBSITE_PUBLIC_URL') or 'http://127.0.0.1:8080').rstrip('/')

def _row_public(row):
    return {
        'ok': True,
        'kind': 'b2c',
        'email': row['email'],
        'name': row['name'],
        'address': row['address'],
        'zip': row['zip'],
        'city': row['city'],
        'age_confirmed': bool(row['age_confirmed']),
        'age_method': 'checkbox',
        'created_at': row['created_at'],
        'last_login_at': row['last_login_at'],
        'active': True,
    }

def _load(conn, session):
    if not session:
        return None
    return conn.execute('select * from customer_accounts where id=?', (session['user_id'],)).fetchone()

def handle(handler, method, path):
    if not path.startswith('/api/b2b/customer'):
        return False
    conn = handler.db()
    ip = handler.client_address[0]
    rel = path[len('/api/b2b/customer'):] or '/'
    token = handler.cookie(COOKIE)
    session = read_session(conn, 'customer', token) if token else None
    try:
        if method == 'GET' and rel == '/catalog':
            return handler.json(200, checkout.public_catalog(conn))
        if method == 'GET' and rel == '/me':
            row = _load(conn, session)
            if not row:
                return handler.json(401, {'ok': False, 'error': 'login_required'})
            body = _row_public(row)
            body['csrf_token'] = session['csrf_token']
            return handler.json(200, body)
        if method == 'GET' and rel == '/guest/order':
            return checkout.guest_order(handler, conn)
        row = _load(conn, session)
        if method == 'GET' and rel == '/order':
            if not row:
                return handler.json(401, {'ok': False, 'error': 'login_required'})
            return checkout.customer_order(handler, conn, row)
        if method != 'POST':
            return handler.json(404, {'ok': False, 'error': 'not_found'})
        data = handler.payload()
        if rel == '/login':
            return _login(handler, conn, ip, data)
        if rel == '/register':
            return _register(handler, conn, ip, data)
        if rel == '/forgot':
            return _forgot(handler, conn, ip, data)
        if rel == '/reset':
            return _reset(handler, conn, ip, data)
        if rel == '/guest/checkout':
            return _guest_checkout(handler, conn, data)
        if rel == '/checkout':
            if not row:
                return handler.json(401, {'ok': False, 'error': 'login_required'})
            if not session or not csrf_ok(session, handler.csrf_presented(data)):
                return handler.json(403, {'ok': False, 'error': 'csrf'})
            return checkout.customer_checkout(handler, conn, row, data)
        if rel == '/logout':
            if session and not csrf_ok(session, handler.csrf_presented(data)):
                return handler.json(403, {'ok': False, 'error': 'csrf'})
            delete_session(conn, 'customer', token)
            conn.commit()
            return handler.json(200, {'ok': True}, cookie=clear_cookie(COOKIE))
        return handler.json(404, {'ok': False, 'error': 'not_found'})
    finally:
        conn.close()

def _guest_checkout(handler, conn, data):
    """Kauf ohne Konto. Kein Session-Cookie, darum nur JSON (Browser schickt das cross-origin
    nicht ohne CORS-Freigabe) und ein Limit pro E-Mail plus ein globales Limit."""
    if not getattr(handler, '_json', False):
        return handler.json(415, {'ok': False, 'error': 'json_required'})
    if str(data.get('website') or '').strip():
        # Honeypot-Feld: Menschen sehen es nicht.
        return handler.json(422, {'ok': False, 'error': 'guest_invalid'})
    if not data.get('preview'):
        guest = data.get('guest') if isinstance(data.get('guest'), dict) else {}
        email = str(guest.get('email') or '').strip().lower()[:254]
        per_mail = int(os.environ.get('CRM_GUEST_LIMIT_PER_EMAIL', '5'))
        overall = int(os.environ.get('CRM_GUEST_LIMIT_GLOBAL', '200'))
        if not rate_ok(conn, 'guest-checkout:all', overall, 3600) or (
                email and not rate_ok(conn, f'guest-checkout:{email}', per_mail, 3600)):
            conn.commit()
            return handler.json(429, {'ok': False, 'error': 'rate_limited',
                                      'message': checkout.GUEST_MESSAGES['rate_limited']})
        conn.commit()
    return checkout.guest_checkout(handler, conn, data)

def _login(handler, conn, ip, data):
    limit, window = login_limit()
    email = str(data.get('email') or '').strip().lower()
    bucket = f'customer-login:{ip}:{email}'
    if not rate_ok(conn, bucket, limit, window):
        conn.commit()
        return handler.json(429, {'ok': False, 'error': 'rate_limited'})
    row = conn.execute('select * from customer_accounts where lower(email)=?', (email,)).fetchone()
    if not row or not verify_password(data.get('password') or '', row['password_hash']):
        conn.commit()
        return handler.json(401, {'ok': False, 'error': 'login_failed'})
    conn.execute("update customer_accounts set last_login_at=datetime('now') where id=?", (row['id'],))
    row = conn.execute('select * from customer_accounts where id=?', (row['id'],)).fetchone()
    tok, csrf = create_session(conn, 'customer', row['id'], 'full')
    rate_clear(conn, bucket)
    conn.commit()
    body = _row_public(row)
    body['csrf_token'] = csrf
    body['scope'] = 'full'
    return handler.json(200, body, cookie=session_cookie(COOKIE, tok))

def _register(handler, conn, ip, data):
    limit, window = login_limit()
    if not rate_ok(conn, f'customer-register:{ip}', max(5, limit // 2), max(window, 3600)):
        conn.commit()
        return handler.json(429, {'ok': False, 'error': 'rate_limited'})
    email = str(data.get('email') or '').strip().lower()
    name = str(data.get('name') or '').strip()
    password = data.get('password') or ''
    address = str(data.get('address') or '').strip()
    zipc = str(data.get('zip') or '').strip()
    city = str(data.get('city') or '').strip()
    if '@' not in email or len(name) < 2 or len(password) < 10 or len(address) < 3:
        conn.commit()
        return handler.json(422, {'ok': False, 'error': 'invalid_registration'})
    if not _truthy(data.get('age_18')):
        conn.commit()
        return handler.json(422, {'ok': False, 'error': 'age_required'})
    if conn.execute('select 1 from dealer_accounts where lower(email)=?', (email,)).fetchone():
        conn.commit()
        return handler.json(409, {'ok': False, 'error': 'dealer_email'})
    if conn.execute('select 1 from customer_accounts where lower(email)=?', (email,)).fetchone():
        conn.commit()
        return handler.json(409, {'ok': False, 'error': 'email_taken'})
    now = utcnow()
    # Checkbox = Selbstbestätigung. age_verified bleibt 0, bis das CRM manuell prüft. Keine Ausweisbilder.
    existing = conn.execute(
        "select id, customer_type from customers where lower(email)=? order by id limit 1", (email,)).fetchone()
    if existing and existing['customer_type'] not in ('Endkunde', None, ''):
        conn.commit()
        return handler.json(409, {'ok': False, 'error': 'email_taken'})
    if existing:
        cid = existing['id']
        conn.execute(
            """update customers set name=?, address=?, city=?, customer_type='Endkunde',
               age_verified_at=?, age_verify_method='checkbox', age_verified=0, updated_at=datetime('now')
               where id=?""",
            (name, address, city, now, cid))
    else:
        cid = conn.execute(
            """insert into customers(name,email,customer_type,address,city,age_verified_at,age_verify_method,age_verified,source,tags)
               values(?,?, 'Endkunde', ?, ?, ?, 'checkbox', 0, 'website', 'B2C')""",
            (name, email, address, city, now)).lastrowid
    try:
        aid = conn.execute(
            """insert into customer_accounts(customer_id,email,password_hash,name,address,zip,city,age_confirmed,age_confirmed_at)
               values(?,?,?,?,?,?,?,1,?)""",
            (cid, email, hash_password(password), name, address, zipc, city, now)).lastrowid
    except IntegrityError:
        conn.rollback()
        return handler.json(409, {'ok': False, 'error': 'email_taken'})
    conn.execute(
        'insert into notes(customer_id,channel,body,author) values(?,?,?,?)',
        (cid, 'notiz', 'B2C-Konto angelegt. Altersbestätigung nur Checkbox 18+, keine e-ID und keine Ausweisdaten.', 'Portal'))
    conn.execute("update customer_accounts set last_login_at=datetime('now') where id=?", (aid,))
    row = conn.execute('select * from customer_accounts where id=?', (aid,)).fetchone()
    tok, csrf = create_session(conn, 'customer', aid, 'full')
    conn.commit()
    subject, text = registration_mail(name)
    deliver(conn, email, subject, text)
    body = _row_public(row)
    body['csrf_token'] = csrf
    body['scope'] = 'full'
    body['customer_id'] = cid
    return handler.json(201, body, cookie=session_cookie(COOKIE, tok))

def _forgot(handler, conn, ip, data):
    limit, window = login_limit()
    if not rate_ok(conn, f'customer-forgot:{ip}', 5, max(window, 3600)):
        conn.commit()
        return handler.json(429, {'ok': False, 'error': 'rate_limited'})
    email = str(data.get('email') or '').strip().lower()
    row = conn.execute('select * from customer_accounts where lower(email)=?', (email,)).fetchone() if '@' in email else None
    if row:
        raw = new_token()
        conn.execute(
            "update customer_accounts set reset_token_hash=?, reset_expires_at=? where id=?",
            (token_hash(raw), utc_plus(2 * 3600), row['id']))
        link = f'{_public()}/konto.html?token={raw}'
        subject, body = reset_mail(link)
        deliver(conn, email, subject, body)
    conn.commit()
    return handler.json(200, {'ok': True, 'status': 'logged'})

def _reset(handler, conn, ip, data):
    limit, window = login_limit()
    if not rate_ok(conn, f'customer-reset:{ip}', limit, window):
        conn.commit()
        return handler.json(429, {'ok': False, 'error': 'rate_limited'})
    raw = (data.get('token') or '').strip()
    password = data.get('password') or ''
    if not raw or len(password) < 10:
        conn.commit()
        return handler.json(422, {'ok': False, 'error': 'invalid_reset'})
    row = conn.execute(
        "select * from customer_accounts where reset_token_hash=? and reset_expires_at > datetime('now')",
        (token_hash(raw),)).fetchone()
    if not row:
        conn.commit()
        return handler.json(401, {'ok': False, 'error': 'reset_invalid'})
    conn.execute(
        """update customer_accounts set password_hash=?, reset_token_hash=null, reset_expires_at=null,
           last_login_at=datetime('now') where id=?""",
        (hash_password(password), row['id']))
    row = conn.execute('select * from customer_accounts where id=?', (row['id'],)).fetchone()
    tok, csrf = create_session(conn, 'customer', row['id'], 'full')
    conn.commit()
    body = _row_public(row)
    body['csrf_token'] = csrf
    body['scope'] = 'full'
    return handler.json(200, body, cookie=session_cookie(COOKIE, tok))
