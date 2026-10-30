"""Paid shop order → bexio, order first.

Search or create the contact (street_name, house_number, postcode, city),
create kb_order, then an invoice from that order. With BEXIO_DELIVERY_ENABLED
(default off) a delivery note is created from the order, its PDF is mailed,
and a stock failure mails only the stock-alert recipient. The invoice is still
created. BEXIO_API_TOKEN and SMTP_PASS are never written into notes or errors.

docs.bexio.com: POST /2.0/kb_order/{id}/delivery and POST /2.0/kb_order/{id}/invoice.
PDF for orders and invoices is GET .../pdf with JSON {name,mime,content}. The
public docs page does not list a delivery PDF; we call GET /2.0/kb_delivery/{id}/pdf
in that same shape. bexio documents no kb_order webhook.
"""
import base64, json, os, re, smtplib
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API = 'https://api.bexio.com'
STOCK_HINT = 'Lieferschein fehlgeschlagen – Bestand pruefen'
DEFAULT_DELIVERY_RECIPIENTS = 'mail@vapelounge.ch,daniela@bernvapes.ch'
DEFAULT_STOCK_RECIPIENT = 'daniela@bernvapes.ch'
_HOUSE = re.compile(r'^(?P<street>.*\D)\s+(?P<house>\d[\w/-]*)$')
_transport = None
_mail_transport = None


class BexioError(RuntimeError):
    def __init__(self, message, body='', code=None):
        self.body = body or ''
        self.code = code
        RuntimeError.__init__(self, message)


def set_transport(fn):
    global _transport
    _transport = fn


def set_mail_transport(fn):
    global _mail_transport
    _mail_transport = fn


def sync_enabled():
    return os.environ.get('BEXIO_SYNC_ENABLED', '0').strip().lower() in ('1', 'true', 'yes', 'on')


def delivery_enabled():
    return os.environ.get('BEXIO_DELIVERY_ENABLED', '0').strip().lower() in ('1', 'true', 'yes', 'on')


def _off(status, detail):
    return {'created': False, 'status': status, 'detail': detail}


def _recipients(env_name, default):
    raw = os.environ.get(env_name)
    if raw is None or not str(raw).strip():
        raw = default
    return [part.strip() for part in str(raw).split(',') if part.strip()]


def split_street(address):
    text = (address or '').strip()
    match = _HOUSE.match(text)
    if not match:
        return text, ''
    return match.group('street').strip(), match.group('house').strip()


def _call(token, method, path, body=None):
    data = None if body is None else json.dumps(body).encode('utf-8')
    req = Request(API + path, data=data, method=method.upper())
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Accept', 'application/json')
    req.add_header('User-Agent', 'bernvapes-crm/1.0')
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    fn = _transport or urlopen
    try:
        resp = fn(req, timeout=30)
    except HTTPError as ex:
        raw = b''
        try:
            raw = ex.read() or b''
        except Exception:
            raw = b''
        raise BexioError('bexio http %s' % ex.code, raw.decode('utf-8', 'replace')[:800], ex.code) from ex
    except URLError as ex:
        raise BexioError('bexio unreachable') from ex
    try:
        raw = resp.read()
        code = getattr(resp, 'status', None)
        if code is None:
            code = getattr(resp, 'code', 200)
    finally:
        close = getattr(resp, 'close', None)
        if close:
            close()
    if code and int(code) >= 400:
        raise BexioError('bexio http %s' % code, (raw or b'').decode('utf-8', 'replace')[:800], int(code))
    if not raw:
        return {}
    try:
        return json.loads(raw.decode('utf-8'))
    except ValueError as ex:
        raise BexioError('bexio invalid json') from ex


def _error_text(ex):
    body = getattr(ex, 'body', '') or ''
    if body:
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            for key in ('message', 'error', 'error_description'):
                if parsed.get(key):
                    return str(parsed[key])[:800]
        return body[:800]
    return str(ex)[:800]


def _save(conn, order_id, **fields):
    cols = list(fields)
    conn.execute(
        'update orders set %s where id=?' % ', '.join('%s=?' % name for name in cols),
        tuple(fields[name] for name in cols) + (order_id,))
    conn.commit()
    return conn.execute('select * from orders where id=?', (order_id,)).fetchone()


