-- Endkunden-Konten (B2C). Sofort aktiv. Altersbestätigung nur als Checkbox, keine e-ID.
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS customer_accounts(
 id INTEGER PRIMARY KEY,
 customer_id INTEGER REFERENCES customers(id),
 email TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL,
 name TEXT,
 address TEXT,
 zip TEXT,
 city TEXT,
 age_confirmed INTEGER DEFAULT 0,
 age_confirmed_at TEXT,
 reset_token_hash TEXT,
 reset_expires_at TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 last_login_at TEXT);
CREATE INDEX IF NOT EXISTS ix_customer_accounts_email ON customer_accounts(email);
