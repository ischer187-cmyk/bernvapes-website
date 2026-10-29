"""Shared HTTP harness. One local CRM on 127.0.0.1, a fresh SQLite file per test."""
import json, os, sys, tempfile, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_server = None
_port = None

def configure(db_path):
    os.environ['DATABASE_URL'] = ''
    os.environ['CRM_SQLITE_PATH'] = str(db_path)
    os.environ['CRM_ADMIN_EMAIL'] = 'admin@bernvapes.test'
    os.environ['CRM_ADMIN_PASSWORD'] = 'local-test-password'
    os.environ['CRM_WEBHOOK_SECRET'] = 'whsec-test'
    os.environ['BEXIO_WRITE_ENABLED'] = '0'
    os.environ['EMAIL_DRIVER'] = 'log'
    os.environ['WEBSITE_PUBLIC_URL'] = 'http://127.0.0.1:8080'
    os.environ['CRM_MAIL_LOG'] = str(Path(db_path).parent / 'mail.log')
    os.environ['CRM_COOKIE_SECURE'] = '0'
    os.environ.setdefault('CRM_LOGIN_LIMIT', '8')
    os.environ.setdefault('CRM_LOGIN_WINDOW', '600')

def ensure_server():
    global _server, _port
    if _server is not None:
        return _port
    import app
    httpd = app.make_server('127.0.0.1', 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    _server = httpd
    _port = httpd.server_address[1]
    return _port

class Client:
    def __init__(self, port):
        self.port = port
        self.cookies = {}
        self.csrf = None

    def request(self, method, path, json_body=None, headers=None, form=None):
        import http.client
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        hs = {}
        body = None
        if self.cookies:
            hs['Cookie'] = '; '.join(f'{k}={v}' for k, v in self.cookies.items())
        if json_body is not None:
            body = json.dumps(json_body).encode()
            hs['Content-Type'] = 'application/json'
            hs['Accept'] = 'application/json'
        elif form is not None:
            from urllib.parse import urlencode
            body = urlencode(form).encode()
            hs['Content-Type'] = 'application/x-www-form-urlencoded'
        if self.csrf and method != 'GET':
            hs['X-CSRF-Token'] = self.csrf
        if headers:
            hs.update(headers)
        conn.request(method, path, body=body, headers=hs)
        resp = conn.getresponse()
        raw = resp.read()
        for val in resp.msg.get_all('Set-Cookie') or []:
            nv = val.split(';', 1)[0]
            if '=' not in nv:
                continue
            n, v = nv.split('=', 1)
            if v == '':
                self.cookies.pop(n.strip(), None)
            else:
                self.cookies[n.strip()] = v.strip()
        text = raw.decode()
        data = None
        if raw[:1:] in (b'{', b'['):
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = None
        if isinstance(data, dict) and data.get('csrf_token'):
            self.csrf = data['csrf_token']
        conn.close()
        return resp.status, data, text

def fresh_db():
    tmp = tempfile.TemporaryDirectory(prefix='bv-crm-')
    configure(Path(tmp.name) / 'crm.db')
    from migrate import migrate
    migrate()
    return tmp

def admin_login(port):
    from auth import totp_code
    client = Client(port)
    st, data, text = client.request('POST', '/login', json_body={
        'email': os.environ['CRM_ADMIN_EMAIL'], 'password': os.environ['CRM_ADMIN_PASSWORD']})
    assert st == 200, (st, data, text)
    assert data['scope'] == 'totp_setup'
    assert data.get('totp_secret')
    st, data, text = client.request('POST', '/login/totp', json_body={'code': totp_code(data['totp_secret'])})
    assert st == 200, (st, data, text)
    assert data['scope'] == 'full'
    assert client.csrf
    return client
