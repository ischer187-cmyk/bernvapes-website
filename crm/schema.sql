PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS customers(
 id INTEGER PRIMARY KEY, bexio_contact_id INTEGER UNIQUE, name TEXT, email TEXT, phone TEXT,
 nicotine_mg REAL, preferred_channels TEXT,           -- z.B. 'whatsapp,email'
 age_verified_at TEXT, age_verify_method TEXT,         -- nur Datum + Methode, KEINE Bilder
 birthdate TEXT,                                      -- TT.MM.JJJJ, kein Ausweisbild
 consent_newsletter INTEGER DEFAULT 0, consent_whatsapp INTEGER DEFAULT 0, consent_age_data INTEGER DEFAULT 0,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS orders(
 id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id), channel TEXT,
 status TEXT DEFAULT 'pending',  -- pending/paid/failed/shipped
 total_chf REAL, shipping_chf REAL DEFAULT 0, birthdate TEXT, age_check_status TEXT,
 postfinance_tx_id TEXT, bexio_order_id INTEGER, bexio_kb_order_id INTEGER, bexio_delivery_id INTEGER,
 bexio_delivery_nr TEXT, delivery_mail_status TEXT, delivery_error TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS order_items(
 id INTEGER PRIMARY KEY, order_id INTEGER REFERENCES orders(id), article TEXT, bexio_article_id INTEGER,
 qty INTEGER, unit_chf REAL, bottle_ml INTEGER, target_mg REAL, shots INTEGER);
