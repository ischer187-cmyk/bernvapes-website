-- Phase 1 Erweiterung (idempotent). Altersprüfung: NUR Datum + Methode + Referenz, NIE Ausweisbilder/-nummern.
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS companies(id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT DEFAULT 'b2b', -- b2b/supplier
 uid TEXT, email TEXT, phone TEXT, website TEXT, terms TEXT, notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, contact_person TEXT, email TEXT, phone TEXT,
 assortment TEXT, lead_time_days INTEGER, notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS deals(id INTEGER PRIMARY KEY, title TEXT NOT NULL, customer_id INTEGER REFERENCES customers(id),
 company_id INTEGER REFERENCES companies(id),
 stage TEXT DEFAULT 'anfrage' CHECK(stage IN('anfrage','angebot','verhandlung','gewonnen','verloren')),
 value_chf REAL, source TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS consents(id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id),
 email TEXT, kind TEXT NOT NULL, -- newsletter/whatsapp/age_data
 status TEXT DEFAULT 'pending' CHECK(status IN('pending','granted','revoked')), source TEXT, doi_token TEXT,
 requested_at TEXT DEFAULT CURRENT_TIMESTAMP, confirmed_at TEXT, revoked_at TEXT);
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, title TEXT NOT NULL, customer_id INTEGER REFERENCES customers(id),
 deal_id INTEGER REFERENCES deals(id), due_date TEXT, assignee TEXT, done INTEGER DEFAULT 0,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP, done_at TEXT);
CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id),
 deal_id INTEGER REFERENCES deals(id), channel TEXT DEFAULT 'notiz', -- notiz/email/whatsapp/telegram/bot/telefon
 direction TEXT, body TEXT NOT NULL, author TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS webhook_events(id INTEGER PRIMARY KEY, source TEXT, event_id TEXT, received_at TEXT DEFAULT CURRENT_TIMESTAMP,
 status TEXT, UNIQUE(source,event_id)); -- nur Metadaten, keine Payloads mit Personendaten
CREATE INDEX IF NOT EXISTS ix_cust_email ON customers(email);
CREATE INDEX IF NOT EXISTS ix_tasks_open ON tasks(done,due_date);
