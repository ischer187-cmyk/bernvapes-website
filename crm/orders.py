"""Order intake shared by POST /webhook/order and the B2B portal."""
from crmlib import convert, set_member_status
from bexio_billing import BexioBilling
from pricing import unit_price

def _num(v, default=0.0):
    if v is None or v == '':
        return default
    return float(v)

def process_order(c, d, customer_id=None, dealer_id=None):
    """Create a customer (or reuse one) and an order. Same path for shop webhook and B2B.

    A B2B order (channel 'b2b' or a dealer id) requires an approved, company-verified
    dealer. Personal age checks are not applied. Payment is Rechnung. bexio is only
    asked through the disabled stub.
    """
    data = dict(d)
    email = str(data.get('email') or '').strip().lower()
    b2b = bool(dealer_id) or data.get('channel') == 'b2b'
    dealer = None
    if b2b:
        if not dealer_id:
            found = c.execute('select id from dealer_accounts where lower(email)=?', (email,)).fetchone()
            if not found:
                raise ValueError('no approved dealer for this order')
            dealer_id = found[0]
        dealer = c.execute('select * from dealer_accounts where id=?', (dealer_id,)).fetchone()
        if not dealer or dealer['status'] != 'approved' or not dealer['company_verified_at']:
            raise ValueError('company not verified')
        customer_id = dealer['customer_id']
        email = (dealer['email'] or email).strip().lower()
        data['channel'] = 'b2b'
        data['payment_method'] = 'rechnung'
        data['company'] = data.get('company') or dealer['company_name']
        data['email'] = email
    if '@' not in email:
        raise ValueError('invalid email')
    items = data.get('items')
    if not isinstance(items, list) or not items:
        raise ValueError('items must be a non-empty list')
    if b2b:
        fixed = []
        for i in items:
            if isinstance(i, str):
                raise ValueError('b2b items need a sku')
            sku = (i.get('sku') or '').strip()
            prod = c.execute('select * from products where sku=? and coalesce(active,1)=1', (sku,)).fetchone()
            if not prod:
                raise ValueError('unknown sku')
            qty = int(i.get('qty', 1))
            if qty < 1 or qty > 999:
                raise ValueError('invalid qty')
            unit, _over = unit_price(c, dealer_id, prod)
            fixed.append({'article': prod['name'], 'sku': sku, 'qty': qty, 'unit_chf': unit, 'bottle_ml': prod['bottle_ml']})
        items = fixed
        data['items'] = items
    test = 1 if data.get('test') in (True, 1, 'true', '1') else 0
    converted = False
    if customer_id:
        r = c.execute('select id,customer_type from customers where id=?', (customer_id,)).fetchone()
        if not r:
            raise ValueError('customer missing')
        cid = r[0]
        created = False
        c.execute(
            "update customers set email=coalesce(nullif(email,''),?), name=coalesce(nullif(name,''),?), phone=coalesce(nullif(phone,''),?), city=coalesce(nullif(city,''),?), updated_at=datetime('now') where id=?",
            (email, data.get('name'), data.get('phone'), data.get('city'), cid))
        if r[1] == 'Interessent':
            converted = convert(c, cid, 'erste Bestellung via Website', 'Webhook')
    else:
        r = c.execute('select id,customer_type from customers where lower(email)=? order by id limit 1', (email,)).fetchone()
        if r:
            cid = r[0]
            created = False
            c.execute(
                "update customers set name=coalesce(nullif(name,''),?), phone=coalesce(nullif(phone,''),?), city=coalesce(nullif(city,''),?), updated_at=datetime('now') where id=?",
                (data.get('name'), data.get('phone'), data.get('city'), cid))
            if r[1] == 'Interessent':
                converted = convert(c, cid, 'erste Bestellung via Website', 'Webhook')
        else:
            ctype = 'Businesskunde' if data.get('company') else 'Endkunde'
            cid = c.execute(
                'insert into customers(name,email,phone,city,customer_type,company_name,tags) values(?,?,?,?,?,?,?)',
                (data.get('name') or email, email, data.get('phone'), data.get('city'), ctype, data.get('company'), 'test' if test else None)).lastrowid
            created = True
    if data.get('company'):
        co = c.execute('select id from companies where name=?', (data['company'],)).fetchone()
        coid = co[0] if co else c.execute("insert into companies(name,kind,uid) values(?,'b2b',?)", (data['company'], dealer['uid'] if dealer else None)).lastrowid
        c.execute(
            "update customers set company_id=coalesce(company_id,?), company_name=coalesce(company_name,?), customer_type=case when customer_type in ('Endkunde','Interessent') then 'Businesskunde' else customer_type end where id=?",
            (coid, data['company'], cid))
        if not converted and c.execute('select customer_type from customers where id=?', (cid,)).fetchone()[0] == 'Interessent':
            converted = convert(c, cid, 'erste Bestellung via Website', 'Webhook')
    total = data.get('total', data.get('total_chf'))
    if total is None:
        total = sum(_num(i.get('qty', 1)) * _num(i.get('unit_chf', i.get('price', 0))) for i in items if isinstance(i, dict))
    ext = data.get('external_ref')
    if ext and c.execute('select 1 from orders where external_ref=?', (str(ext),)).fetchone():
        raise ValueError('external_ref already exists')
    pay = data.get('payment_method')
    oid = c.execute(
        "insert into orders(customer_id,channel,status,total_chf,external_ref,payment_status,payment_provider,currency,is_test,payment_method,dealer_account_id,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
        (cid, data.get('channel', 'website'), 'neu', float(total), str(ext) if ext else None,
         data.get('payment_status', 'offen'), data.get('payment_provider'), data.get('currency', 'CHF'), test,
         pay, dealer_id)).lastrowid
    for i in items:
        if isinstance(i, str):
            i = {'article': i}
        c.execute(
            'insert into order_items(order_id,article,qty,unit_chf,bottle_ml,target_mg,shots) values(?,?,?,?,?,?,?)',
            (oid, i.get('article') or i.get('name'), int(i.get('qty', 1)), i.get('unit_chf', i.get('price')),
             i.get('bottle_ml'), i.get('target_mg'), i.get('shots')))
    note = f'Bestellung via {"Händlerportal" if b2b else "Website"} #{oid}'
    if ext:
        note += f' ({ext})'
    note += f' · CHF {float(total):.2f}'
    if test:
        note += ' [TEST]'
    if b2b:
        note += '. Firmenprüfung statt persönlicher Altersprüfung. Zahlungsart Rechnung.'
    c.execute('insert into notes(customer_id,channel,direction,body,author) values(?,?,?,?,?)',
              (cid, 'b2b' if b2b else 'website', 'in', note, 'Webhook'))
    for (mid,) in c.execute("select id from campaign_members where customer_id=? and status<>'bestellt'", (cid,)).fetchall():
        set_member_status(c, mid, 'bestellt', f'Bestellung #{oid}', 'Webhook')
    bexio = None
    if b2b:
        bexio = BexioBilling().create_invoice({'order_id': oid, 'customer_id': cid, 'total_chf': float(total), 'payment_method': 'rechnung'})
        c.execute('insert into notes(customer_id,channel,body,author) values(?,?,?,?)',
                  (cid, 'notiz', f"bexio Rechnung #{oid}: {bexio['status']} — {bexio['detail']}", 'System'))
    return {
        'order_id': oid, 'customer_id': cid, 'customer_created': created, 'converted_to_business': converted,
        'url': f'/bestellung/{oid}', 'payment_method': pay, 'company_verified': bool(b2b), 'bexio': bexio,
    }
