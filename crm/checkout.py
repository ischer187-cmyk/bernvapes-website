"""B2C checkout: cart → order on the customer → PostFinance payment page.

Pre-order bottles (Lemon Pie, Mango Lassi, Mandarine Nuss, Apple Pie) use the
same payment. The line is stored with preorder=1. Prices come from the product
table (price_einstieg), never from the browser.
"""
import os, re
from bexio_sync import sync_paid_order
from db import IntegrityError
import postfinance

PREORDER_SKUS = ('lemon-pie', 'mango-lassi', 'mandarine-nuss', 'apple-pie')
PAID_STATES = ('FULFILL', 'COMPLETED')
FAIL_STATES = ('FAILED', 'DECLINE', 'VOIDED')
WEBHOOK_PATH = '/webhook/postfinance'
_TX = re.compile(r'^\d{1,18}$')


class CheckoutError(Exception):
    def __init__(self, status, code):
        self.status = status
        self.code = code
        Exception.__init__(self, code)


def _public():
    return (os.environ.get('WEBSITE_PUBLIC_URL') or 'http://127.0.0.1:8080').rstrip('/')


def _fold(value):
    s = (value or '').lower().replace('·', ' ')
    for src, dst in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')):
        s = s.replace(src, dst)
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def _from_key(value):
    k = (value or '').lower().strip()
    k = re.sub(r'_(100|60)ml$', '', k)
    k = k.replace('_otr', ' uf ys')
    return _fold(k)


def _catalog(conn):
    rows = conn.execute('select * from products where coalesce(active,1)=1').fetchall()
    by = {}
    for row in rows:
        by[_fold(row['name'])] = row
        by[_fold(row['sku'])] = row
    return by


def _resolve(by, item):
    for raw in (item.get('sku'), item.get('id'), item.get('name')):
        if not raw:
            continue
        hit = by.get(_fold(raw)) or by.get(_from_key(raw))
        if hit:
            return hit
    return None


def price_items(conn, items):
    if not isinstance(items, list) or not items:
        raise CheckoutError(422, 'empty_cart')
    by = _catalog(conn)
    merged = {}
    order = []
    for item in items:
        if not isinstance(item, dict):
            raise CheckoutError(422, 'unknown_item')
        prod = _resolve(by, item)
        if not prod:
            raise CheckoutError(422, 'unknown_item')
        try:
            qty = int(item.get('qty') or 1)
        except (TypeError, ValueError):
            raise CheckoutError(422, 'invalid_qty')
        if qty < 1 or qty > 99:
            raise CheckoutError(422, 'invalid_qty')
        sku = prod['sku']
        if sku not in merged:
            merged[sku] = {'sku': sku, 'name': prod['name'], 'qty': 0, 'unit_chf': round(float(prod['price_einstieg']), 2),
                           'bottle_ml': prod['bottle_ml'], 'preorder': sku in PREORDER_SKUS}
            order.append(sku)
        merged[sku]['qty'] += qty
        if merged[sku]['qty'] > 99:
            raise CheckoutError(422, 'invalid_qty')
    lines = []
    for sku in order:
        row = merged[sku]
        row['line_chf'] = round(row['qty'] * row['unit_chf'], 2)
        lines.append(row)
    total = round(sum(row['line_chf'] for row in lines), 2)
    return lines, total


def _public_lines(lines):
    out = []
    for row in lines:
        out.append({
            'sku': row['sku'], 'name': row['name'], 'qty': row['qty'], 'unit_chf': row['unit_chf'],
            'line_chf': row['line_chf'], 'preorder': bool(row['preorder']),
        })
    return out


def quote(conn, account, items):
    lines, total = price_items(conn, items)
    return {
        'ok': True, 'preview': True, 'total_chf': total, 'currency': 'CHF',
        'items': _public_lines(lines), 'customer_id': account['customer_id'],
    }


def _split_name(name):
    parts = (name or '').split()
    if len(parts) >= 2:
        return parts[0], ' '.join(parts[1:])
    if parts:
        return parts[0], parts[0]
    return 'Kunde', 'Kunde'


