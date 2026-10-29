"""Passwords, TOTP (RFC 6238), sessions, CSRF, rate limits. Stdlib only.

scrypt when hashlib provides it (OpenSSL). LibreSSL in Xcode Python 3.9 has no
hashlib.scrypt, so those builds use PBKDF2-HMAC-SHA256. sha1/sha256/hmac/pbkdf2
are available on both. This module does not touch ssl.
"""
import base64, hashlib, hmac, os, secrets, struct, time
from datetime import datetime, timedelta, timezone

SESSION_HOURS = 8
PBKDF2_ROUNDS = 600000
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1

def utcnow():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

def utc_plus(seconds):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime('%Y-%m-%d %H:%M:%S')

def _scrypt():
    fn = getattr(hashlib, 'scrypt', None)
    return fn if callable(fn) else None

def hash_password(pw):
    salt = os.urandom(16)
    raw = pw.encode()
    scrypt = _scrypt()
    if scrypt is not None:
        try:
            dk = scrypt(raw, salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
        except AttributeError:
            scrypt = None
        else:
            return 'scrypt$' + salt.hex() + '$' + dk.hex()
    dk = hashlib.pbkdf2_hmac('sha256', raw, salt, PBKDF2_ROUNDS, dklen=32)
    return 'pbkdf2$%d$%s$%s' % (PBKDF2_ROUNDS, salt.hex(), dk.hex())

def verify_password(pw, stored):
    try:
        parts = (stored or '').split('$')
        raw = pw.encode()
        if len(parts) == 3 and parts[0] == 'scrypt':
            scrypt = _scrypt()
            if scrypt is None:
                return False
            salt = bytes.fromhex(parts[1])
            dk = scrypt(raw, salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
            return hmac.compare_digest(dk.hex(), parts[2])
        if len(parts) == 4 and parts[0] == 'pbkdf2':
            rounds = int(parts[1])
            if rounds < PBKDF2_ROUNDS or rounds > 5000000:
                return False
            salt = bytes.fromhex(parts[2])
            dk = hashlib.pbkdf2_hmac('sha256', raw, salt, rounds, dklen=32)
            return hmac.compare_digest(dk.hex(), parts[3])
        return False
    except Exception:
        return False

def new_totp_secret():
    return base64.b32encode(os.urandom(20)).decode().rstrip('=')

def _totp_key(secret):
    s = secret.strip().upper().replace(' ', '')
    s += '=' * ((8 - len(s) % 8) % 8)
    return base64.b32decode(s, casefold=True)

def totp_code(secret, at=None, step=30, digits=6):
    if at is None:
        at = time.time()
    counter = int(at) // step
    msg = struct.pack('>Q', counter)
    digest = hmac.new(_totp_key(secret), msg, hashlib.sha1).digest()
    off = digest[-1] & 0x0f
    num = struct.unpack('>I', digest[off:off + 4])[0] & 0x7fffffff
    return str(num % (10 ** digits)).zfill(digits)

def totp_ok(secret, code, window=1, at=None):
    code = ''.join(ch for ch in (code or '') if ch.isdigit())
    if len(code) != 6 or not secret:
        return False
    now = time.time() if at is None else at
    for w in range(-window, window + 1):
        if hmac.compare_digest(totp_code(secret, now + w * 30), code):
            return True
    return False

def otpauth_uri(secret, email, issuer='Bernvapes'):
    from urllib.parse import quote
    label = quote(issuer + ':' + email)
    return f'otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&digits=6&period=30'

def new_token():
    return secrets.token_urlsafe(32)

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def cookie_secure():
    return os.environ.get('CRM_COOKIE_SECURE', '0').strip().lower() in ('1', 'true', 'yes', 'on')

def session_cookie(name, token):
    parts = [f'{name}={token}', 'HttpOnly', 'SameSite=Lax', 'Path=/', f'Max-Age={SESSION_HOURS * 3600}']
    if cookie_secure():
        parts.append('Secure')
    return '; '.join(parts)

def clear_cookie(name):
    parts = [f'{name}=', 'HttpOnly', 'SameSite=Lax', 'Path=/', 'Max-Age=0']
    if cookie_secure():
        parts.append('Secure')
    return '; '.join(parts)

def create_session(conn, kind, user_id, scope):
    token = new_token()
    csrf = new_token()
    exp = utc_plus(SESSION_HOURS * 3600)
    conn.execute(
        'insert into sessions(token_hash,kind,scope,user_id,csrf_token,expires_at) values(?,?,?,?,?,?)',
        (token_hash(token), kind, scope, user_id, csrf, exp))
    return token, csrf

def read_session(conn, kind, token):
    if not token:
        return None
    row = conn.execute(
        "select * from sessions where token_hash=? and kind=? and expires_at > datetime('now')",
        (token_hash(token), kind)).fetchone()
    return row

def delete_session(conn, kind, token):
    if not token:
        return
    conn.execute('delete from sessions where token_hash=? and kind=?', (token_hash(token), kind))

def rotate_session(conn, kind, old_token, user_id, scope):
    delete_session(conn, kind, old_token)
    return create_session(conn, kind, user_id, scope)

def rate_ok(conn, bucket, limit, window_sec):
    cutoff = utc_plus(-window_sec)
    n = conn.execute('select count(*) from rate_limits where bucket=? and at>?', (bucket, cutoff)).fetchone()[0]
    if n >= limit:
        return False
    conn.execute('insert into rate_limits(bucket, at) values(?,?)', (bucket, utcnow()))
    if n == 0:
        conn.execute('delete from rate_limits where at < ?', (utc_plus(-2 * 24 * 3600),))
    return True

def rate_clear(conn, bucket):
    conn.execute('delete from rate_limits where bucket=?', (bucket,))

def login_limit():
    return int(os.environ.get('CRM_LOGIN_LIMIT', '8')), int(os.environ.get('CRM_LOGIN_WINDOW', '600'))

def csrf_ok(session, presented):
    if not session or not presented:
        return False
    expected = session['csrf_token']
    if not expected or len(presented) != len(expected):
        return False
    return hmac.compare_digest(presented, expected)
