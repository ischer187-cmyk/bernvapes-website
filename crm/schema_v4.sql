-- Auth, Händlerportal, Preisstufen. Idempotent. Keine Geheimnisse.
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS admin_users(
 id INTEGER PRIMARY KEY,
 email TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL,
 totp_secret TEXT,
 totp_confirmed INTEGER DEFAULT 0,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 last_login_at TEXT);

CREATE TABLE IF NOT EXISTS sessions(
 id INTEGER PRIMARY KEY,
 token_hash TEXT NOT NULL UNIQUE,
 kind TEXT NOT NULL,
 scope TEXT NOT NULL DEFAULT 'full',
 user_id INTEGER NOT NULL,
 csrf_token TEXT NOT NULL,
 expires_at TEXT NOT NULL,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS rate_limits(
 id INTEGER PRIMARY KEY,
 bucket TEXT NOT NULL,
 at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_rate_bucket ON rate_limits(bucket, at);

CREATE TABLE IF NOT EXISTS dealer_accounts(
 id INTEGER PRIMARY KEY,
 customer_id INTEGER REFERENCES customers(id),
 email TEXT NOT NULL UNIQUE,
 password_hash TEXT,
 totp_secret TEXT,
 totp_confirmed INTEGER DEFAULT 0,
 status TEXT NOT NULL DEFAULT 'pending',
 company_name TEXT,
 uid TEXT,
 contact_person TEXT,
 price_tier TEXT DEFAULT 'einstieg',
 company_verified_at TEXT,
 company_verify_method TEXT,
 invite_token_hash TEXT,
 invite_expires_at TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS products(
 id INTEGER PRIMARY KEY,
 sku TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL,
 bottle_ml INTEGER,
 active INTEGER DEFAULT 1,
 price_einstieg REAL NOT NULL,
 price_haendler REAL NOT NULL,
 price_grosshaendler REAL NOT NULL,
 sample_price INTEGER DEFAULT 1);

CREATE TABLE IF NOT EXISTS price_overrides(
 id INTEGER PRIMARY KEY,
 dealer_id INTEGER NOT NULL REFERENCES dealer_accounts(id),
 product_id INTEGER NOT NULL REFERENCES products(id),
 unit_chf REAL NOT NULL,
 UNIQUE(dealer_id, product_id));

CREATE TABLE IF NOT EXISTS mail_log(
 id INTEGER PRIMARY KEY,
 to_addr TEXT,
 subject TEXT,
 body TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP);