def place(conn, account, items):
    if not postfinance.configured():
        raise CheckoutError(503, 'postfinance_not_configured')
    lines, total = price_items(conn, items)
    cid = account['customer_id']
    aid = account['id']
    email = (account['email'] or '').strip().lower()
    oid = conn.execute(
        """insert into orders(customer_id,customer_account_id,channel,status,total_chf,payment_status,payment_provider,
           currency,is_test,payment_method,updated_at) values(?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
        (cid, aid, 'website', 'offen', total, 'offen', 'postfinance', 'CHF', 1, 'postfinance')).lastrowid
    ref = 'bv-%s' % oid
    conn.execute('update orders set external_ref=? where id=?', (ref, oid))
    for row in lines:
        conn.execute(
            'insert into order_items(order_id,article,qty,unit_chf,bottle_ml,preorder) values(?,?,?,?,?,?)',
            (oid, row['name'], row['qty'], row['unit_chf'], row['bottle_ml'], 1 if row['preorder'] else 0))
    names = ', '.join('%s%s' % (row['name'], ' (Vorbestellung)' if row['preorder'] else '') for row in lines)
    conn.execute(
        'insert into notes(customer_id,channel,direction,body,author) values(?,?,?,?,?)',
        (cid, 'website', 'in', 'Shop-Kasse #%s %s · CHF %.2f [TEST]. %s' % (oid, ref, total, names), 'Shop'))
    conn.commit()
    given, family = _split_name(account['name'])
    payload = {
        'currency': 'CHF',
        'language': 'de-CH',
        'merchantReference': ref,
        'invoiceMerchantReference': ref,
        'customerEmailAddress': email,
        'successUrl': '%s/kasse-ok.html?ref=%s' % (_public(), ref),
        'failedUrl': '%s/kasse-fail.html?ref=%s' % (_public(), ref),
        'billingAddress': {
            'givenName': given,
            'familyName': family,
            'street': account['address'] or '-',
            'postcode': account['zip'] or '0000',
            'city': account['city'] or '-',
            'country': 'CH',
            'emailAddress': email,
        },
        'metaData': {'orderId': str(oid), 'integrationMode': 'PaymentPage'},
        'lineItems': [_wallee_line(row) for row in lines],
    }
    try:
        tx = postfinance.create_transaction(payload)
        url = postfinance.payment_page_url(tx['id'])
    except postfinance.PostFinanceError:
        conn.execute(
            "update orders set status='fehler', payment_status='fehler', updated_at=datetime('now') where id=?",
            (oid,))
        conn.commit()
        raise
    tx_id = str(tx['id'])
    conn.execute(
        "update orders set postfinance_tx_id=?, payment_tx_id=?, postfinance_state=?, updated_at=datetime('now') where id=?",
        (tx_id, tx_id, tx.get('state') or 'PENDING', oid))
    conn.commit()
    return {
        'ok': True, 'order_id': oid, 'ref': ref, 'paymentUrl': url, 'integrationMode': 'PaymentPage',
        'total_chf': total, 'currency': 'CHF', 'test': True, 'items': _public_lines(lines),
    }


def _wallee_line(row):
    name = row['name']
    if row['preorder']:
        name = '%s (Vorbestellung)' % name
    return {
        'uniqueId': row['sku'],
        'sku': row['sku'],
        'name': name,
        'quantity': row['qty'],
        'amountIncludingTax': row['line_chf'],
        'type': 'PRODUCT',
    }


def customer_checkout(handler, conn, account, data):
    try:
        if data.get('preview'):
            return handler.json(200, quote(conn, account, data.get('items')))
        return handler.json(200, place(conn, account, data.get('items')))
    except CheckoutError as ex:
        return handler.json(ex.status, {'ok': False, 'error': ex.code})
    except postfinance.PostFinanceError:
        return handler.json(502, {'ok': False, 'error': 'postfinance_failed'})


def customer_order(handler, conn, account):
    from urllib.parse import parse_qs, urlparse
    ref = (parse_qs(urlparse(handler.path).query).get('ref') or [''])[0].strip()
    if not re.fullmatch(r'bv-\d{1,18}', ref or ''):
        return handler.json(422, {'ok': False, 'error': 'invalid_ref'})
    order = conn.execute(
        'select * from orders where external_ref=? and customer_id=?',
        (ref, account['customer_id'])).fetchone()
    if not order:
        return handler.json(404, {'ok': False, 'error': 'not_found'})
    items = conn.execute('select article,qty,unit_chf,preorder from order_items where order_id=?', (order['id'],)).fetchall()
    return handler.json(200, {
        'ok': True,
        'ref': ref,
        'order_id': order['id'],
        'status': order['status'],
        'payment_status': order['payment_status'],
        'postfinance_state': order['postfinance_state'],
        'total_chf': order['total_chf'],
        'currency': order['currency'] or 'CHF',
        'test': bool(order['is_test']),
        'items': [{
            'name': i['article'], 'qty': i['qty'], 'unit_chf': i['unit_chf'], 'preorder': bool(i['preorder']),
        } for i in items],
    })


def apply_webhook(conn, data):
    """Wallee notification. The paid flag is taken from the transaction we read, not from the body alone."""
    if not isinstance(data, dict):
        return 400, {'ok': False, 'error': 'invalid json'}
    if not postfinance.configured():
        return 503, {'ok': False, 'error': 'postfinance_not_configured'}
    if data.get('listenerEntityTechnicalName') not in (None, '', 'Transaction'):
        return 200, {'ok': True, 'status': 'ignored'}
    if 'spaceId' in data and str(data.get('spaceId')) != postfinance.space_id():
        return 422, {'ok': False, 'error': 'space'}
    entity = str(data.get('entityId') if data.get('entityId') is not None else '').strip()
    if not _TX.match(entity):
        return 422, {'ok': False, 'error': 'invalid_entity'}
    event_id = str(data.get('eventId') or ('tx-%s-%s' % (entity, data.get('state') or 'read')))
    begun = _event_begin(conn, event_id)
    if begun == 'duplicate':
        return 200, {'ok': True, 'status': 'duplicate', 'event_id': event_id}
    try:
        tx = postfinance.read_transaction(entity)
    except postfinance.PostFinanceError:
        _event_status(conn, event_id, 'error')
        return 502, {'ok': False, 'error': 'postfinance_failed'}
    ref = str(tx.get('merchantReference') or '')
    order = conn.execute('select * from orders where external_ref=?', (ref,)).fetchone() if ref else None
    if not order or str(order['postfinance_tx_id'] or '') != str(tx.get('id')):
        _event_status(conn, event_id, 'error')
        return 422, {'ok': False, 'error': 'order_not_found'}
    state = str(tx.get('state') or '')
    conn.execute(
        "update orders set postfinance_state=?, updated_at=datetime('now') where id=?",
        (state, order['id']))
    bexio = None
    if state in PAID_STATES:
        conn.execute(
            "update orders set payment_status='bezahlt', status='bezahlt', updated_at=datetime('now') where id=?",
            (order['id'],))
        conn.execute(
            'insert into notes(customer_id,channel,body,author) values(?,?,?,?)',
            (order['customer_id'], 'notiz',
             'PostFinance %s bezahlt, Transaktion %s, Bestellung #%s beim Kunden.' % (state, entity, order['id']),
             'Webhook'))
        bexio = sync_paid_order(conn, order['id'])
        detail = bexio.get('detail') or bexio.get('status')
        conn.execute(
            'insert into notes(customer_id,channel,body,author) values(?,?,?,?)',
            (order['customer_id'], 'notiz', 'bexio Sync #%s: %s — %s' % (order['id'], bexio.get('status'), detail), 'System'))
        paid = 'paid'
    elif state in FAIL_STATES:
        conn.execute(
            "update orders set payment_status='fehlgeschlagen', status='fehlgeschlagen', updated_at=datetime('now') where id=?",
            (order['id'],))
        paid = 'failed'
    else:
        paid = 'pending'
    _event_status(conn, event_id, 'processed')
    body = {'ok': True, 'status': paid, 'order_id': order['id'], 'state': state, 'ref': ref}
    if bexio is not None:
        body['bexio'] = {'status': bexio.get('status'), 'created': bool(bexio.get('created'))}
    return 200, body


def _event_begin(conn, event_id):
    row = conn.execute(
        'select status from webhook_events where source=? and event_id=?',
        ('postfinance', event_id)).fetchone()
    if row and row['status'] == 'processed':
        return 'duplicate'
    try:
        if row:
            conn.execute(
                'update webhook_events set status=? where source=? and event_id=?',
                ('received', 'postfinance', event_id))
        else:
            conn.execute(
                'insert into webhook_events(source,event_id,status) values(?,?,?)',
                ('postfinance', event_id, 'received'))
        conn.commit()
    except IntegrityError:
        conn.rollback()
        return 'duplicate'
    return 'ok'


def _event_status(conn, event_id, status):
    conn.execute(
        'update webhook_events set status=? where source=? and event_id=?',
        (status, 'postfinance', event_id))
    conn.commit()
