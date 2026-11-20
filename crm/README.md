# Bernvapes Steuerzentrale

Local CRM for the Mac test. Start instructions, the dealer walkthrough, and the later Hetzner notes are in [../LOCAL.md](../LOCAL.md).

SQLite is the database unless `DATABASE_URL` is a Postgres URL. The admin UI is password + TOTP by default (`CRM_REQUIRE_2FA=true`; missing or invalid values stay on). Set `CRM_REQUIRE_2FA=false` for password-only admin login. Rate limit, CSRF, session rotation and password checks stay active either way. The dealer portal on the website talks to this process. Mail is logged, not sent. bexio writes are a disabled stub.
