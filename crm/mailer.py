"""Customer mail.

EMAIL_DRIVER=log (default) writes crm/mail.log and sends nothing.
EMAIL_DRIVER=smtp sends through SMTP. The password stays in the environment
and is never written into the mail log or an error line.
"""
import logging
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent
log = logging.getLogger('bernvapes.mail')

SHIP_NOTICE = (
    'Wir verkaufen nur an Personen ab 18 Jahren. '
    'Deine Bestellung wird erst versendet, nachdem wir dich kontaktiert und dein Alter bestätigt haben.'
)


class Mailer:
    def send(self, to, subject, body):
        raise NotImplementedError


class LogMailer(Mailer):
    """Writes the message to mail.log and stdout. Does not open a network connection."""

    def send(self, to, subject, body):
        path = Path(os.environ.get('CRM_MAIL_LOG') or (ROOT / 'mail.log'))
        line = 'TO %s\nSUBJECT %s\n%s\n----\n' % (to, subject, body)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as handle:
            handle.write(line)
        print('[mail:log] not sent — logged for %s: %s' % (to, subject), flush=True)


class SmtpMailer(Mailer):
    """SMTP from SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_TLS."""

    def send(self, to, subject, body):
        host = (os.environ.get('SMTP_HOST') or '').strip()
        if not host:
            raise RuntimeError('SMTP_HOST is empty')
        port = int((os.environ.get('SMTP_PORT') or '587').strip() or '587')
        user = os.environ.get('SMTP_USER') or ''
        password = os.environ.get('SMTP_PASS') or ''
        sender = (os.environ.get('SMTP_FROM') or user).strip()
        if not sender:
            raise RuntimeError('SMTP_FROM is empty')
        tls_raw = (os.environ.get('SMTP_TLS') if os.environ.get('SMTP_TLS') is not None else '1').strip().lower()
        tls = tls_raw not in ('0', 'false', 'no', 'off')
        msg = EmailMessage()
        msg['From'] = sender
        msg['To'] = to
        msg['Subject'] = subject
        msg.set_content(body)
        if port == 465:
            smtp = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            smtp = smtplib.SMTP(host, port, timeout=30)
        try:
            smtp.ehlo()
            if port != 465 and tls:
                smtp.starttls()
                smtp.ehlo()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        finally:
            try:
                smtp.quit()
            except Exception:
                pass


def get_mailer():
    driver = (os.environ.get('EMAIL_DRIVER') or 'log').strip().lower()
    if driver in ('log', 'noop', ''):
        return LogMailer()
    if driver == 'smtp':
        return SmtpMailer()
    raise RuntimeError('EMAIL_DRIVER %r is not available. Use log or smtp.' % driver)


def _safe(ex):
    text = '%s: %s' % (type(ex).__name__, ex)
    secret = os.environ.get('SMTP_PASS') or ''
    if secret and secret in text:
        text = text.replace(secret, '***')
    return text[:400]


def deliver(conn, to, subject, body):
    """Copy into mail_log, then send. A transport error is logged and does not raise."""
    ok = True
    try:
        get_mailer().send(to, subject, body)
    except Exception as ex:
        ok = False
        log.error('Mail an %s nicht gesendet (%s): %s', to, subject, _safe(ex))
    if conn is not None:
        conn.execute('insert into mail_log(to_addr,subject,body) values(?,?,?)', (to, subject, body))
        conn.commit()
    return ok


def registration_mail(name):
    subject = 'Bernvapes – dein Konto'
    body = (
        'Guten Tag %s\n\n'
        'schön, dass du bei Bernvapes ein Konto hast. Du kannst dich damit anmelden und bestellen.\n\n'
        'Wir verkaufen nur an Personen ab 18 Jahren.\n\n'
        'Freundliche Grüsse\nBernvapes\nFährstrasse 29, 3004 Bern\n'
    ) % (name or '')
    return subject, body


def reset_mail(link):
    subject = 'Bernvapes – Passwort zurücksetzen'
    body = (
        'Guten Tag\n\n'
        'du möchtest das Passwort für dein Bernvapes-Konto neu setzen. '
        'Der Link gilt zwei Stunden und funktioniert nur einmal:\n\n'
        '%s\n\n'
        'Wenn du das nicht warst, kannst du diese Mail ignorieren. Dein Passwort bleibt dann, wie es ist.\n\n'
        'Freundliche Grüsse\nBernvapes\n'
    ) % link
    return subject, body


def invite_mail(company, link, days, tier_label):
    subject = 'Bernvapes Händlerportal – Einladung'
    body = (
        'Guten Tag\n\n'
        'für %s liegt ein Zugang zum Bernvapes-Händlerportal bereit. '
        'Der Link ist einmalig und gilt %s Tage:\n\n%s\n\n'
        'Danach setzt du ein Passwort und schaltest die Zwei-Faktor-Anmeldung ein.\n'
        'Preisstufe: %s.\n\n'
        'Freundliche Grüsse\nBernvapes\n'
    ) % (company, days, link, tier_label)
    return subject, body


def order_mail(name, ref, lines, shipping, total):
    subject = 'Bernvapes – deine Bestellung %s' % ref
    rows = []
    for line in lines:
        label = line.get('name') or 'Artikel'
        if line.get('preorder'):
            label = '%s (Vorbestellung)' % label
        rows.append('%s × %s' % (label, line.get('qty') or 1))
    ship = 'gratis' if not shipping else 'CHF %.2f' % float(shipping)
    body = (
        'Guten Tag %s\n\n'
        'danke für deine Bestellung bei Bernvapes.\n\n'
        'Bestellung %s\n%s\n\n'
        'Versand: %s\n'
        'Total: CHF %.2f\n\n'
        '%s\n\n'
        'Freundliche Grüsse\nBernvapes\nFährstrasse 29, 3004 Bern\n'
    ) % (name or '', ref, '\n'.join(rows) or '-', ship, float(total), SHIP_NOTICE)
    return subject, body
