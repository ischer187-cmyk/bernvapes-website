"""PostFinance Checkout (Wallee REST) for the local test.

MAC: HMAC-SHA512 over ``version|userId|unixTime|METHOD|path``, key = base64-decoded
POSTFINANCE_SPACE_KEY. Headers x-mac-version, x-mac-userid, x-mac-timestamp, x-mac-value.

Cloudflare answers 1010 to the default Python-urllib User-Agent. Every call sends
``User-Agent: bernvapes-crm/1.0``. The space key is never logged and never put in an error.
"""
import base64, hashlib, hmac, json, os, re, time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER_AGENT = 'bernvapes-crm/1.0'
API_BASE = 'https://checkout.postfinance.ch'
_DIGITS = re.compile(r'^\d{1,18}$')
_transport = None


class PostFinanceError(Exception):
    pass


def set_transport(fn):
    """Test hook. Replaces urlopen. None restores the real client."""
    global _transport
    _transport = fn


def space_id():
    return (os.environ.get('POSTFINANCE_SPACE_ID') or '').strip()


def user_id():
    return (os.environ.get('POSTFINANCE_USER_ID') or '').strip()


def space_key():
    return (os.environ.get('POSTFINANCE_SPACE_KEY') or '').strip()


def configured():
    return bool(space_id() and user_id() and space_key())


def mac_value(method, path, user, secret_b64, unix_time, version='1'):
    """Base64 HMAC-SHA512. The secret is decoded before it is used as the key."""
    msg = '%s|%s|%s|%s|%s' % (version, user, int(unix_time), method.upper(), path)
    try:
        key = base64.b64decode(secret_b64, validate=True)
    except Exception as ex:
        raise PostFinanceError('postfinance key invalid') from ex
    if not key:
        raise PostFinanceError('postfinance key invalid')
    digest = hmac.new(key, msg.encode('utf-8'), hashlib.sha512).digest()
    return base64.b64encode(digest).decode('ascii')


def mac_headers(method, path, user, secret_b64, unix_time):
    version = '1'
    return {
        'x-mac-version': version,
        'x-mac-userid': str(user),
        'x-mac-timestamp': str(int(unix_time)),
        'x-mac-value': mac_value(method, path, user, secret_b64, unix_time, version),
    }


class MacRequest(Request):
    """Keep header spelling, and treat names as case-insensitive.

    urllib adds ``User-agent: Python-urllib/x.y`` when ``has_header('User-agent')``
    is false. That value is what Cloudflare rejects with error 1010.
    """

    def add_header(self, key, val):
        self.headers[key] = val
        self.unredirected_hdrs[key] = val

    def has_header(self, header_name):
        want = header_name.lower()
        for key in list(self.headers.keys()) + list(self.unredirected_hdrs.keys()):
            if key.lower() == want:
                return True
        return False


def _api_base():
    return (os.environ.get('POSTFINANCE_API_BASE') or API_BASE).rstrip('/')


def _id(label, value):
    text = str(value if value is not None else '').strip()
    if not _DIGITS.match(text):
        raise PostFinanceError('postfinance %s invalid' % label)
    return text


def request_json(method, path, body=None, unix_time=None):
    if not configured():
        raise PostFinanceError('postfinance not configured')
    user = _id('user', user_id())
    _id('space', space_id())
    secret = space_key()
    if unix_time is None:
        unix_time = int(time.time())
    method = method.upper()
    data = None if body is None else json.dumps(body).encode('utf-8')
    headers = mac_headers(method, path, user, secret, unix_time)
    headers['Accept'] = 'application/json'
    headers['User-Agent'] = USER_AGENT
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = MacRequest(_api_base() + path, data=data, headers=headers, method=method)
    fn = _transport or urlopen
    try:
        resp = fn(req, timeout=30)
    except HTTPError as ex:
        raise PostFinanceError('postfinance http %s' % ex.code) from ex
    except URLError as ex:
        raise PostFinanceError('postfinance unreachable') from ex
    try:
        raw = resp.read()
        code = getattr(resp, 'status', None) or getattr(resp, 'code', 200)
    finally:
        close = getattr(resp, 'close', None)
        if close:
            close()
    if code and int(code) >= 400:
        raise PostFinanceError('postfinance http %s' % code)
    return _parse(raw)


def _parse(raw):
    text = (raw or b'').decode('utf-8').strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return text


def read_space():
    """GET /api/space/read — the call verified against the test space."""
    return request_json('GET', '/api/space/read?spaceId=%s' % _id('space', space_id()))


def search_payment_methods():
    """POST /api/payment-method-configuration/search — verified with the same MAC and User-Agent."""
    path = '/api/payment-method-configuration/search?spaceId=%s' % _id('space', space_id())
    return request_json('POST', path, {})


def create_transaction(payload):
    path = '/api/transaction/create?spaceId=%s' % _id('space', space_id())
    data = request_json('POST', path, payload)
    if not isinstance(data, dict) or data.get('id') is None:
        raise PostFinanceError('postfinance transaction missing')
    return data


def payment_page_url(transaction_id):
    """Hosted payment page. This is integrationMode PaymentPage (full redirect)."""
    path = '/api/transaction-payment-page/payment-page-url?spaceId=%s&id=%s' % (
        _id('space', space_id()), _id('transaction', transaction_id))
    data = request_json('GET', path)
    if isinstance(data, str) and data.startswith('http'):
        return data
    if isinstance(data, dict):
        for key in ('url', 'paymentPageUrl'):
            if isinstance(data.get(key), str) and data[key].startswith('http'):
                return data[key]
    raise PostFinanceError('postfinance payment page missing')


def read_transaction(transaction_id):
    path = '/api/transaction/read?spaceId=%s&id=%s' % (
        _id('space', space_id()), _id('transaction', transaction_id))
    data = request_json('GET', path)
    if not isinstance(data, dict):
        raise PostFinanceError('postfinance transaction missing')
    return data
