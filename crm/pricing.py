"""Price tiers: Einstieg, Händler, Grosshändler, plus per-shop product overrides."""
import re

TIERS = ('einstieg', 'haendler', 'grosshaendler')
TIER_LABEL = {'einstieg': 'Einstieg', 'haendler': 'Händler', 'grosshaendler': 'Grosshändler'}
TIER_COLUMN = {
    'einstieg': 'price_einstieg',
    'haendler': 'price_haendler',
    'grosshaendler': 'price_grosshaendler',
}
_ALIAS = {
    'einstieg': 'einstieg',
    'händler': 'haendler', 'haendler': 'haendler', 'handler': 'haendler',
    'grosshändler': 'grosshaendler', 'grosshaendler': 'grosshaendler', 'grosshandler': 'grosshaendler',
}

# Sample trade prices for the local test. Dominic replaces them in the CRM (Preise).
# 60 ml: Einstieg / Händler / Grosshändler. 100 ml is a step up. Not live shop prices.
SAMPLE_60 = (12.90, 10.40, 8.20)
SAMPLE_100 = (16.90, 13.50, 10.80)

def _p(name, ml):
    a, b, c = SAMPLE_100 if ml == 100 else SAMPLE_60
    sku = name.lower().replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    sku = re.sub(r'[^a-z0-9]+', '-', sku).strip('-')
    return (sku, name, ml, a, b, c)

SAMPLE_PRODUCTS = [
    _p('Lemon Pie', 60), _p('Mango Lassi', 60), _p('Mandarine Nuss', 60), _p('Apple Pie', 60),
    _p('Monbijou Marder', 60), _p('Breitsch Hirsch', 60), _p('Matte Eule', 60),
    _p('Länggass Dachs', 60), _p('Wyler Falke', 60), _p('Schanzen Kater', 60), _p('Bollwerk Köter', 60),
    _p('Breitsch Hirsch uf Ys', 60), _p('Matte Eule uf Ys', 60), _p('Länggass Dachs uf Ys', 60), _p('Wyler Falke uf Ys', 60),
    _p('Gipfel Adler', 100), _p('Nebel Wolf', 100), _p('Steinschlag Bock', 100),
    _p('Waldwiesen Biene', 100), _p('Wildwasser Biber', 100), _p('Absturz Milan', 100),
    _p('Waldbrand Salamander', 100), _p('Abgrund Gemse', 100), _p('Erdbeben Elch', 100),
    _p('Gipfel Adler uf Ys', 100), _p('Nebel Wolf uf Ys', 100), _p('Steinschlag Bock uf Ys', 100),
]

def normalize_tier(value):
    key = (value or '').strip().lower()
    tier = _ALIAS.get(key)
    if not tier:
        raise ValueError('unknown tier')
    return tier

def seed_products(conn):
    for sku, name, ml, a, b, c in SAMPLE_PRODUCTS:
        conn.execute(
            'insert or ignore into products(sku,name,bottle_ml,price_einstieg,price_haendler,price_grosshaendler,sample_price,active) values(?,?,?,?,?,?,1,1)',
            (sku, name, ml, a, b, c))

def unit_price(conn, dealer_id, product):
    ov = conn.execute(
        'select unit_chf from price_overrides where dealer_id=? and product_id=?',
        (dealer_id, product['id'])).fetchone()
    if ov is not None:
        return float(ov['unit_chf']), True
    dealer = conn.execute('select price_tier from dealer_accounts where id=?', (dealer_id,)).fetchone()
    tier = normalize_tier(dealer['price_tier'] if dealer else 'einstieg')
    return float(product[TIER_COLUMN[tier]]), False

UID_RE = re.compile(r'^CHE-\d{3}\.\d{3}\.\d{3}$')

def normalize_uid(value):
    uid = re.sub(r'\s+', '', (value or '')).upper()
    if not UID_RE.match(uid):
        raise ValueError('UID must look like CHE-123.456.789')
    return uid
