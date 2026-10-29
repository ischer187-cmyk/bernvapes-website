# Start für den 14er

Zwei Terminal-Fenster. Ordner: die Website.

## Fenster 1, Ordner `crm`

Diese Namen müssen gesetzt sein. Die Werte kommen von Dominic, sie stehen nicht in dieser Datei:

- CRM_ADMIN_EMAIL
- CRM_ADMIN_PASSWORD
- CRM_WEBHOOK_SECRET

Dann:

```bash
python3 migrate.py
python3 app.py
```

Browser: http://127.0.0.1:18734

Dort einloggen (Passwort und der 6-stellige Code aus der App). Die Kundenliste ist der Tab **Konten**.

## Fenster 2, Ordner der Website

```bash
python3 serve_local.py
```

Browser: http://127.0.0.1:8080

Login oben rechts, Konto-Seite: http://127.0.0.1:8080/konto.html

Das ist der Endkunden-Login. Das Händlerportal ist aus. Name, den du nicht setzen musst: B2B_ENABLED

Optionaler Name, nur wenn die Links nicht auf diesen Rechner zeigen sollen: WEBSITE_PUBLIC_URL

Leer lassen: DATABASE_URL und BEXIO_WRITE_ENABLED

Für die Test-Kasse (PostFinance), nur die Namen:

- POSTFINANCE_SPACE_ID
- POSTFINANCE_USER_ID
- POSTFINANCE_SPACE_KEY

Webhook im CRM: POST /webhook/postfinance

bexio nach der Zahlung bleibt aus. Namen, nur wenn du es einschaltest: BEXIO_SYNC_ENABLED, BEXIO_API_TOKEN, BEXIO_USER_ID

Passwort-vergessen-Links stehen im CRM unter **Steuerung → Mail-Log**. Es geht keine echte Mail raus.