def _delivery_settled(order):
    if not delivery_enabled():
        return True
    return (order['delivery_mail_status'] or '') in ('sent', 'stock_alert_sent')


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
    if order['bexio_order_id'] and not order['bexio_kb_order_id']:
        return {'created': False, 'status': 'exists', 'invoice_id': order['bexio_order_id'],
                'detail': 'Invoice already stored.'}
    if order['bexio_order_id'] and _delivery_settled(order):
        return {'created': False, 'status': 'exists', 'invoice_id': order['bexio_order_id'],
                'kb_order_id': order['bexio_kb_order_id'], 'delivery_id': order['bexio_delivery_id'],
                'delivery_mail_status': order['delivery_mail_status'],
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
            contact_id = _find_or_create_contact(token, cust, acc, user_id, owner_id, country_id)
            conn.execute('update customers set bexio_contact_id=? where id=?', (contact_id, cust['id']))
            conn.commit()
        if not order['bexio_kb_order_id']:
            created = _create_order(token, order, items, contact_id, user_id, currency_id)
            order = _save(conn, order_id, bexio_kb_order_id=int(created['id']))
            order_nr = created.get('document_nr') or ('AU-%s' % created['id'])
        else:
            order_nr = 'AU-%s' % order['bexio_kb_order_id']
        if delivery_enabled() and not _delivery_settled(order):
            order = _deliver(conn, token, order, cust, items, order_nr)
        if not order['bexio_order_id']:
            invoice_id = _invoice_from_order(token, order['bexio_kb_order_id'])
            order = _save(conn, order_id, bexio_order_id=invoice_id)
        else:
            invoice_id = order['bexio_order_id']
    except BexioError as ex:
        return _off('error', _error_text(ex))
    return {
        'created': True, 'status': 'created', 'contact_id': contact_id, 'invoice_id': invoice_id,
        'kb_order_id': order['bexio_kb_order_id'], 'delivery_id': order['bexio_delivery_id'],
        'delivery_mail_status': order['delivery_mail_status'],
        'detail': 'bexio order and invoice stored.',
    }


def _deliver(conn, token, order, cust, items, order_nr):
    if not order['bexio_delivery_id']:
        try:
            created = _create_delivery(token, order['bexio_kb_order_id'])
        except BexioError as ex:
            text = _error_text(ex)
            try:
                _stock_alert(order, cust, items, order_nr, text)
                status = 'stock_alert_sent'
            except (OSError, RuntimeError):
                status = 'alert_failed'
            return _save(conn, order['id'], delivery_mail_status=status, delivery_error=text[:500])
        order = _save(
            conn, order['id'],
            bexio_delivery_id=int(created['id']),
            bexio_delivery_nr=created.get('document_nr') or ('LS-%s' % created['id']))
    if (order['delivery_mail_status'] or '') == 'sent':
        return order
    try:
        filename, pdf = _delivery_pdf(token, order['bexio_delivery_id'], order['bexio_delivery_nr'])
        _send_delivery_mail(order, cust, items, order_nr, filename, pdf)
    except (BexioError, OSError, RuntimeError) as ex:
        return _save(conn, order['id'], delivery_error=_error_text(ex)[:500])
    return _save(conn, order['id'], delivery_mail_status='sent', delivery_error=None)


def _find_or_create_contact(token, cust, acc, user_id, owner_id, country_id):
    email = (cust['email'] if cust else '') or ''
    if email:
        found = _call(token, 'POST', '/2.0/contact/search', [
            {'field': 'mail', 'value': email, 'criteria': '='}])
        if isinstance(found, list) and found and found[0].get('id') is not None:
            return int(found[0]['id'])
    return _create_contact(token, cust, acc, user_id, owner_id, country_id)


def _split_name(name):
    parts = (name or '').split()
    if not parts:
        return 'Kunde', 'Bernvapes'
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], ' '.join(parts[1:])


def _create_contact(token, cust, acc, user_id, owner_id, country_id):
    given, family = _split_name(cust['name'] if cust else '')
    line = (cust['address'] if cust and cust['address'] else None) or (acc['address'] if acc else '') or ''
    street, house = split_street(line)
    body = {
        'contact_type_id': 2,
        'name_1': family,
        'name_2': given,
        'street_name': street,
        'house_number': house,
        'postcode': (acc['zip'] if acc and acc['zip'] else '') or '',
        'city': (cust['city'] if cust and cust['city'] else None) or (acc['city'] if acc else '') or '',
        'country_id': country_id,
        'mail': cust['email'] if cust else '',
        'user_id': user_id,
        'owner_id': owner_id,
    }
    created = _call(token, 'POST', '/2.0/contact', body)
    if not isinstance(created, dict) or created.get('id') is None:
        raise BexioError('bexio response missing id')
    return int(created['id'])


def _position(text, qty, unit):
    """Gleiche MwSt-Behandlung wie die Artikel: Bruttopreis, tax_id nur wenn gesetzt."""
    row = {
        'type': 'KbPositionCustom',
        'amount': str(int(qty or 1)),
        'unit_price': '%.2f' % float(unit or 0),
        'text': text,
    }
    tax = (os.environ.get('BEXIO_TAX_ID') or '').strip()
    if tax.isdigit():
        row['tax_id'] = int(tax)
    return row


def _positions(order, items):
    rows = []
    for item in items:
        text = item['article'] or 'Artikel'
        if item['preorder']:
            text = '%s (Vorbestellung)' % text
        rows.append(_position(text, item['qty'] or 1, item['unit_chf']))
    if 'shipping_chf' in order.keys() and order['shipping_chf'] is not None:
        rows.append(_position('Versand', 1, order['shipping_chf']))
    return rows


