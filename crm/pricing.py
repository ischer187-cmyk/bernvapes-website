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
# The consumer shop must not charge these. It uses RETAIL_CHF (old shop, inkl. MwSt.).
SAMPLE_60 = (12.90, 10.40, 8.20)
SAMPLE_100 = (16.90, 13.50, 10.80)

# Consumer prices copied from https://bernvapes.ch (WooCommerce), read 20 Nov 2026.
# Quartier lines are 40 ml shortfill (filled toward 60 ml) at CHF 25.
# Bergtier lines are 100 ml shortfill at CHF 34. On-the-rocks is the same price.
# The new line (lemon-pie, mango-lassi, mandarine-nuss, apple-pie) is not on the old shop.
# Dominic set it to CHF 25 on 27 Nov 2026 (same as a 60 ml Quartier bottle).
# The seven old-shop articles (Safari, Felsenau Fuchs, Schnee Hase, Abgrund Gemse,
# Breitsch Hirsch uf Ys) were approved for the new catalog on 27 Nov 2026.
RETAIL_CHF = {
    'lemon-pie': 25.00,
    'mango-lassi': 25.00,
    'mandarine-nuss': 25.00,
    'apple-pie': 25.00,
    'monbijou-marder': 25.00,
    'breitsch-hirsch': 25.00,
    'matte-eule': 25.00,
    'laenggass-dachs': 25.00,
    'wyler-falke': 25.00,
    'schanzen-kater': 25.00,
    'bollwerk-koeter': 25.00,
    'matte-eule-uf-ys': 25.00,
    'laenggass-dachs-uf-ys': 25.00,
    'wyler-falke-uf-ys': 25.00,
    'gipfel-adler': 34.00,
    'nebel-wolf': 34.00,
    'steinschlag-bock': 34.00,
    'waldwiesen-biene': 34.00,
    'wildwasser-biber': 34.00,
    'absturz-milan': 34.00,
    'waldbrand-salamander': 34.00,
    'erdbeben-elch': 34.00,
    'gipfel-adler-uf-ys': 34.00,
    'nebel-wolf-uf-ys': 34.00,
    'steinschlag-bock-uf-ys': 34.00,
    'whiskey-cherry-panda': 25.00,
    'apfel-tabak-rhino': 25.00,
    'erdbeer-creme-tiger': 25.00,
    'felsenau-fuchs': 25.00,
    'breitsch-hirsch-uf-ys': 25.00,
    'schnee-hase': 34.00,
    'abgrund-gemse': 34.00,
}

# Catalog details for the articles taken over from the old shop (bernvapes.ch, 27 Nov 2026).
# image is a site path. image_placeholder=1 marks a stand-in until a real bottle photo exists.
# orderable=0 keeps the article visible but not in the cart (Felsenau Fuchs is sold out).
PLACEHOLDER_IMAGE = 'assets/web/produkte_clean/PLATZHALTER_bild_fehlt.webp'
PRODUCT_INFO = {
    'whiskey-cherry-panda': dict(
        line='Safari-Tiere', size='30 ml Shortfill, auf 60 ml auffüllbar',
        image='assets/web/produkte_clean/panda_60ml.webp', orderable=1,
        description='Saftige Kirschen mit einem Hauch Whiskey, vollmundig und mit süsser Note abgerundet.'),
    'apfel-tabak-rhino': dict(
        line='Safari-Tiere', size='30 ml Shortfill, auf 60 ml auffüllbar',
        image='assets/web/produkte_clean/rhino_60ml.webp', orderable=1,
        description='Würziger Tabak kombiniert mit fruchtigen Noten von saftigen Äpfeln.'),
    'erdbeer-creme-tiger': dict(
        line='Safari-Tiere', size='30 ml Shortfill, auf 60 ml auffüllbar',
        image='assets/web/produkte_clean/tiger_60ml.webp', orderable=1,
        description='Reife Erdbeeren und Vanillecreme, frisch, süss und cremig.'),
    'felsenau-fuchs': dict(
        line='Quartiere', size='40 ml Shortfill, auf 60 ml auffüllbar',
        image='assets/web/produkte_clean/felsenau_fuchs_60ml.webp', orderable=0,
        description='Haselnuss und Blueberry: fruchtiges Blueberry-Aroma, mit angenehmem Nussgeschmack abgerundet. Zurzeit ausverkauft.'),
    'breitsch-hirsch-uf-ys': dict(
        line='Quartiere On the Rocks', size='40 ml Shortfill, auf 60 ml auffüllbar',
        image=PLACEHOLDER_IMAGE, image_placeholder=1, orderable=1,
        description='Pistache, roter Apfel und Koolada: unser Pistachevape mit kühlem Abgang.'),
    'schnee-hase': dict(
        line='Bergtiere', size='100 ml Shortfill, auf 120 ml auffüllbar',
        image='assets/web/produkte_clean/schnee_hase_100ml.webp', orderable=1,
        description='Salziges Cashew: feines Nuss-Liquid, nicht zu süss, ideal im Tröpfler.'),
    'abgrund-gemse': dict(
        line='Bergtiere', size='100 ml Shortfill, auf 120 ml auffüllbar',
        image=PLACEHOLDER_IMAGE, image_placeholder=1, orderable=1,
        description='Natürliche Himbeere mit feinem, cremigem Mascarpone-Abgang.'),
}
PRODUCT_INFO_COLUMNS = {
    'product_line': 'TEXT', 'size_label': 'TEXT', 'description': 'TEXT',
    'image': 'TEXT', 'image_placeholder': 'INTEGER', 'orderable': 'INTEGER',
}

