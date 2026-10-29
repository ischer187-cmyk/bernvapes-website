# Bernvapes — lokal testen (Mac)

Die Steuerzentrale und das Händlerportal laufen auf dem Mac. Nichts wird deployed, nichts geht an `main`, DNS und die Live-Server werden nicht angefasst. Railway ist nicht vorgesehen.

SQLite ist die Datenbank. Postgres ist nur der spätere Umzug (Abschnitt 6).

## 1. Was Dominic vorher setzt

Im Terminal, bevor `app.py` startet. Keine Secrets in Dateien im Git.

| Variable | Pflicht jetzt | Bedeutung |
|---|---|---|
| `CRM_ADMIN_EMAIL` | ja | Login der Steuerzentrale |
| `CRM_ADMIN_PASSWORD` | ja | mindestens 10 Zeichen. Nur beim ersten Start, wenn noch kein Admin existiert |
| `CRM_WEBHOOK_SECRET` | ja | Header `X-Bernvapes-Secret` für `POST /webhook/order`. Ohne Wert antwortet der Webhook mit 503 |
| `WEBSITE_PUBLIC_URL` | nein | Default `http://127.0.0.1:8080`. Steht in den Einladungslinks |
| `DATABASE_URL` | nein | **leer lassen.** Gesetzt heisst Postgres |
| `BEXIO_WRITE_ENABLED` | nein | **auf 0 lassen.** Der Stub ruft bexio nicht auf |
| `EMAIL_DRIVER` | nein | Default `log`. Es gibt keinen SMTP-Versand |

Beispielpreise (Einstieg / Händler / Grosshändler) liegen nach dem ersten Start in der Datenbank. Das sind keine Ladenpreise. Echte Stufen setzt Dominic später in der Steuerzentrale unter **Preise**.

Noch nicht nötig, später schon: Domain (zum Beispiel `crm.bernvapes.ch`), SMTP-Anbieter, Hetzner, Postgres-Passwort.

## 2. Steuerzentrale starten

Terminal A, im Repo:

```bash
cd crm
export CRM_ADMIN_EMAIL='dominic@example.com'
export CRM_ADMIN_PASSWORD='ein-langes-passwort'
export CRM_WEBHOOK_SECRET='ein-langes-geheimnis'
export WEBSITE_PUBLIC_URL='http://127.0.0.1:8080'
python3 migrate.py
python3 app.py
```

Es braucht kein `pip` und kein Docker. `python3` auf Apple Silicon reicht.

