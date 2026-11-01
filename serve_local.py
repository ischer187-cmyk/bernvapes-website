"""Local website server for the Mac test. Binds 127.0.0.1:8080 and proxies /b2b-api to the CRM.

Not a deploy. Does not talk to the live shop, DNS, or any public host.
"""
import http.client, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parent
UPSTREAM = os.environ.get('CRM_UPSTREAM', 'http://127.0.0.1:18734')
PORT = int(os.environ.get('WEB_PORT', '8080'))
TYPES = {
    '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
    '.png': 'image/png', '.webp': 'image/webp', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.json': 'application/json', '.txt': 'text/plain; charset=utf-8',
    '.webm': 'video/webm', '.mp4': 'video/mp4',
}

def b2b_enabled():
    """Shop login is B2C until B2B_ENABLED is true/1/yes/on. Default false."""
    return os.environ.get('B2B_ENABLED', 'false').strip().lower() in ('1', 'true', 'yes', 'on')

def inject_flags(html):
    flag = b'true' if b2b_enabled() else b'false'
    snippet = b'<script>window.BV_B2B_ENABLED=' + flag + b';if(window.BV_B2B_ENABLED)document.documentElement.setAttribute("data-b2b","1");</script>'
    lower = html.lower()
    at = lower.find(b'</head>')
    if at < 0:
        return snippet + html
    return html[:at] + snippet + html[at:]

def _blocked(rel):
    parts = Path(rel).parts
    if not parts:
        return False
    if parts[0] in ('crm', '.git', '.github') or any(p.startswith('.') for p in parts):
        return True
    low = rel.lower()
    return low.endswith('.env') or low.endswith('.db') or 'mail.log' in low

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self._route()

    def do_POST(self):
        self._route()

    def do_OPTIONS(self):
        self._route()

    def _route(self):
        path = urlsplit(self.path).path
        if path.startswith('/b2b-api'):
            return self._proxy('/api/b2b' + self.path[len('/b2b-api'):])
        if path == '/webhook/postfinance':
            return self._proxy(self.path)
        rel = unquote(path).lstrip('/') or 'index.html'
        if _blocked(rel) or '..' in rel.split('/'):
            return self._send(404, b'not found', 'text/plain')
        full = (ROOT / rel).resolve()
        try:
            full.relative_to(ROOT.resolve())
        except ValueError:
            return self._send(404, b'not found', 'text/plain')
        if full.is_dir():
            full = full / 'index.html'
        if not full.is_file():
            return self._send(404, b'not found', 'text/plain')
        data = full.read_bytes()
        ct = TYPES.get(full.suffix.lower(), 'application/octet-stream')
        if full.suffix.lower() == '.html':
            data = inject_flags(data)
        return self._send(200, data, ct)

    def _proxy(self, target):
        u = urlsplit(UPSTREAM)
        n = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(n) if n else None
        headers = {}
        for key in ('Content-Type', 'Accept', 'Cookie', 'X-CSRF-Token', 'Origin'):
            if self.headers.get(key):
                headers[key] = self.headers[key]
        if body is not None:
            headers['Content-Length'] = str(len(body))
        try:
            conn = http.client.HTTPConnection(u.hostname, u.port or 18734, timeout=30)
            conn.request(self.command, target, body=body, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
            self.send_response(resp.status)
            self.send_header('Content-Type', resp.getheader('Content-Type') or 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            for val in resp.msg.get_all('Set-Cookie') or []:
                self.send_header('Set-Cookie', val)
            self.end_headers()
            self.wfile.write(raw)
            conn.close()
        except OSError:
            msg = b'{"ok":false,"error":"crm_unreachable"}'
            self._send(502, msg, 'application/json')

    def _send(self, code, body, ct):
        self.send_response(code)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

def main():
    host = os.environ.get('WEB_BIND', '127.0.0.1')
    if host not in ('127.0.0.1', '::1', 'localhost') and os.environ.get('WEB_ALLOW_PUBLIC_BIND') != '1':
        raise SystemExit(f'Refusing to bind {host}. Local default is 127.0.0.1.')
    print(f'Bernvapes Website: http://{host}:{PORT}', flush=True)
    print(f'Händlerportal:     http://{host}:{PORT}/haendler.html', flush=True)
    print(f'CRM upstream:      {UPSTREAM}', flush=True)
    ThreadingHTTPServer((host, PORT), H).serve_forever()

if __name__ == '__main__':
    main()
