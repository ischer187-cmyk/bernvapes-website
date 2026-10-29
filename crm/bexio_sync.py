"""Optional bexio customer + invoice after a paid shop order.

BEXIO_SYNC_ENABLED defaults off. BEXIO_API_TOKEN is read from the environment and
never written into notes, errors, or logs. This is separate from the B2B stub in
bexio_billing.py, which still never calls the network.
"""
import json, os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API = 'https://api.bexio.com'
_transport = None


def set_transport(fn):
    global _transport
    _transport = fn


def sync_enabled():
    return os.environ.get('BEXIO_SYNC_ENABLED', '0').strip().lower() in ('1', 'true', 'yes', 'on')


def _off(status, detail):
    return {'created': False, 'status': status, 'detail': detail}


def _request(token, path, body):
    data = json.dumps(body).encode('utf-8')
    req = Request(API + path, data=data, method='POST')
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Accept', 'application/json')
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', 'bernvapes-crm/1.0')
    fn = _transport or urlopen
    try:
        resp = fn(req, timeout=30)
    except HTTPError as ex:
        raise RuntimeError('bexio http %s' % ex.code) from ex
    except URLError as ex:
        raise RuntimeError('bexio unreachable') from ex
    try:
        raw = resp.read()
        code = getattr(resp, 'status', None) or getattr(resp, 'code', 200)
    finally:
        close = getattr(resp, 'close', None)
        if close:
            close()
    if code and int(code) >= 400:
        raise RuntimeError('bexio http %s' % code)
    try:
        parsed = json.loads(raw.decode('utf-8') or '{}')
    except ValueError as ex:
        raise RuntimeError('bexio invalid json') from ex
    if not isinstance(parsed, dict) or parsed.get('id') is None:
        raise RuntimeError('bexio response missing id')
    return parsed


def sync_paid_order(conn, order_id):
    if not sync_enabled():
        return _off('disabled', 'BEXIO_SYNC_ENABLED is off. No bexio request was made.')
    token = (os.environ.get('BEXIO_API_TOKEN') or '').strip()
    if not token:
        return _off('missing_token', 'BEXIO_API_TOKEN is empty. No bexio request was made.')
    user_raw = (os.environ.get('BEXIO_USER_ID') or '').strip()
    if not user_raw.isdigit():
        return _off('incomplete_config', 'BEXIO_USER_ID is empty. No bexio request was made.')
    order = conn.execute('select * from orders where id=?', (order_id,)).fetchone()
    if not order:
        return _off('missing_order', 'Order missing. No bexio request was made.')
    if order['bexio_order_id']:
        return {'created': False, 'status': 'exists', 'invoice_id': order['bexio_order_id'],
                'detail': 'Invoice already stored.'}
    cust = conn.execute('select * from customers where id=?', (order['customer_id'],)).fetchone()
    acc = conn.execute(
        'select address,zip,city from customer_accounts where customer_id=? order by id limit 1',
        (order['customer_id'],)).fetchone()
    items = conn.execute('select * from order_items where order_id=?', (order_id,)).fetchall()
    user_id = int(user_raw)
    owner_id = int((os.environ.get('BEXIO_OWNER_ID') or user_raw).strip())
    country_id = int((os.environ.get('BEXIO_COUNTRY_ID') or '1').strip() or '1')
    currency_id = int((os.environ.get('BEXIO_CURRENCY_ID') or '1').strip() or '1')
    try:
        contact_id = cust['bexio_contact_id'] if cust else None
        if not contact_id:
            contact_id = _create_contact(token, cust, acc, user_id, owner_id, country_id)
            conn.execute('update customers set bexio_contact_id=? where id=?', (contact_id, cust['id']))
        invoice_id = _create_invoice(token, order, items, contact_id, user_id, currency_id)
        conn.execute('update orders set bexio_order_id=? where id=?', (invoice_id, order_id))
    except RuntimeError as ex:
        return _off('error', str(ex))
    return {'created': True, 'status': 'created', 'contact_id': contact_id, 'invoice_id': invoice_id,
            'detail': 'bexio contact and invoice stored.'}


def _split_name(name):
    parts = (name or '').split()
    if not parts:
        return 'Kunde', 'Bernvapes'
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], ' '.join(parts[1:])


def _create_contact(token, cust, acc, user_id, owner_id, country_id):
    given, family = _split_name(cust['name'] if cust else '')
    body = {
        'contact_type_id': 2,
        'name_1': family,
        'name_2': given,
        'address': (cust['address'] if cust and cust['address'] else None) or (acc['address'] if acc else '') or '',
        'postcode': (acc['zip'] if acc and acc['zip'] else '') or '',
        'city': (cust['city'] if cust and cust['city'] else None) or (acc['city'] if acc else '') or '',
        'country_id': country_id,
        'mail': cust['email'] if cust else '',
        'user_id': user_id,
        'owner_id': owner_id,
    }
    return int(_request(token, '/2.0/contact', body)['id'])


def _create_invoice(token, order, items, contact_id, user_id, currency_id):
    positions = []
    for item in items:
        text = item['article'] or 'Artikel'
        if item['preorder']:
            text = '%s (Vorbestellung)' % text
        row = {
            'type': 'KbPositionCustom',
            'amount': str(int(item['qty'] or 1)),
            'unit_price': '%.2f' % float(item['unit_chf'] or 0),
            'text': text,
        }
        tax = (os.environ.get('BEXIO_TAX_ID') or '').strip()
        if tax.isdigit():
            row['tax_id'] = int(tax)
        positions.append(row)
    body = {
        'title': 'Bernvapes Bestellung #%s' % order['id'],
        'contact_id': int(contact_id),
        'user_id': user_id,
        'currency_id': currency_id,
        'mwst_type': 0 if (os.environ.get('BEXIO_TAX_ID') or '').strip().isdigit() else 2,
        'mwst_is_net': False,
        'api_reference': order['external_ref'] or ('bv-%s' % order['id']),
        'positions': positions,
    }
    return int(_request(token, '/2.0/kb_invoice', body)['id'])
