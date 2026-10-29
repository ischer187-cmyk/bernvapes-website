"""Copy the local SQLite file into Postgres.

Leave DATABASE_URL unset on the Mac. Use this only for the later Hetzner move,
after Postgres is up and DATABASE_URL is a postgresql:// URL.

    pip3 install 'psycopg[binary]'
    DATABASE_URL=postgresql://bernvapes:secret@127.0.0.1:5432/bernvapes \
      python3 migrate_sqlite_to_postgres.py
"""
import os, sqlite3, sys
from pathlib import Path

TABLES = [
    'admin_users', 'customers', 'companies', 'suppliers', 'campaigns', 'products',
    'deals', 'consents', 'tasks', 'notes', 'orders', 'order_items', 'webhook_events',
    'campaign_members', 'campaign_events', 'dealer_accounts', 'price_overrides',
    'sessions', 'rate_limits', 'mail_log',
]

def main():
    url = (os.environ.get('DATABASE_URL') or '').strip()
    if not (url.startswith('postgres://') or url.startswith('postgresql://')):
        sys.exit('DATABASE_URL must be a postgresql:// URL. Leave it empty to stay on SQLite.')
    src_path = os.environ.get('CRM_SQLITE_PATH') or str(Path(__file__).resolve().parent / 'crm.db')
    if not Path(src_path).exists():
        sys.exit('SQLite file not found: ' + src_path)
    try:
        from migrate import migrate
        from db import connect
    except ImportError as ex:
        sys.exit('Postgres driver missing. pip3 install \'psycopg[binary]\' (' + str(ex) + ')')
    pg = connect()
    migrate(pg, seed=False)
    pg.commit()
    src = sqlite3.connect(src_path)
    src.row_factory = sqlite3.Row
    present = {r[0] for r in src.execute("select name from sqlite_master where type='table'")}
    for table in reversed(TABLES):
        if table in present:
            pg.execute('delete from ' + table)
    pg.commit()
    copied = 0
    for table in TABLES:
        if table not in present:
            continue
        src_cols = [r[1] for r in src.execute('pragma table_info(' + table + ')')]
        dst_cols = {r[0] for r in pg.execute(
            "select column_name from information_schema.columns where table_schema='public' and table_name=?",
            (table,)).fetchall()}
        cols = [c for c in src_cols if c in dst_cols]
        rows = src.execute('select ' + ','.join(cols) + ' from ' + table).fetchall() if cols else []
        if not rows:
            continue
        sql = 'insert into ' + table + '(' + ','.join(cols) + ') values(' + ','.join(['?'] * len(cols)) + ')'
        for row in rows:
            pg.execute(sql, tuple(row[c] for c in cols))
            copied += 1
        pg.raw.execute(
            "SELECT setval(pg_get_serial_sequence(%s, 'id'), GREATEST(COALESCE((SELECT MAX(id) FROM " + table + "), 1), 1))",
            (table,))
    pg.commit()
    pg.close()
    src.close()
    print('Copied', copied, 'rows from', src_path, 'into Postgres. The SQLite file was not deleted.')

if __name__ == '__main__':
    main()