def _p(name, ml):
    a, b, c = SAMPLE_100 if ml == 100 else SAMPLE_60
    sku = name.lower().replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    sku = re.sub(r'[^a-z0-9]+', '-', sku).strip('-')
    return (sku, name, ml, a, b, c)

SAMPLE_PRODUCTS = [
    _p('Lemon Pie', 60), _p('Mango Lassi', 60), _p('Mandarine Nuss', 60), _p('Apple Pie', 60),
    _p('Monbijou Marder', 60), _p('Breitsch Hirsch', 60), _p('Matte Eule', 60),
    _p('Länggass Dachs', 60), _p('Wyler Falke', 60), _p('Schanzen Kater', 60), _p('Bollwerk Köter', 60),
    _p('Matte Eule uf Ys', 60), _p('Länggass Dachs uf Ys', 60), _p('Wyler Falke uf Ys', 60),
    _p('Gipfel Adler', 100), _p('Nebel Wolf', 100), _p('Steinschlag Bock', 100),
    _p('Waldwiesen Biene', 100), _p('Wildwasser Biber', 100), _p('Absturz Milan', 100),
    _p('Waldbrand Salamander', 100), _p('Erdbeben Elch', 100),
    _p('Gipfel Adler uf Ys', 100), _p('Nebel Wolf uf Ys', 100), _p('Steinschlag Bock uf Ys', 100),
    # From the old shop (approved 27 Nov 2026). B2B tiers are the same sample tiers.
    _p('Whiskey Cherry Panda', 60), _p('Apfel Tabak Rhino', 60), _p('Erdbeer Creme Tiger', 60),
    _p('Felsenau Fuchs', 60), _p('Breitsch Hirsch uf Ys', 60),
    _p('Schnee Hase', 100), _p('Abgrund Gemse', 100),
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
            'insert or ignore into products(sku,name,bottle_ml,price_einstieg,price_haendler,price_grosshaendler,sample_price,active,price_retail) values(?,?,?,?,?,?,1,1,?)',
            (sku, name, ml, a, b, c, RETAIL_CHF.get(sku)))

def apply_retail(conn):
    """Fill empty consumer prices. Does not touch B2B tiers or a retail price already set."""
    for sku, price in RETAIL_CHF.items():
        conn.execute(
            'update products set price_retail=? where sku=? and price_retail is null',
            (price, sku))

def apply_info(conn):
    """Fill empty catalog details (line, size, text, image, orderable). Never overwrites a set value."""
    for sku, info in PRODUCT_INFO.items():
        for col, key in (('product_line', 'line'), ('size_label', 'size'), ('description', 'description'),
                         ('image', 'image'), ('image_placeholder', 'image_placeholder'), ('orderable', 'orderable')):
            conn.execute(
                f'update products set {col}=? where sku=? and {col} is null',
                (info.get(key, 0 if key == 'image_placeholder' else None), sku))

def is_orderable(prod):
    """False only when the row says orderable=0 (for example sold out). Missing column means orderable."""
    keys = prod.keys()
    return not ('orderable' in keys and prod['orderable'] is not None and int(prod['orderable']) == 0)

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
