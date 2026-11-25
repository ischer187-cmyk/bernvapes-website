"""B2C checkout: cart → order on the customer → PostFinance payment page.

Pre-order bottles (Lemon Pie, Mango Lassi, Mandarine Nuss, Apple Pie) use the
same payment. The line is stored with preorder=1. Prices come from the product
table (price_einstieg), never from the browser.
"""
import datetime, hashlib, hmac, json, logging, os, re
from bexio_sync import sync_paid_order
from db import IntegrityError
from mailer import SHIP_NOTICE, deliver, order_mail
import postfinance
from shipping import FREE_SHIPPING_THRESHOLD_CHF, SHIPPING_FEE_CHF, VAT_RATE, shipping_for

PREORDER_SKUS = ('lemon-pie', 'mango-lassi', 'mandarine-nuss', 'apple-pie')
PAID_STATES = ('FULFILL', 'COMPLETED')
FAIL_STATES = ('FAILED', 'DECLINE', 'VOIDED')
WEBHOOK_PATH = '/webhook/postfinance'
_TX = re.compile(r'^\d{1,18}$')
_BIRTH = re.compile(r'^(\d{2})\.(\d{2})\.(\d{4})$')
NOTICE_ALL = 'Vor dem Versand wird die Altersverifikation durchgeführt.'
NOTICE_NEW = (
    'Nach der Bestellung prüfen wir dein Alter anhand eines amtlichen Ausweises, '
    'zum Beispiel in einem kurzen Videoanruf. Ein Bild des Ausweises speichern wir nicht.'
)
AGE_OPEN = 'Altersprüfung offen'
AGE_MESSAGES = {
    'underage': 'Du musst mindestens 18 Jahre alt sein.',
    'birthdate_invalid': 'Bitte Geburtsdatum als TT.MM.JJJJ angeben.',
    'age_confirm_required': 'Bitte bestätige, dass du 18 Jahre oder älter bist.',
    'terms_required': 'Bitte akzeptiere die AGB und die Datenschutzerklärung.',
}
GUEST_CHANNEL = 'website-gast'
GUEST_TAGS = 'B2C,Gast'
_EMAIL = re.compile(r'^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$')
_ZIP = re.compile(r'^\d{4}$')
GUEST_MESSAGES = {
    'guest_invalid': 'Bitte Name, E-Mail und Lieferadresse vollständig angeben.',
    'dealer_email': 'Diese E-Mail gehört zu einem Händlerkonto. Bitte im Händlerportal bestellen.',
    'rate_limited': 'Zu viele Versuche. Bitte kurz warten.',
}


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


def _truthy(value):
    return value in (True, 1, '1', 'true', 'True', 'on', 'ja', 'yes', 'oui')


def parse_birthdate(value):
    match = _BIRTH.match((value or '').strip())
    if not match:
        raise CheckoutError(422, 'birthdate_invalid')
    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    try:
        born = datetime.date(year, month, day)
    except ValueError:
        raise CheckoutError(422, 'birthdate_invalid')
    if born > datetime.date.today():
        raise CheckoutError(422, 'birthdate_invalid')
    return born.strftime('%d.%m.%Y'), born


def assert_adult(data):
    """Pflicht: Geburtsdatum, Alters-Häkchen und AGB. Alter mindestens 18."""
    if not isinstance(data, dict) or not _truthy(data.get('age_confirmed')):
        raise CheckoutError(422, 'age_confirm_required')
    text, born = parse_birthdate(data.get('birthdate'))
    today = datetime.date.today()
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    if age < 18:
        raise CheckoutError(422, 'underage')
    if not _truthy(data.get('terms_accepted')):
        raise CheckoutError(422, 'terms_required')
    return text


def _customer(conn, account):
    return conn.execute('select * from customers where id=?', (account['customer_id'],)).fetchone()


def _verified(cust):
    return bool(cust and cust['age_verified'])


def notices_for(conn, account):
    notes = [SHIP_NOTICE, NOTICE_ALL]
    if not _verified(_customer(conn, account)):
        notes.append(NOTICE_NEW)
    return notes


