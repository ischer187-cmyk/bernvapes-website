# Bernvapes Steuerzentrale

Local CRM for the Mac test. Start instructions, the dealer walkthrough, and the later Hetzner notes are in [../LOCAL.md](../LOCAL.md).

SQLite is the database unless `DATABASE_URL` is a Postgres URL. The admin UI is password + TOTP. The dealer portal on the website talks to this process. Mail is logged, not sent. bexio writes are a disabled stub.