def _sales_body(order, items, contact_id, user_id, currency_id):
    return {
        'title': 'Bernvapes Bestellung #%s' % order['id'],
        'contact_id': int(contact_id),
        'user_id': user_id,
        'currency_id': currency_id,
        'mwst_type': 0 if (os.environ.get('BEXIO_TAX_ID') or '').strip().isdigit() else 2,
        'mwst_is_net': False,
        'api_reference': order['external_ref'] or ('bv-%s' % order['id']),
        'positions': _positions(order, items),
    }


def _create_order(token, order, items, contact_id, user_id, currency_id):
    created = _call(token, 'POST', '/2.0/kb_order', _sales_body(order, items, contact_id, user_id, currency_id))
    if not isinstance(created, dict) or created.get('id') is None:
        raise BexioError('bexio response missing id')
    return created


def _create_delivery(token, kb_order_id):
    created = _call(token, 'POST', '/2.0/kb_order/%s/delivery' % int(kb_order_id), {})
    if not isinstance(created, dict) or created.get('id') is None:
        raise BexioError('bexio response missing id')
    return created


def _invoice_from_order(token, kb_order_id):
    created = _call(token, 'POST', '/2.0/kb_order/%s/invoice' % int(kb_order_id), {})
    if not isinstance(created, dict) or created.get('id') is None:
        raise BexioError('bexio response missing id')
    return int(created['id'])


def _delivery_pdf(token, delivery_id, delivery_nr):
    payload = _call(token, 'GET', '/2.0/kb_delivery/%s/pdf' % int(delivery_id))
    if not isinstance(payload, dict) or not payload.get('content'):
        raise BexioError('bexio delivery pdf missing')
    try:
        data = base64.b64decode(payload['content'])
    except (ValueError, TypeError) as ex:
        raise BexioError('bexio delivery pdf invalid') from ex
    name = payload.get('name') or ('%s.pdf' % (delivery_nr or ('LS-%s' % delivery_id)))
    return name, data


def _customer_line(cust):
    name = (cust['name'] if cust else '') or 'Kunde'
    email = (cust['email'] if cust else '') or ''
    return '%s <%s>' % (name, email) if email else name


def _article_lines(items):
    lines = []
    for item in items:
        text = item['article'] or 'Artikel'
        lines.append('%s × %s' % (text, int(item['qty'] or 1)))
    return '\n'.join(lines)


def _send_delivery_mail(order, cust, items, order_nr, filename, pdf):
    recipients = _recipients('DELIVERY_NOTE_RECIPIENTS', DEFAULT_DELIVERY_RECIPIENTS)
    nr = order['bexio_delivery_nr'] or filename
    ref = order['external_ref'] or ('#%s' % order['id'])
    subject = 'Lieferschein %s' % nr
    body = '\n'.join([
        'Lieferschein %s' % nr,
        'Auftrag %s' % order_nr,
        'Shop %s' % ref,
        'Kunde: %s' % _customer_line(cust),
        'Artikel:',
        _article_lines(items) or '-',
    ])
    _send_mail(recipients, subject, body, (filename, pdf, 'application/pdf'))


def _stock_alert(order, cust, items, order_nr, error_text):
    recipient = _recipients('STOCK_ALERT_RECIPIENT', DEFAULT_STOCK_RECIPIENT)
    ref = order['external_ref'] or ('#%s' % order['id'])
    body = '\n'.join([
        STOCK_HINT,
        'Auftrag: %s' % order_nr,
        'Shop: %s' % ref,
        'Kunde: %s' % _customer_line(cust),
        'Artikel:',
        _article_lines(items) or '-',
        'Fehler: %s' % error_text,
    ])
    _send_mail(recipient, STOCK_HINT, body, None)


def _send_mail(recipients, subject, body, attachment):
    if _mail_transport:
        _mail_transport(list(recipients), subject, body, attachment)
        return
    _smtp_send(recipients, subject, body, attachment)


def _smtp_send(recipients, subject, body, attachment):
    host = (os.environ.get('SMTP_HOST') or '').strip()
    if not host:
        raise RuntimeError('smtp_not_configured')
    port = int((os.environ.get('SMTP_PORT') or '587').strip() or '587')
    user = os.environ.get('SMTP_USER') or ''
    password = os.environ.get('SMTP_PASS') or ''
    sender = (os.environ.get('SMTP_FROM') or user).strip()
    if not sender:
        raise RuntimeError('smtp_not_configured')
    msg = EmailMessage()
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject
    msg.set_content(body)
    if attachment:
        filename, data, mime = attachment
        main, sub = (mime.split('/', 1) + ['octet-stream'])[:2]
        msg.add_attachment(data, maintype=main, subtype=sub, filename=filename)
    if port == 465:
        smtp = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        smtp = smtplib.SMTP(host, port, timeout=30)
    try:
        smtp.ehlo()
        if port != 465:
            smtp.starttls()
            smtp.ehlo()
        if user:
            smtp.login(user, password)
        smtp.send_message(msg)
    finally:
        try:
            smtp.quit()
        except Exception:
            pass