def order_notices(order):
    notes = [SHIP_NOTICE, NOTICE_ALL]
    if (order['age_check_status'] or '') == AGE_OPEN:
        notes.append(NOTICE_NEW)
    return notes


def public_catalog(conn):
    rows = conn.execute(
        'select sku,name,price_einstieg from products where coalesce(active,1)=1 order by name'
    ).fetchall()
    return {
        'ok': True,
        'currency': 'CHF',
        'shipping_fee_chf': SHIPPING_FEE_CHF,
        'free_shipping_threshold_chf': FREE_SHIPPING_THRESHOLD_CHF,
        'vat_rate': VAT_RATE,
        'products': [{
            'sku': r['sku'], 'name': r['name'], 'price_chf': round(float(r['price_einstieg']), 2),
        } for r in rows],
    }


def _totals(lines):
    subtotal = round(sum(row['line_chf'] for row in lines), 2)
    shipping = shipping_for(subtotal)
    total = round(subtotal + shipping, 2)
    remaining = 0.0 if shipping == 0 else round(FREE_SHIPPING_THRESHOLD_CHF - subtotal, 2)
    return subtotal, shipping, total, remaining


def _money_fields(subtotal, shipping, total, remaining):
    return {
        'subtotal_chf': subtotal,
        'shipping_chf': shipping,
        'total_chf': total,
        'free_shipping': shipping == 0,
        'remaining_to_free_chf': remaining,
        'shipping_fee_chf': SHIPPING_FEE_CHF,
        'free_shipping_threshold_chf': FREE_SHIPPING_THRESHOLD_CHF,
        'vat_rate': VAT_RATE,
        'currency': 'CHF',
    }


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
    lines, _goods = price_items(conn, items)
    subtotal, shipping, total, remaining = _totals(lines)
    body = {
        'ok': True, 'preview': True,
        'items': _public_lines(lines), 'customer_id': account['customer_id'],
        'needs_age_check': not _verified(_customer(conn, account)),
        'notices': notices_for(conn, account),
    }
    body.update(_money_fields(subtotal, shipping, total, remaining))
    return body


def _split_name(name):
    parts = (name or '').split()
    if len(parts) >= 2:
        return parts[0], ' '.join(parts[1:])
    if parts:
        return parts[0], parts[0]
    return 'Kunde', 'Kunde'


