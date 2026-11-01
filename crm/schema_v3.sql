-- Phase 3: Kampagnen (idempotent). KEIN Versand-Code; Status nur manuell gepflegt.
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS campaigns(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT,
 status TEXT DEFAULT 'entwurf', active INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS campaign_members(id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
 customer_id INTEGER NOT NULL REFERENCES customers(id),
 status TEXT NOT NULL DEFAULT 'bereit' CHECK(status IN('bereit','mail_entwurf','mail_gesendet','sms_faellig','sms_gesendet','antwort','interessiert','bestellt','kein_interesse')),
 created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(campaign_id,customer_id));
CREATE TABLE IF NOT EXISTS campaign_events(id INTEGER PRIMARY KEY, member_id INTEGER REFERENCES campaign_members(id),
 campaign_id INTEGER, customer_id INTEGER, old_status TEXT, new_status TEXT, note TEXT, author TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_cust_type ON customers(customer_type);
