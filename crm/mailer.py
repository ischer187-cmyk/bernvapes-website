"""E-mail sending is an interface. The default driver logs and stores nothing itself.
No SMTP client is included and nothing is sent."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

class Mailer:
    def send(self, to, subject, body):
        raise NotImplementedError

class LogMailer(Mailer):
    """Writes the message to mail.log and stdout. Does not open a network connection."""
    def send(self, to, subject, body):
        path = Path(os.environ.get('CRM_MAIL_LOG') or (ROOT / 'mail.log'))
        line = f"TO {to}\nSUBJECT {subject}\n{body}\n----\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as f:
            f.write(line)
        print(f'[mail:{os.environ.get("EMAIL_DRIVER","log")}] not sent — logged for {to}: {subject}', flush=True)

def get_mailer():
    driver = (os.environ.get('EMAIL_DRIVER') or 'log').strip().lower()
    if driver in ('log', 'noop', ''):
        return LogMailer()
    raise RuntimeError('EMAIL_DRIVER %r is not available. Only log/noop ship with this build; no SMTP is configured.' % driver)