def place(conn, account, items, data=None, guest=False):
    if not postfinance.configured():
        raise CheckoutError(503, 'postfinance_not_configured')
    lines, _goods = price_items(conn, items)
    birth = assert_adult(data or {})
    subtotal, shipping, total, remaining = _totals(lines)
    if guest:
        account = dict(account, customer_id=_guest_customer(conn, account), id=None)
    cid = account['customer_id']
    aid = account['id']
    email = (account['email'] or '').strip().lower()
    cust = _customer(conn, account)
    age_status = None if _verified(cust) else AGE_OPEN
    test_flag = 1 if postfinance.is_test_mode() else 0
    oid = conn.execute(
        """insert into orders(customer_id,customer_account_id,channel,status,total_chf,shipping_chf,birthdate,
           age_check_status,payment_status,payment_provider,currency,is_test,payment_method,updated_at)
           values(?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
        (cid, aid, GUEST_CHANNEL if guest else 'website', 'offen', total, shipping, birth, age_status,
         'offen', 'postfinance', 'CHF', test_flag, 'postfinance')).lastrowid
    ref = 'bv-%s' % oid
    conn.execute('update orders set external_ref=? where id=?', (ref, oid))
    conn.execute(
        "update customers set birthdate=?, updated_at=datetime('now') where id=?",
        (birth, cid))
    for row in lines:
        conn.execute(
            'insert into order_items(order_id,article,qty,unit_chf,bottle_ml,preorder,sku) values(?,?,?,?,?,?,?)',
            (oid, row['name'], row['qty'], row['unit_chf'], row['bottle_ml'], 1 if row['preorder'] else 0, row['sku']))
    names = ', '.join('%s%s' % (row['name'], ' (Vorbestellung)' if row['preorder'] else '') for row in lines)
    ship_note = 'Versand gratis' if shipping == 0 else 'Versand CHF %.2f' % shipping
    test_tag = ' [TEST]' if test_flag else ''
    conn.execute(
        'insert into notes(customer_id,channel,direction,body,author) values(?,?,?,?,?)',
        (cid, 'website', 'in', 'Shop-Kasse #%s %s · CHF %.2f (%s)%s. %s' % (oid, ref, total, ship_note, test_tag, names), 'Shop'))
    if guest:
        conn.execute(
            'insert into notes(customer_id,channel,direction,body,author) values(?,?,?,?,?)',
            (cid, 'notiz', 'in',
             'Gastbestellung #%s ohne Kundenkonto. Lieferadresse: %s, %s %s.' % (
                 oid, account['address'], account['zip'], account['city']),
             'Shop'))
    if age_status == AGE_OPEN:
        conn.execute(
            'insert into notes(customer_id,channel,direction,body,author) values(?,?,?,?,?)',
            (cid, 'notiz', 'in',
             'Altersprüfung offen. Versand gesperrt. Persönlich melden für die Altersverifizierung. Keine Ausweisbilder speichern.',
             'Shop'))
    conn.commit()
    given, family = _split_name(account['name'])
    payload = {
        'currency': 'CHF',
        'language': 'de-CH',
        'merchantReference': ref,
        'invoiceMerchantReference': ref,
        'customerEmailAddress': email,
        'successUrl': '%s/kasse-ok.html?ref=%s%s' % (_public(), ref, _guest_q(ref) if guest else ''),
        'failedUrl': '%s/kasse-fail.html?ref=%s%s' % (_public(), ref, _guest_q(ref) if guest else ''),
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
        'lineItems': _wallee_lines(lines, shipping),
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
    body = {
        'ok': True, 'order_id': oid, 'ref': ref, 'paymentUrl': url, 'integrationMode': 'PaymentPage',
        'test': bool(test_flag), 'items': _public_lines(lines),
        'needs_age_check': age_status == AGE_OPEN,
        'age_check_status': age_status,
        'notices': order_notices({'age_check_status': age_status}),
    }
    if guest:
        body['guest'] = True
        token = guest_token(ref)
        if token:
            body['guest_token'] = token
    body.update(_money_fields(subtotal, shipping, total, remaining))
    _mail_received(conn, oid, ref, lines, shipping, total, account, guest=guest)
    return body


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
        'aggregatedTaxRate': VAT_RATE,
    }


def _wallee_lines(lines, shipping):
    out = [_wallee_line(row) for row in lines]
    if shipping > 0:
        out.append({
            'uniqueId': 'versand',
            'sku': 'versand',
            'name': 'Versand',
            'quantity': 1,
            'amountIncludingTax': round(float(shipping), 2),
            'type': 'SHIPPING',
            'aggregatedTaxRate': VAT_RATE,
        })
    return out


def customer_checkout(handler, conn, account, data):
    try:
        if data.get('preview'):
            return handler.json(200, quote(conn, account, data.get('items')))
        return handler.json(200, place(conn, account, data.get('items'), data))
    except CheckoutError as ex:
        body = {'ok': False, 'error': ex.code}
        if ex.code in AGE_MESSAGES:
            body['message'] = AGE_MESSAGES[ex.code]
        return handler.json(ex.status, body)
    except postfinance.PostFinanceError:
        return handler.json(502, {'ok': False, 'error': 'postfinance_failed'})


def guest_profile(data):
    """Pflichtangaben für die Gastbestellung. Nur Schweizer Lieferadressen (PLZ 4-stellig)."""
    raw = data.get('guest') if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        raise CheckoutError(422, 'guest_invalid')
    def val(key, limit=200):
        return str(raw.get(key) or '').strip()[:limit]
    g = {
        'name': ' '.join(val('name').split()),
        'email': val('email', 254).lower(),
        'address': val('address'),
        'zip': val('zip', 10),
        'city': val('city', 100),
        'phone': val('phone', 40),
    }
    bad = []
    if len(g['name']) < 2 or len(g['name'].split()) < 2:
        bad.append('name')
    if not _EMAIL.match(g['email']):
        bad.append('email')
    if len(g['address']) < 3:
        bad.append('address')
    if not _ZIP.match(g['zip']):
        bad.append('zip')
    if len(g['city']) < 2:
        bad.append('city')
    if bad:
        ex = CheckoutError(422, 'guest_invalid')
        ex.fields = bad
        raise ex
    return g


def _guest_customer(conn, g):
    """CRM-Kontakt für den Gast: bestehenden Endkunden per E-Mail weiterverwenden, sonst neu anlegen.
    Ein Kontakt mit Kundenkonto wird nicht überschrieben. Händler-E-Mails sind gesperrt."""
    email = g['email']
    if conn.execute('select 1 from dealer_accounts where lower(email)=?', (email,)).fetchone():
        raise CheckoutError(409, 'dealer_email')
    row = conn.execute(
        'select id, customer_type, extra, tags from customers where lower(email)=? order by id limit 1',
        (email,)).fetchone()
    if row and row['customer_type'] not in ('Endkunde', None, ''):
        raise CheckoutError(409, 'dealer_email')
    has_account = conn.execute(
        'select 1 from customer_accounts where lower(email)=?', (email,)).fetchone()
    if row:
        if not has_account:
            try:
                extra = json.loads(row['extra'] or '{}')
                if not isinstance(extra, dict):
                    extra = {}
            except ValueError:
                extra = {}
            extra.update({'gast': True, 'zip': g['zip']})
            tags = row['tags'] or ''
            if 'Gast' not in tags.split(','):
                tags = (tags + ',Gast') if tags else GUEST_TAGS
            conn.execute(
                """update customers set name=?, address=?, city=?, phone=coalesce(nullif(?,''),phone),
                   extra=?, tags=?, updated_at=datetime('now') where id=?""",
                (g['name'], g['address'], g['city'], g.get('phone') or '', json.dumps(extra, ensure_ascii=False), tags, row['id']))
        return row['id']
    return conn.execute(
        """insert into customers(name,email,phone,customer_type,address,city,age_verify_method,age_verified,source,tags,extra)
           values(?,?,?,'Endkunde',?,?,'checkbox',0,'website',?,?)""",
        (g['name'], email, g.get('phone') or None, g['address'], g['city'], GUEST_TAGS,
         json.dumps({'gast': True, 'zip': g['zip']}, ensure_ascii=False))).lastrowid


def _guest_key():
    secret = os.environ.get('CRM_GUEST_ORDER_SECRET') or os.environ.get('CRM_WEBHOOK_SECRET') or ''
    return secret.encode('utf-8') if secret else b''


def guest_token(ref):
    """Zugriffsschlüssel für die Bestellbestätigung ohne Login. Ohne Server-Secret kein Token."""
    key = _guest_key()
    if not key:
        return ''
    return hmac.new(key, ('guest-order:' + ref).encode('utf-8'), hashlib.sha256).hexdigest()[:32]


def _guest_q(ref):
    token = guest_token(ref)
    return '&g=%s' % token if token else ''


def guest_checkout(handler, conn, data):
    try:
        if data.get('preview'):
            body = quote(conn, {'id': None, 'customer_id': None}, data.get('items'))
            body['guest'] = True
            body.pop('customer_id', None)
            return handler.json(200, body)
        g = guest_profile(data)
        account = {'id': None, 'customer_id': None, 'email': g['email'], 'name': g['name'],
                   'address': g['address'], 'zip': g['zip'], 'city': g['city'], 'phone': g['phone']}
        return handler.json(200, place(conn, account, data.get('items'), data, guest=True))
    except CheckoutError as ex:
        conn.rollback()
        body = {'ok': False, 'error': ex.code}
        if ex.code in AGE_MESSAGES:
            body['message'] = AGE_MESSAGES[ex.code]
        elif ex.code in GUEST_MESSAGES:
            body['message'] = GUEST_MESSAGES[ex.code]
        if getattr(ex, 'fields', None):
            body['fields'] = ex.fields
        return handler.json(ex.status, body)
    except postfinance.PostFinanceError:
        return handler.json(502, {'ok': False, 'error': 'postfinance_failed'})


def guest_order(handler, conn):
    """Status einer Gastbestellung für kasse-ok.html. Nur mit gültigem Token, ohne Adresse und Geburtsdatum."""
    from urllib.parse import parse_qs, urlparse
    q = parse_qs(urlparse(handler.path).query)
    ref = (q.get('ref') or [''])[0].strip()
    token = (q.get('g') or [''])[0].strip()
    if not re.fullmatch(r'bv-\d{1,18}', ref or ''):
        return handler.json(422, {'ok': False, 'error': 'invalid_ref'})
    want = guest_token(ref)
    if not want or not token or not hmac.compare_digest(want, token):
        return handler.json(404, {'ok': False, 'error': 'not_found'})
    order = conn.execute(
        'select * from orders where external_ref=? and channel=?', (ref, GUEST_CHANNEL)).fetchone()
    if not order:
        return handler.json(404, {'ok': False, 'error': 'not_found'})
    items = conn.execute('select article,qty,preorder from order_items where order_id=?', (order['id'],)).fetchall()
    shipping = round(float(order['shipping_chf'] or 0), 2)
    total = round(float(order['total_chf'] or 0), 2)
    return handler.json(200, {
        'ok': True, 'guest': True, 'ref': ref,
        'payment_status': order['payment_status'],
        'shipping_chf': shipping, 'total_chf': total,
        'currency': order['currency'] or 'CHF',
        'test': bool(order['is_test']),
        'needs_age_check': (order['age_check_status'] or '') == AGE_OPEN,
        'notices': order_notices(order),
        'items': [{'name': i['article'], 'qty': i['qty'], 'preorder': bool(i['preorder'])} for i in items],
    })


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
    shipping = round(float(order['shipping_chf'] or 0), 2)
    total = round(float(order['total_chf'] or 0), 2)
    return handler.json(200, {
        'ok': True,
        'ref': ref,
        'order_id': order['id'],
        'status': order['status'],
        'payment_status': order['payment_status'],
        'postfinance_state': order['postfinance_state'],
        'subtotal_chf': round(total - shipping, 2),
        'shipping_chf': shipping,
        'total_chf': total,
        'currency': order['currency'] or 'CHF',
        'test': bool(order['is_test']),
        'birthdate': order['birthdate'],
        'age_check_status': order['age_check_status'],
        'needs_age_check': (order['age_check_status'] or '') == AGE_OPEN,
        'notices': order_notices(order),
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


def _mail_received(conn, oid, ref, lines, shipping, total, account, guest=False):
    """Eingangsbestätigung sofort nach der Bestellung (UWG). Ein Mailfehler macht die Bestellung nicht rückgängig."""
    email = (account['email'] or '').strip()
    name = account['name'] or ''
    if not email:
        logging.getLogger('bernvapes.mail').error('Eingangsbestätigung #%s ohne E-Mail', oid)
        return
    payload = [{
        'name': row['name'], 'qty': row['qty'], 'preorder': bool(row['preorder']),
    } for row in lines]
    subject, body = order_mail(name, ref, payload, shipping, total)
    if guest:
        hint = (
            'Du hast als Gast bestellt, ohne Kundenkonto. Wenn du später mit dieser E-Mail '
            'ein Konto anlegst, siehst du deine Bestellungen dort: %s/konto.html?neu=1\n\n' % _public())
        body = body.replace('Freundliche Grüsse', hint + 'Freundliche Grüsse', 1)
    order = conn.execute('select customer_id from orders where id=?', (oid,)).fetchone()
    if deliver(conn, email, subject, body):
        return
    if order:
        conn.execute(
            'insert into notes(customer_id,channel,body,author) values(?,?,?,?)',
            (order['customer_id'], 'notiz',
             'Eingangsbestätigung an %s nicht gesendet. Details im Server-Log.' % email, 'System'))
        conn.commit()


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
