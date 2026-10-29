"""Potenzielle Neukunden (Interessent) aus CSV importieren. Wiederholbar: Dedup über normalisierter Name+Ort
und über Website-/E-Mail-Domain gegen ALLE Kontakte (inkl. bexio-Gruppe 9). Bestehende Interessenten werden nur
ergänzt (leere Felder), andere Treffer übersprungen. Usage: python3 import_prospects.py [datei.csv] [--status potenziell] [--dry-run]"""
import csv, sys, json, pathlib, collections
from crmlib import norm, domain, enroll_prospects
from migrate import migrate
from db import connect
D=pathlib.Path(__file__).parent
migrate()
args=[a for a in sys.argv[1:] if not a.startswith('--')]
p=pathlib.Path(args[0]) if args else next(x for x in (D/'vapeshops_schweiz.csv',D.parent/'vapeshops_schweiz.csv') if x.exists())
status=sys.argv[sys.argv.index('--status')+1] if '--status' in sys.argv else 'potenziell'
KNOWN={'name','city','canton','address','website','email','phone','mobile','type','status','source','note','ansprechperson','contact_person','prioritaet','priority','sprache','language'}
c=connect(); st=collections.Counter(); skipped=[]
def index():
  nc,dm={},{}
  for kid,n,cn,city,web,em,t in c.execute('select id,name,company_name,city,website,email,customer_type from customers'):
    for x in {n,cn}:
      if x: nc.setdefault((norm(x),norm(city)),(kid,t))
    for d in (domain(web),domain(em)):
      if d: dm.setdefault(d,[]).append((kid,t,norm(city)))
  return nc,dm
nc,dm=index()
import re
def names(n): return [n]+re.findall(r'\(([^)]+)\)',n)+[re.sub(r'\s*\([^)]*\)','',n)]  # 'Shop X (Firma Y)' -> beide Namen
def by_name(r):  # Name+Ort; Kontakte ohne Ort (z.B. aus bexio) auch nur über den Namen
  return next((nc[k] for x in names(r['name']) for k in ((norm(x),norm(r.get('city'))),(norm(x),'')) if k in nc),None)
for r in csv.DictReader(open(p,encoding='utf-8')):
  r={(k or '').strip().lower():(v or '').strip() for k,v in r.items()}
  if r.get('status')!=status:
    # andere Zeilen (z.B. 'bestehend'): nur Anreicherung bestehender Kontakte (aktiv, prioritaet, ...), nie neu anlegen
    hit=by_name(r) or next((dm[d][0][:2] for d in (domain(r.get('website')),domain(r.get('email'))) if d and d in dm),None)
    if hit:
      ex=json.loads(c.execute('select extra from customers where id=?',(hit[0],)).fetchone()[0] or '{}')
      add={k:v for k,v in r.items() if k not in KNOWN and v and k not in ex}
      if add: ex.update(add); c.execute('update customers set extra=? where id=?',(json.dumps(ex,ensure_ascii=False),hit[0])); st['bestehende Kontakte angereichert']+=1
    continue
  st['gelesen']+=1
  hit=by_name(r); branch=None
  if not hit:
    for d in (domain(r.get('website')),domain(r.get('email'))):
      for kid,t,cty in dm.get(d or '',[]):
        # gleiche Domain: Kunde/Firma -> Duplikat; anderer Interessent in anderer Stadt -> eigene Filiale
        if t!='Interessent' or not cty or not norm(r.get('city')) or cty==norm(r.get('city')): hit=(kid,t); break
        branch=d
      if hit: break
  extra={k:v for k,v in r.items() if k not in KNOWN and v}
  if r.get('type'): extra['shop_typ']=r['type']
  if r.get('note'): extra['notiz']=r['note']
  vals=dict(company_name=r['name'],contact_person=r.get('ansprechperson') or r.get('contact_person') or None,email=r.get('email') or None,
    phone=r.get('mobile') or r.get('phone') or None,city=r.get('city') or None,canton=r.get('canton') or None,website=r.get('website') or None,
    address=r.get('address') or None,source=r.get('source') or None,priority=r.get('prioritaet') or r.get('priority') or None,
    language=r.get('sprache') or r.get('language') or None)
  if hit:
    kid,t=hit
    if t=='Interessent':
      sets=','.join(f"{k}=coalesce(nullif({k},''),?)" for k in vals)
      c.execute(f"update customers set {sets},updated_at=datetime('now') where id=?",(*vals.values(),kid)); st['Duplikat (Interessent ergänzt)']+=1
      ex=json.loads(c.execute('select extra from customers where id=?',(kid,)).fetchone()[0] or '{}'); ex.update({k:v for k,v in extra.items() if k not in ex})
      c.execute('update customers set extra=? where id=?',(json.dumps(ex,ensure_ascii=False) if ex else None,kid))
    else: st[f'Duplikat übersprungen ({t})']+=1; skipped.append(f"{r['name']} ({r.get('city')}) = Kontakt #{kid} [{t}]")
    continue
  kid=c.execute('insert into customers(name,customer_type,tags,extra,'+','.join(vals)+') values(?,?,?,?,'+','.join('?'*len(vals))+')',
    (r['name'],'Interessent','Scout: '+p.name+(f', Filiale ({branch})' if branch else ''),json.dumps(extra,ensure_ascii=False) if extra else None,*vals.values())).lastrowid
  st['neu importiert']+=1; st['davon Filialen (gleiche Domain, andere Stadt)']+=bool(branch)
  nc.setdefault((norm(r['name']),norm(r.get('city'))),(kid,'Interessent'))
  for d in (domain(r.get('website')),domain(r.get('email'))):
    if d: dm.setdefault(d,[]).append((kid,'Interessent',norm(r.get('city'))))
n=enroll_prospects(c)
if '--dry-run' in sys.argv: c.rollback(); print('DRY-RUN')
else: c.commit()
print(dict(st)); print('neu in Kampagne eingeschrieben:',n); [print('  übersprungen:',s) for s in skipped]