Die Steuerzentrale hört nur auf [http://127.0.0.1:18734](http://127.0.0.1:18734).

1. E-Mail und Passwort eingeben.
2. Den angezeigten TOTP-Schlüssel in eine Authenticator-App eintragen (oder den otpauth-Link öffnen).
3. Den 6-stelligen Code bestätigen. Ohne Code kein Zugang zu den Daten.

`crm/crm.db` und `crm/mail.log` bleiben lokal und stehen in `.gitignore`.

## 3. Webseite und Händlerportal starten

Terminal B, im Repo-Root (nicht in `crm/`):

```bash
python3 serve_local.py
```

- Seite: [http://127.0.0.1:8080](http://127.0.0.1:8080)
- Händler: [http://127.0.0.1:8080/haendler.html](http://127.0.0.1:8080/haendler.html)

`/b2b-api/...` auf diesem Server geht an die Steuerzentrale auf Port 18734. Die HTML-Datei direkt aus dem Finder öffnen reicht nicht, weil der Browser dann das CRM nicht erreicht.

## 4. Lokaler Durchlauf (fiktiver Shop)

Shop nur als Beispiel: **Dampfwerk Test**, E-Mail `dampfwerk@example.com`, keine echte Firma.

1. In der Steuerzentrale **Kunden → Potenzielle Neukunden**.
2. Shop `Dampfwerk Test`, E-Mail `dampfwerk@example.com`, Ort `Bern`, Priorität `A`, Sprache `de`. **Interessent anlegen.**
3. Auf dem Kontakt **Einladung erzeugen**, Stufe **Händler**. Es wird keine Mail verschickt.
4. Der einmalige Link steht auf dem Kontakt unter **Einladungslink** und unter **Steuerung → Mail-Log**. Er sieht so aus: `http://127.0.0.1:8080/haendler.html?token=…`
5. Link im Browser öffnen. Passwort setzen (mindestens 10 Zeichen). TOTP-Schlüssel in die App, Code bestätigen.
6. Die Stufe Händler ist sofort aktiv, weil die Einladung aus der Steuerzentrale kam. Lemon Pie steht als Beispiel bei **CHF 10.40**. Preise sind ohne Login nicht auf der öffentlichen Seite.
7. Menge setzen und **Auf Rechnung bestellen**. Zahlungsart ist Rechnung. Eine persönliche Altersprüfung gibt es hier nicht; die Firma gilt durch die Einladung als geprüft.
8. Zurück in der Steuerzentrale: der Kontakt ist **Businesskunde**, `converted_at` ist gesetzt, die Kampagne **Einstiegspaket neue Liquids** bleibt, der Status ist **Bestellt**, der ältere Verlauf ist noch da. Die Bestellung hat Kanal `b2b` und Zahlungsart `Rechnung`. In den Notizen steht, dass bexio nicht aufgerufen wurde.

Selbstregistrierung (zweiter Weg): auf `haendler.html` **Registrieren**, Firma plus UID im Format `CHE-123.456.789`. Das Konto bleibt **pending**. Preise und Bestellung sind gesperrt, bis unter **Händler** in der Steuerzentrale **Freigeben** gedrückt wurde. Danach gilt die UID als Firmenprüfung.

Ein Sonderpreis pro Sorte steht am Händlerkonto (Override) und schlägt die Stufe.

## 5. Was absichtlich nicht live ist

- E-Mail: Schnittstelle `Mailer`, Default loggt nach `crm/mail.log` und ins Mail-Log. Kein SMTP.
- bexio Rechnungen und Kunden anlegen: Stub, Flag `BEXIO_WRITE_ENABLED` aus, kein HTTP-Call. Lesen für `classify_contacts.py --refresh` bleibt der alte GET-Weg und braucht `BEXIO_API_TOKEN` nur wenn Dominic das ausdrücklich will.
- Webhooks `payment`, `oneguard`, `newsletter-doi`, `contact`: angenommen und gespeichert, ändern keine Kundendaten. `POST /webhook/order` ist der echte Bestellweg (Shop und Händlerportal).
- Keine Railway-Konfiguration, kein Deploy, kein DNS.

## 6. Später: Hetzner mit Docker

Erst wenn der Mac-Test steht. Weiterhin nicht die Live-Server `80.74.142.120` und `178.104.76.163`, und kein Umschalten von DNS aus diesem Stand.

1. `crm/.env` aus `crm/.env.example` füllen. `CRM_COOKIE_SECURE=1` nur hinter HTTPS.
2. Im Ordner `crm/`: `docker compose up -d --build`. Das bindet CRM und Webseite an `127.0.0.1` auf dem Server. Davor einen Reverse Proxy (Caddy oder nginx) mit TLS setzen, wenn eine Domain drankommt.
3. Postgres nur mit Profil: `docker compose --profile postgres up -d --build` und `DATABASE_URL=postgresql://bernvapes:…@postgres:5432/bernvapes`.
4. Bestehende SQLite-Datei rübernehmen, einmalig:

```bash
pip3 install 'psycopg[binary]'
DATABASE_URL='postgresql://bernvapes:…@127.0.0.1:5432/bernvapes' \
  CRM_SQLITE_PATH='./crm.db' \
  python3 migrate_sqlite_to_postgres.py
```

Die SQLite-Datei wird dabei nicht gelöscht. Ohne `DATABASE_URL` bleibt jeder Start auf SQLite, auf dem Mac und später auf dem Server.

## 7. Tests

Im Repo-Root:

```bash
python3 -m unittest discover -s crm/tests -v
```

Die Tests legen eine temporäre SQLite-Datei an und prüfen Login mit TOTP, CSRF, Rate-Limit, Preisstufen inklusive Override, Freigabe-Sperre, UID-Format, Webhook-Umwandlung und die Händler-Bestellung auf Rechnung.
