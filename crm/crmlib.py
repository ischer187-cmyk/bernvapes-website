"""Gemeinsame Helfer: Normalisierung, Kampagnen-Status, Umwandlung."""
import re, unicodedata, json
from urllib.parse import urlparse
FREEMAIL={'gmail.com','gmx.ch','gmx.de','gmx.net','bluewin.ch','hotmail.com','outlook.com','yahoo.com','icloud.com','sunrise.ch','hispeed.ch','web.de','protonmail.com','yahoo.de','live.com','me.com'}
LEGAL=r'\b(gmbh|ag|sa|sarl|sagl|kg|co|ltd|inc|klg|einzelfirma)\b'
def norm(s):
  s=unicodedata.normalize('NFKD',(s or '').lower()); s=''.join(ch for ch in s if not unicodedata.combining(ch))
  s=re.sub(LEGAL,' ',s); return re.sub(r'[^a-z0-9]+','',s)
def domain(u):
  if not u: return None
  u=u.strip().lower()
  if '@' in u and '/' not in u:
    d=u.split('@')[-1]; return None if d in FREEMAIL else d
  if '://' not in u: u='http://'+u
  d=urlparse(u).netloc.split(':')[0]
  return d[4:] if d.startswith('www.') else (d or None)
CAMPAIGN='Einstiegspaket neue Liquids'
STATI=[('bereit','Bereit'),('mail_entwurf','Mail-Entwurf'),('mail_gesendet','Mail gesendet'),('sms_faellig','SMS fällig'),('sms_gesendet','SMS gesendet'),
       ('antwort','Antwort'),('interessiert','Interessiert'),('bestellt','Bestellt'),('kein_interesse','Kein Interesse')]
CONTACTED=('mail_gesendet','sms_faellig','sms_gesendet','antwort','interessiert','bestellt','kein_interesse')
RESPONDED=('antwort','interessiert','bestellt','kein_interesse')
def set_member_status(c,mid,new,note=None,author='CRM'):
  r=c.execute('select campaign_id,customer_id,status from campaign_members where id=?',(mid,)).fetchone()
  if not r or new not in dict(STATI) or r[2]==new: return False
  c.execute("update campaign_members set status=?,updated_at=datetime('now') where id=?",(new,mid))
  c.execute('insert into campaign_events(member_id,campaign_id,customer_id,old_status,new_status,note,author) values(?,?,?,?,?,?,?)',(mid,r[0],r[1],r[2],new,note,author))
  return True
def enroll_prospects(c,campaign=CAMPAIGN):
  cid=c.execute('select id from campaigns where name=?',(campaign,)).fetchone()[0]; n=0
  # Shops mit aktiv='vermutlich geschlossen' werden NICHT eingeschrieben
  for (kid,) in c.execute("select id from customers where customer_type='Interessent' and coalesce(json_extract(extra,'$.aktiv'),'') not like 'vermutlich geschlossen%'").fetchall():
    cur=c.execute('insert or ignore into campaign_members(campaign_id,customer_id,status) values(?,?,?)',(cid,kid,'bereit'))
    if cur.rowcount:
      n+=1; c.execute('insert into campaign_events(member_id,campaign_id,customer_id,old_status,new_status,note,author) values(?,?,?,?,?,?,?)',(cur.lastrowid,cid,kid,None,'bereit','eingeschrieben','System'))
  # bereits eingeschriebene, inzwischen als geschlossen markierte Shops: nur entfernen, solange noch 'bereit' (nichts passiert)
  for mid,kid in c.execute("select m.id,m.customer_id from campaign_members m join customers cu on cu.id=m.customer_id where m.campaign_id=? and m.status='bereit' and coalesce(json_extract(cu.extra,'$.aktiv'),'') like 'vermutlich geschlossen%'",(cid,)).fetchall():
    c.execute('delete from campaign_events where member_id=?',(mid,)); c.execute('delete from campaign_members where id=?',(mid,))
    c.execute('insert into notes(customer_id,channel,body,author) values(?,?,?,?)',(kid,'notiz',f'Nicht in Kampagne {campaign!r}: Shop vermutlich geschlossen','System'))
  return n
def convert(c,kid,reason,author='CRM'):
  """Interessent -> Businesskunde. Kampagnen-Mitgliedschaften + Verlauf bleiben erhalten."""
  r=c.execute('select customer_type from customers where id=?',(kid,)).fetchone()
  if not r or r[0]!='Interessent': return False
  c.execute("update customers set customer_type='Businesskunde',converted_at=datetime('now'),updated_at=datetime('now') where id=?",(kid,))
  c.execute('insert into notes(customer_id,channel,body,author) values(?,?,?,?)',(kid,'notiz',f'Umgewandelt zu Businesskunde ({reason})',author))
  return True
