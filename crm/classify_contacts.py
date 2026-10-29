"""Kundentypen + Tags aus bexio-Kontaktgruppen setzen (idempotent, schreibt NIE nach bexio).
Quelle: bexio_contact_groups.json (nur IDs/Gruppen/Ort/URL). Mit --refresh wird die Datei per GET (read-only) neu
aus bexio geladen; Token nur aus Env BEXIO_API_TOKEN. Usage: python3 classify_contacts.py [--refresh] [--dry-run]"""
import json, sys, os, csv, pathlib, re, collections, urllib.request
from crmlib import norm, domain
from migrate import migrate
from db import connect
D=pathlib.Path(__file__).parent; GF=D/'bexio_contact_groups.json'
def get(path):
  r=urllib.request.Request('https://api.bexio.com'+path,headers={'Authorization':'Bearer '+os.environ['BEXIO_API_TOKEN'],'Accept':'application/json'},method='GET')
  return json.load(urllib.request.urlopen(r,timeout=60))
if '--refresh' in sys.argv:
  cs=[];off=0
  while True:
    d=get(f'/2.0/contact?limit=500&offset={off}'); cs+=d
    if len(d)<500: break
    off+=500
  g=get('/2.0/contact_group')
  json.dump({'groups':{x['id']:re.sub(r'\s+',' ',x['name']) for x in g},'contacts':{str(o['id']):{'groups':[int(x) for x in (o.get('contact_group_ids') or '').split(',') if x],
    'contact_type_id':o.get('contact_type_id'),'city':o.get('city'),'url':o.get('url')} for o in cs}},open(GF,'w'),ensure_ascii=False); os.chmod(GF,0o600)
G=json.load(open(GF)); GN={int(k):v for k,v in G['groups'].items()}
TYPE={1:'Businesskunde',10:'Businesskunde',11:'Businesskunde',12:'Businesskunde',17:'Businesskunde',9:'Interessent',
      2:'Endkunde',15:'Endkunde',13:'Endkunde',14:'Endkunde',18:'Endkunde',3:'Lieferant',19:'Lieferant',7:'Sonstige',8:'Sonstige',20:'Sonstige'}
PRIO=['Interessent','Businesskunde','Lieferant','Endkunde','Sonstige']  # bei mehreren Gruppen
BRAND={1:'Bernvapes',2:'Bernvapes',9:'Bernvapes',10:'Bernvapes',11:'Bernvapes',15:'Bernvapes',12:'Trankwerk',13:'Trankwerk',14:'Bastelwerk',17:'Hardie',18:'Hardie',19:'Hardie'}
VAPE=re.compile(r'vape|vaper|dampf|smoke|e-?zig|liquid|steam|tabak|trafik|cbd|nebel|aromen',re.I)
# bestehende Shops aus CSV
csvp=next((p for p in (D/'vapeshops_schweiz.csv',D.parent/'vapeshops_schweiz.csv') if p.exists()),None)
best_n,best_d=set(),set()
if csvp:
  for r in csv.DictReader(open(csvp,encoding='utf-8')):
    if r['status']=='bestehend':
      best_n.add(norm(r['name'])); [best_d.add(x) for x in (domain(r['website']),domain(r['email'])) if x]
migrate()
c=connect(); cnt=collections.Counter(); brands=collections.Counter(); why=collections.Counter()
rows=c.execute("select id,bexio_contact_id,name,email,city,website,customer_type,converted_at from customers where bexio_contact_id is not null").fetchall()
for kid,bid,name,email,city,web,ctype,conv in rows:
  b=G['contacts'].get(str(bid))
  if not b: cnt['nicht in bexio-Datei']+=1; continue
  gs=b['groups']; types=[TYPE[g] for g in gs if g in TYPE]
  if types: t=sorted(types,key=PRIO.index)[0]; why['Gruppe']+=1
  else:
    isco=b['contact_type_id']==1; shop=norm(name) in best_n or domain(email) in best_d or domain(b.get('url')) in best_d
    if shop: t='Businesskunde'; why['CSV bestehend']+=1
    elif isco and VAPE.search((name or '')+' '+(email or '')+' '+(b.get('url') or '')): t='Businesskunde'; why['Firma (Vape-Branche)']+=1
    elif isco: t='Sonstige'; why['Firma ohne Gruppe (Dienstleister etc.)']+=1
    else: t='Endkunde'; why['Person ohne Gruppe']+=1
  if conv and t=='Interessent': t='Businesskunde'  # lokal bereits umgewandelt
  br=sorted({BRAND[g] for g in gs if g in BRAND}); brands[', '.join(br) or '(keine Marke)']+=1
  tags=[GN.get(g,f'Gruppe {g}') for g in gs]+[f'Marke: {x}' for x in br]
  cn=name if b['contact_type_id']==1 else None
  c.execute("update customers set customer_type=?,tags=?,brand=?,bexio_groups=?,company_name=coalesce(company_name,?),city=coalesce(nullif(city,''),?),website=coalesce(nullif(website,''),?) where id=?",
    (t,', '.join(tags) or None,', '.join(br) or None,','.join(map(str,gs)) or None,cn,b.get('city'),b.get('url'),kid)); cnt[t]+=1
  if t=='Lieferant' and not c.execute('select 1 from suppliers where name=?',(name,)).fetchone():
    c.execute('insert into suppliers(name,email,notes) values(?,?,?)',(name,email,'aus bexio-Gruppe '+', '.join(GN.get(g,'') for g in gs)))
from crmlib import enroll_prospects
n=enroll_prospects(c)
if '--dry-run' in sys.argv: c.rollback(); print('DRY-RUN')
else: c.commit()
print('Typen:',dict(cnt)); print('Grund:',dict(why)); print('Marken:',dict(brands)); print('neu in Kampagne eingeschrieben:',n)
