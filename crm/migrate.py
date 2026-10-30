"""Apply schema.sql + schema_v2.sql + schema_v3.sql + schema_v4.sql and missing columns.

orders.shipping_chf, orders.birthdate, orders.age_check_status and customers.birthdate
are added here for databases created before the shop shipping / age check.

SQLite is the default. If DATABASE_URL is a Postgres URL, the same schema is
applied there (with a few compatibility functions) and no SQLite file is touched.
"""
import os
from pathlib import Path
from db import ROOT, connect, adapt_schema_pg, PG_COMPAT, database_url
from auth import hash_password
from pricing import seed_products

FILES = ('schema.sql', 'schema_v2.sql', 'schema_v3.sql', 'schema_v4.sql')
ADD = {
    'customers': {
        'age_verify_ref': 'TEXT', 'age_verified': 'INTEGER DEFAULT 0', 'birthdate': 'TEXT',
        'customer_type': "TEXT DEFAULT 'Endkunde'", 'company_id': 'INTEGER', 'city': 'TEXT', 'tags': 'TEXT',
        'company_name': 'TEXT', 'contact_person': 'TEXT', 'canton': 'TEXT', 'website': 'TEXT', 'address': 'TEXT',
        'source': 'TEXT', 'priority': 'TEXT', 'extra': 'TEXT', 'brand': 'TEXT', 'bexio_groups': 'TEXT',
        'converted_at': 'TEXT', 'language': 'TEXT'},
    'orders': {
        'payment_provider': 'TEXT', 'payment_tx_id': 'TEXT', 'external_ref': 'TEXT', 'updated_at': 'TEXT',
        'payment_status': 'TEXT', 'currency': "TEXT DEFAULT 'CHF'", 'is_test': 'INTEGER DEFAULT 0',
        'payment_method': 'TEXT', 'dealer_account_id': 'INTEGER',
        'customer_account_id': 'INTEGER', 'postfinance_state': 'TEXT',
        'shipping_chf': 'REAL DEFAULT 0', 'birthdate': 'TEXT', 'age_check_status': 'TEXT',
        'bexio_kb_order_id': 'INTEGER', 'bexio_delivery_id': 'INTEGER', 'bexio_delivery_nr': 'TEXT',
        'delivery_mail_status': 'TEXT', 'delivery_error': 'TEXT'},
    'order_items': {'preorder': 'INTEGER DEFAULT 0'},
}

def _columns(conn, table):
    if conn.pg:
        rows = conn.execute(
            "select column_name from information_schema.columns where table_schema='public' and table_name=?",
            (table,)).fetchall()
        return {r[0] for r in rows}
    return {r[1] for r in conn.execute(f'pragma table_info({table})').fetchall()}

def _apply_sql(conn, sql):
    if conn.pg:
        conn.executescript(adapt_schema_pg(sql))
    else:
        conn.executescript(sql)

def ensure_admin(conn):
    n = conn.execute('select count(*) from admin_users').fetchone()[0]
    if n:
        return False
    email = (os.environ.get('CRM_ADMIN_EMAIL') or '').strip().lower()
    pw = os.environ.get('CRM_ADMIN_PASSWORD') or ''
    if not email or not pw:
        return False
    if len(pw) < 10:
        raise SystemExit('CRM_ADMIN_PASSWORD must be at least 10 characters')
    conn.execute('insert into admin_users(email,password_hash) values(?,?)', (email, hash_password(pw)))
    return True

def migrate(conn=None, seed=True):
    own = conn is None
    if own:
        conn = connect()
    if conn.pg:
        conn.executescript(PG_COMPAT)
    # schema_v3 indexes customers.customer_type, which is added below (not in schema.sql).
    for name in ('schema.sql', 'schema_v2.sql'):
        _apply_sql(conn, (ROOT / name).read_text(encoding='utf-8'))
    for table, cols in ADD.items():
        have = _columns(conn, table)
        for col, decl in cols.items():
            if col not in have:
                conn.execute(f'alter table {table} add column {col} {decl}')
    for name in ('schema_v3.sql', 'schema_v4.sql', 'schema_v5.sql'):
        _apply_sql(conn, (ROOT / name).read_text(encoding='utf-8'))
    have_dealer = _columns(conn, 'dealer_accounts')
    if 'last_login_at' not in have_dealer:
        conn.execute('alter table dealer_accounts add column last_login_at TEXT')
    if conn.pg:
        conn.execute('create unique index if not exists ux_orders_extref on orders(external_ref) where external_ref is not null')
    else:
        conn.execute('create unique index if not exists ux_orders_extref on orders(external_ref) where external_ref is not null')
    conn.execute(
        "insert or ignore into campaigns(name,description,status,active) values(?,?,?,?)",
        ('Einstiegspaket neue Liquids',
         'Einstiegspaket für neue Shops (Entwurf, inaktiv). Versand nicht konfiguriert.',
         'entwurf', 0))
    if seed:
        seed_products(conn)
        ensure_admin(conn)
    if own:
        conn.commit()
        conn.close()
    return conn

if __name__ == '__main__':
    migrate()
    print('Schema aktuell (' + ('postgres' if database_url().startswith('postgres') else 'sqlite') + ').')
