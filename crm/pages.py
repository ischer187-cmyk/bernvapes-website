"""Bernvapes Steuerzentrale – HTML pages. Server and auth live in app.py."""
import json, os, html, re, pathlib, datetime, contextvars
from db import connect
CSRF = contextvars.ContextVar('crm_csrf', default='')
from crmlib import STATI, CONTACTED, RESPONDED
from pricing import TIER_LABEL, TIERS
D=pathlib.Path(__file__).parent
def db():
    return connect()
STAGES=[('anfrage','Anfrage'),('angebot','Angebot'),('verhandlung','Verhandlung'),('gewonnen','Gewonnen'),('verloren','Verloren')]
WEBHOOKS={'order':'Neue Bestellung (Checkout) – aktiv','payment':'Zahlungsstatus (Stub)','oneguard':'OneGuard Altersprüfung (Stub)',
          'newsletter-doi':'Newsletter Double-Opt-in (Stub)','contact':'Kontakt-/B2B-Formular (Stub)'}
REQ={'order':['event_id','email','items'],'payment':['event_id','order_ref','status'],'oneguard':['event_id','email','verified','method'],
     'newsletter-doi':['event_id','email','action'],'contact':['event_id','email','message']}
PAID=('bezahlt','paid')
e=lambda s:html.escape('' if s is None else str(s))
def chf(v): return "CHF "+f"{(v or 0):,.2f}".replace(',',"'")
CSS=""":root{--bg:#0b0f14;--card:#121922;--line:#1f2a36;--tx:#e6edf3;--mu:#8b98a5;--cy:#22d3ee}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--tx)}
header{display:flex;justify-content:space-between;align-items:center;padding:14px 28px;border-bottom:1px solid var(--line)}
header h1{margin:0;font-size:20px}header h1 span{color:var(--cy)}header a{color:inherit;text-decoration:none}
nav.top{display:flex;gap:4px;padding:10px 28px;border-bottom:1px solid var(--line);flex-wrap:wrap}nav.top a,.tabs a{color:var(--tx);text-decoration:none;padding:7px 14px;border-radius:8px;border:1px solid var(--line);background:#1b2633;font-size:14px}
nav.top a.on,.tabs a.on{background:var(--cy);color:#001;border-color:var(--cy);font-weight:600}nav.top a:hover,.tabs a:hover{border-color:var(--cy)}
h2{font-size:15px;color:var(--cy);margin:0 0 12px;text-transform:uppercase;letter-spacing:.08em}h3{margin:0 0 8px;font-size:15px}
.live{background:#4ade8022;color:#4ade80;border:1px solid #4ade80;padding:6px 12px;border-radius:20px;font-weight:600;font-size:13px}
main{padding:24px 28px;display:grid;gap:22px}section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.kpi{background:#0f151d;border:1px solid var(--line);border-radius:10px;padding:12px}
.kpi b{display:block;font-size:22px;margin-top:4px}.kpi small{color:var(--mu)}.warn b{color:#fbbf24}
table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--mu);font-weight:500}
a{color:var(--cy)}.chip{padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600;background:#8b98a522;color:var(--mu);white-space:nowrap}
.neu,.c-B{background:#fbbf2422;color:#fbbf24}.bezahlt,.c-A{background:#22d3ee22;color:var(--cy)}.versendet,.ok{background:#4ade8022;color:#4ade80}.no,.c-C{background:#f8717122;color:#f87171}
button,.btn{background:#1b2633;color:var(--tx);border:1px solid var(--line);border-radius:8px;padding:6px 10px;cursor:pointer;font-size:12px;margin-right:4px;text-decoration:none;display:inline-block}button:hover{border-color:var(--cy)}
button[disabled]{opacity:.5;cursor:not-allowed}.pri{background:var(--cy);color:#001;border:none;font-weight:600}
input,select,textarea{background:#0f151d;border:1px solid var(--line);color:var(--tx);padding:8px;border-radius:8px;font:inherit;font-size:14px}
.tabs{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:14px}form.inline{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:10px 0}form.i{display:inline}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}.card{background:#0f151d;border:1px solid var(--line);border-radius:10px;padding:14px}
.mu{color:var(--mu);font-size:13px}.board{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}.col{background:#0f151d;border:1px solid var(--line);border-radius:10px;padding:10px;min-height:160px}
.deal{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px;margin-bottom:8px}.hist{border-top:1px solid var(--line);padding:8px 0;font-size:13px}"""
NAV=[('/','Übersicht'),('/bestellungen','Bestellungen'),('/kunden','Kunden'),('/konten','Konten'),('/haendler','Händler'),('/preise','Preise'),('/pipeline','Pipeline'),('/kampagnen','Kampagnen'),('/aufgaben','Aufgaben'),('/agenten','Agenten'),('/steuerung','Steuerung')]
def page(title,body,on='/',csrf=''):
  n=''.join(f'<a href="{h}" class="{"on" if h==on else ""}">{t}</a>' for h,t in NAV)
  tok = csrf or CSRF.get() or ''
  return (f'<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="csrf-token" content="{e(tok)}"><title>{e(title)} · Bernvapes Steuerzentrale</title>'
    f'<link rel="icon" href="/fox.png"><style>{CSS}</style></head><body><header><h1><a href="/"><img src="/fox.png" alt="Bernvapes Fuchs" style="height:44px;width:auto;vertical-align:middle;margin-right:12px">Bernvapes <span>Steuerzentrale</span></a></h1>'
    f'<div style="display:flex;gap:10px;align-items:center"><div class="live">● Live-Daten · lokal</div>'
    f'<form method="post" action="/logout" class="i"><button>Abmelden</button></form></div></header><nav class="top">{n}</nav><main>{body}</main>'
    f'<script>document.addEventListener("submit",function(ev){{var f=ev.target;if(!f||!f.querySelector||f.querySelector("[name=csrf]"))return;var m=document.querySelector("meta[name=csrf-token]");if(!m||!m.content)return;var i=document.createElement("input");i.type="hidden";i.name="csrf";i.value=m.content;f.appendChild(i);}});</script></body></html>')
def kpis(items): return '<div class="kpis">'+''.join(f'<div class="kpi{" warn" if w else ""}"><small>{e(l)}</small><b>{e(v)}</b></div>' for l,v,w in items)+'</div>'
def empty(t,cols=1): return f'<tr><td colspan={cols} class="mu">{t}</td></tr>'
def chip(s,cls=None): return f'<span class="chip {cls or e(s)}">{e(s)}</span>'
def prio(p): return chip(p[0],'c-'+p[0]) if p and p[:1] in 'ABC' else '<span class="mu">–</span>'
# ---------- Übersicht ----------
def prospect_kpis(c):
  one=lambda s,a=():c.execute(s,a).fetchone()[0]
  return [('Potenzielle Kunden',one("select count(*) from customers where customer_type='Interessent'"),0),
   ('Angeschrieben',one(f"select count(distinct customer_id) from campaign_members where status in ({','.join('?'*len(CONTACTED))})",CONTACTED),0),
   ('Geantwortet',one(f"select count(distinct customer_id) from campaign_members where status in ({','.join('?'*len(RESPONDED))})",RESPONDED),0),
   ('Umgewandelt',one("select count(*) from customers where converted_at is not null"),0)]
def uebersicht(q, csrf=''):
  c=db(); one=lambda s,a=():c.execute(s,a).fetchone()[0]
  R="from orders where coalesce(is_test,0)=0 and status<>'storniert'"
  o=lambda w:one(f"select count(*) {R} and {w}"); u=lambda w:one(f"select coalesce(sum(total_chf),0) {R} and {w}")
  T="date(created_at,'localtime')=date('now','localtime')"; W="date(created_at,'localtime')>=date('now','localtime','weekday 1','-7 days')"; M="strftime('%Y-%m',created_at,'localtime')=strftime('%Y-%m','now','localtime')"
  open_pay=one(f"select count(*) {R} and coalesce(payment_status,'offen') not in ('bezahlt','paid')")
  noage=one("select count(distinct cu.id) from customers cu join orders o on o.customer_id=cu.id where coalesce(o.is_test,0)=0 and cu.customer_type='Endkunde' and cu.age_verified_at is null")
  k1=kpis([('Bestellungen heute',o(T),0),('Bestellungen Woche',o(W),0),('Bestellungen Monat',o(M),0),('Umsatz heute',chf(u(T)),0),('Umsatz Woche',chf(u(W)),0),('Umsatz Monat',chf(u(M)),0),
    ('Offene Zahlungen',open_pay,open_pay>0),('Fehlende Alterschecks',noage,noage>0)])
  days=[(datetime.date.today()-datetime.timedelta(days=13-i)).isoformat() for i in range(14)]
  rev=dict(c.execute(f"select date(created_at,'localtime') d,sum(total_chf) {R} and d>=? group by d",(days[0],)).fetchall())
  mx=max([rev.get(d) or 0 for d in days]+[1]); bars=''
  for i,d in enumerate(days):
    h=(rev.get(d) or 0)/mx*80; bars+=f'<rect x="{i*40+4}" y="{88-h:.1f}" width="30" height="{max(h,1):.1f}" rx="4" fill="{"#22d3ee" if i==13 else "#22d3ee55"}"><title>{d}: {chf(rev.get(d))}</title></rect>'
  rec=c.execute('select o.*,cu.name cn from orders o left join customers cu on cu.id=o.customer_id order by o.id desc limit 8').fetchall()
  tc=one('select count(*) from orders where is_test=1')
  return page('Übersicht',f'''<section><h2>Live-Leiste</h2>{k1}<p class="mu">Umsatz letzte 14 Tage (CHF, echte Bestellungen ohne Tests{f", {tc} Testbestellung(en) ausgeblendet" if tc else ""})</p>
  <svg width="100%" height="90" viewBox="0 0 560 90" preserveAspectRatio="none">{bars}</svg></section>
  <section><h2>Neukunden-Akquise</h2>{kpis(prospect_kpis(c))}<p class="mu"><a href="/kunden?tab=neu">Potenzielle Neukunden</a> · <a href="/kampagnen">Kampagnen</a></p></section>
  <section><h2>Eingehende Bestellungen</h2><table>{OH.format("<th>Kunde</th>")}{order_rows(rec) or empty("Noch keine Bestellungen.",8)}</table><p><a href="/bestellungen">Alle Bestellungen →</a></p></section>''','/')
# ---------- Bestellungen ----------
OH='<tr><th>Nr.</th>{}<th>Ext. Ref</th><th>Status</th><th>Zahlung</th><th>Total</th><th>Datum</th><th>Aktionen</th></tr>'
def order_rows(rows,cust=True):
  out=''
  for o in rows:
    act=('' if (o['payment_status'] or '') in PAID else f'<form class="i" method="post" action="/bestellung/{o["id"]}/aktion"><input type=hidden name=a value=bezahlt><button>Als bezahlt</button></form>')+\
        ('' if o['status']=='versendet' else f'<form class="i" method="post" action="/bestellung/{o["id"]}/aktion"><input type=hidden name=a value=versendet><button>Versendet</button></form>')
    out+=(f'<tr><td><a href="/bestellung/{o["id"]}">#{o["id"]}</a></td>'+(f'<td><a href="/kontakt/{o["customer_id"]}">{e(o["cn"])}</a></td>' if cust else '')+
      f'<td>{e(o["external_ref"])}</td><td>{chip(o["status"])}</td><td>{chip(o["payment_status"] or "offen","bezahlt" if (o["payment_status"] or "") in PAID else "neu")}</td><td>{chf(o["total_chf"]) if (o["currency"] or "CHF")=="CHF" else e(o["currency"])+" "+e(o["total_chf"])}</td>'
      f'<td>{e((o["created_at"] or "")[:16])} {chip("TEST","no") if o["is_test"] else ""}</td><td>{act}</td></tr>')
  return out
def bestellungen(q):
  rows=db().execute('select o.*,cu.name cn from orders o left join customers cu on cu.id=o.customer_id order by o.id desc limit 500').fetchall()
  return page('Bestellungen',f'<section><h2>Bestellungen ({len(rows)})</h2><table>{OH.format("<th>Kunde</th>")}{order_rows(rows) or empty("Noch keine Bestellungen.",8)}</table></section>','/bestellungen')
def bestellung(oid):
  c=db(); o=c.execute('select o.*,cu.name cn,cu.email ce from orders o left join customers cu on cu.id=o.customer_id where o.id=?',(oid,)).fetchone()
  if not o: return None
  it=c.execute('select * from order_items where order_id=?',(oid,)).fetchall()
  ih=''.join(f'<tr><td>{e(i["article"])}</td><td>{e(i["qty"])}</td><td>{e(i["unit_chf"])}</td></tr>' for i in it) or empty('Keine Positionen.',3)
  info=(f'<table><tr><td>Kunde</td><td><a href="/kontakt/{o["customer_id"]}">{e(o["cn"])}</a> · {e(o["ce"])}</td></tr><tr><td>Externe Ref.</td><td>{e(o["external_ref"])}</td></tr>'
   f'<tr><td>Kanal</td><td>{e(o["channel"])}</td></tr><tr><td>Status</td><td>{chip(o["status"])}</td></tr><tr><td>Zahlungsart</td><td>{e(o["payment_method"] or "–")}</td></tr><tr><td>Zahlung</td><td>{e(o["payment_status"])} {e(o["payment_provider"] or "")}</td></tr>'
   f'<tr><td>Total</td><td><b>{e(o["currency"] or "CHF")} {(o["total_chf"] or 0):.2f}</b></td></tr><tr><td>Erstellt</td><td>{e(o["created_at"])}</td></tr><tr><td>Test</td><td>{chip("TEST","no") if o["is_test"] else "nein"}</td></tr></table>')
  return page(f'Bestellung #{oid}',f'<section><p><a href="/bestellungen">← Bestellungen</a></p><h2>Bestellung #{oid}</h2><div class="grid2"><div class="card"><h3>Details</h3>{info}</div><div class="card"><h3>Positionen</h3><table><tr><th>Artikel</th><th>Menge</th><th>CHF/Stk</th></tr>{ih}</table></div></div></section>','/bestellungen')
# ---------- Kunden ----------
TABS=[('end','Endkunden',"customer_type='Endkunde'"),('biz','Businesskunden',"customer_type='Businesskunde'"),('neu','Potenzielle Neukunden',"customer_type='Interessent'"),
      ('weitere','Weitere (Lieferanten/Sonstige)',"customer_type not in ('Endkunde','Businesskunde','Interessent') or customer_type is null")]
def kunden(q):
  c=db(); tab=q.get('tab',['end'])[0]; tab=tab if tab in [t[0] for t in TABS] else 'end'; s=q.get('q',[''])[0].strip(); pr=q.get('prio',[''])[0]; ks=q.get('ks',[''])[0]
  cnt={k:c.execute(f'select count(*) from customers where {w}').fetchone()[0] for k,_,w in TABS}
  tabs=''.join(f'<a href="/kunden?tab={k}" class="{"on" if k==tab else ""}">{t} ({cnt[k]})</a>' for k,t,_ in TABS)
  w=[dict((k,v) for k,_,v in TABS)[tab]]; a=[]
  if s: w.append("(name like ? or company_name like ? or email like ? or phone like ? or city like ? or contact_person like ? or tags like ?)"); a+=[f'%{s}%']*7
  if tab=='neu' and pr in ('A','B','C'): w.append('substr(priority,1,1)=?'); a.append(pr)
  if tab=='neu' and ks in dict(STATI): w.append('id in (select customer_id from campaign_members where status=?)'); a.append(ks)
  base=f'select cu.*,(select count(*) from orders o where o.customer_id=cu.id) n_o,(select coalesce(sum(total_chf),0) from orders o where o.customer_id=cu.id and coalesce(is_test,0)=0) rev,(select status from campaign_members m where m.customer_id=cu.id order by id desc limit 1) ms from customers cu where ({") and (".join(w)})'
  order=" order by case substr(priority,1,1) when 'A' then 1 when 'B' then 2 when 'C' then 3 else 4 end, name collate nocase" if tab=='neu' else ' order by name collate nocase'
  rows=c.execute(base+order+' limit 1000',a).fetchall()
  hid=f'<input type=hidden name=tab value="{tab}">'
  extra=''
  if tab=='neu':
    extra=(f'<select name="prio"><option value="">Priorität: alle</option>'+''.join(f'<option {"selected" if pr==x else ""}>{x}</option>' for x in 'ABC')+'</select>'
      f'<select name="ks"><option value="">Kampagnen-Status: alle</option>'+''.join(f'<option value="{v}" {"selected" if ks==v else ""}>{t}</option>' for v,t in STATI)+'</select>')
  form=f'<form class="inline">{hid}<input name="q" value="{e(s)}" placeholder="Suchen (Name, Ort, E-Mail, Telefon, Tags)…" style="width:340px">{extra}<button class="pri">Suchen</button></form>'
  neuform=''
  if tab=='neu':
    neuform='''<form class="inline" method="post" action="/kunden/neu"><input name="company_name" placeholder="Shop / Firma" required><input name="email" type="email" placeholder="E-Mail" required><input name="contact_person" placeholder="Ansprechperson"><input name="city" placeholder="Ort"><input name="canton" placeholder="Kanton" style="width:80px"><select name="priority"><option value="">Prio</option><option>A</option><option>B</option><option>C</option></select><input name="language" placeholder="Sprache (de/fr/it/en)" style="width:150px"><button class="pri">Interessent anlegen</button></form>'''
  if tab=='neu':
    head='<tr><th>Prio</th><th>Shop</th><th>Ansprechperson</th><th>Ort</th><th>Kanton</th><th>Sprache</th><th>Kontakt</th><th>Aktiv</th><th>Kampagne</th></tr>'
    def ex(r):
      try: return json.loads(r['extra'] or '{}')
      except ValueError: return {}
    tr=''.join(f'<tr><td>{prio(r["priority"])}</td><td><a href="/kontakt/{r["id"]}">{e(r["company_name"] or r["name"])}</a>{"<br><span class=mu>bexio</span>" if r["bexio_contact_id"] else ""}</td><td>{e(r["contact_person"]) or "<span class=mu>–</span>"}</td>'
      f'<td>{e(r["city"])}</td><td>{e(r["canton"])}</td><td>{e(r["language"]) or "<span class=mu>–</span>"}</td><td>{e(r["email"])}<br><span class="mu">{e(r["phone"])}</span></td><td class="mu">{e((ex(r).get("aktiv") or "")[:40])}</td><td>{chip(dict(STATI).get(r["ms"],"nicht eingeschrieben"),"neu" if r["ms"] else "no")}</td></tr>' for r in rows)
    cols=9
  else:
    head='<tr><th>Name</th><th>Ort</th><th>E-Mail / Telefon</th><th>Bestellungen</th><th>Umsatz</th><th>Newsletter</th><th>Tags</th></tr>'
    tr=''.join(f'<tr><td><a href="/kontakt/{r["id"]}">{e(r["name"])}</a>{" <span class=mu>("+e(r["customer_type"])+")</span>" if tab=="weitere" else ""}</td><td>{e(r["city"])}</td><td>{e(r["email"])}<br><span class="mu">{e(r["phone"])}</span></td><td>{r["n_o"]}</td><td>{chf(r["rev"])}</td>'
      f'<td>{chip("✓ Einwilligung","versendet") if r["consent_newsletter"] else chip("keine","neu")}</td><td class="mu">{e(r["tags"])}</td></tr>' for r in rows)
    cols=7
  return page('Kunden',f'<section><h2>Kunden</h2><div class="tabs">{tabs}</div>{form}{neuform}<p class="mu">{len(rows)} Treffer{" (max. 1000)" if len(rows)==1000 else ""}</p><table>{head}{tr or empty("Keine Einträge.",cols)}</table></section>','/kunden')
def kontakt(cid):
  c=db(); r=c.execute('select * from customers where id=?',(cid,)).fetchone()
  if not r: return None
  notes=c.execute('select * from notes where customer_id=? order by created_at desc,id desc',(cid,)).fetchall()
  tasks=c.execute('select * from tasks where customer_id=? order by done,due_date',(cid,)).fetchall()
  ords=c.execute('select o.*,null cn from orders o where customer_id=? order by created_at desc',(cid,)).fetchall()
  mem=c.execute('select m.*,ca.name can,ca.status cst,ca.active cact from campaign_members m join campaigns ca on ca.id=m.campaign_id where customer_id=?',(cid,)).fetchall()
  ev=c.execute('select ev.*,ca.name can from campaign_events ev left join campaigns ca on ca.id=ev.campaign_id where customer_id=? order by ev.id desc',(cid,)).fetchall()
  nh=''.join(f'<div class="hist">{chip(n["channel"])} <span class="mu">{e(n["created_at"])} · {e(n["author"])}</span><br>{e(n["body"])}</div>' for n in notes) or '<p class="mu">Noch keine Notizen.</p>'
  tk=''.join(f'<tr><td>{"✅" if t["done"] else "⬜"} {e(t["title"])}</td><td>{e(t["due_date"])}</td></tr>' for t in tasks) or empty('Keine Aufgaben.')
  oh=(OH.format('')+order_rows(ords,False)) if ords else empty('Noch keine Bestellungen.')
  yn=lambda v:chip('ja','ok') if v else chip('nein')
  age=f'{chip("geprüft","ok")} {e(r["age_verified_at"])} · {e(r["age_verify_method"])}' if r['age_verified_at'] else chip('nicht geprüft','no')
  try: ex=json.loads(r['extra'] or '{}')
  except ValueError: ex={}
  F=[('Typ',chip(r['customer_type'])+(f' <span class="mu">umgewandelt {e(r["converted_at"])}</span>' if r['converted_at'] else '')),('Firma/Shop',e(r['company_name'])),('Ansprechperson',e(r['contact_person'])),
     ('E-Mail',e(r['email'])),('Telefon',e(r['phone'])),('Adresse',e(r['address'])),('Ort',e(r['city'])),('Kanton',e(r['canton'])),
     ('Website',f'<a href="{e(r["website"])}" target="_blank" rel="noopener">{e(r["website"])}</a>' if r['website'] else ''),('Priorität',e(r['priority'])),('Sprache',e(r['language'])),('Quelle',e(r['source'])),
     ('Tags',e(r['tags'])),('bexio-ID',e(r['bexio_contact_id'])),('Nikotin (mg)',e(r['nicotine_mg'])),('Alter 18+',age+'<br><span class="mu">Nur Datum + Methode, keine Ausweisdaten</span>'),
     ('Newsletter',yn(r['consent_newsletter'])),('WhatsApp',yn(r['consent_whatsapp']))]+[(k.replace('_',' ').capitalize(),e(v)) for k,v in ex.items()]
  info='<table>'+''.join(f'<tr><td class="mu" style="width:150px">{k}</td><td>{v}</td></tr>' for k,v in F if v)+'</table>'
  isp=r['customer_type']=='Interessent'
  camp=''
  for m in mem:
    ctl=(f'<form class="inline" method="post" action="/kampagne/mitglied/{m["id"]}/status"><select name="status">'+''.join(f'<option value="{v}" {"selected" if v==m["status"] else ""}>{t}</option>' for v,t in STATI)+
         '</select><input name="note" placeholder="Notiz (optional)"><button class="pri">Status setzen</button></form><button disabled title="Kein Versandanbieter angebunden">✉ Versand nicht konfiguriert</button>') if isp else '<p class="mu">Kampagnen-Aktionen nur für Interessenten. Verlauf bleibt erhalten.</p>'
    camp+=f'<div class="card" style="margin-bottom:10px"><b>{e(m["can"])}</b> {chip(m["cst"])} {chip("inaktiv","no") if not m["cact"] else chip("aktiv","ok")}<br>Status: {chip(dict(STATI).get(m["status"]),"neu")}{ctl}</div>'
  eh=''.join(f'<div class="hist"><span class="mu">{e(x["created_at"])} · {e(x["author"])} · {e(x["can"])}</span><br>{e(dict(STATI).get(x["old_status"],x["old_status"]) or "–")} → <b>{e(dict(STATI).get(x["new_status"],x["new_status"]))}</b> {e(x["note"] or "")}</div>' for x in ev)
  conv=f'<form method="post" action="/kontakt/{cid}/umwandeln" onsubmit="return confirm(\'Zu Businesskunde machen?\')"><button class="pri">Zu Businesskunde machen</button></form>' if isp else ''
  deal=c.execute('select * from dealer_accounts where customer_id=? order by id desc limit 1',(cid,)).fetchone()
  tiers=''.join(f'<option value="{t}" {"selected" if deal and deal["price_tier"]==t else ""}>{TIER_LABEL[t]}</option>' for t in TIERS)
  if deal:
    ov=c.execute('select o.unit_chf,p.name,p.sku from price_overrides o join products p on p.id=o.product_id where o.dealer_id=?',(deal['id'],)).fetchall()
    ovh=''.join(f'<tr><td>{e(x["name"])}</td><td>{e(x["sku"])}</td><td>{x["unit_chf"]:.2f}</td></tr>' for x in ov) or empty('Keine Sonderpreise.',3)
    prods=c.execute('select sku,name from products where coalesce(active,1)=1 order by name').fetchall()
    popts=''.join(f'<option value="{e(p["sku"])}">{e(p["name"])}</option>' for p in prods)
    verified=f'{chip("Firma geprüft","ok")} {e(deal["company_verified_at"])} · {e(deal["company_verify_method"])}' if deal['company_verified_at'] else chip('Firma nicht geprüft','no')
    actions=''
    if deal['status']!='approved':
      actions+=f'<form class="i" method="post" action="/haendler/{deal["id"]}/aktion"><input type=hidden name=a value=approve><button class="pri">Freigeben</button></form>'
    if deal['status']!='rejected':
      actions+=f'<form class="i" method="post" action="/haendler/{deal["id"]}/aktion"><input type=hidden name=a value=reject><button>Ablehnen</button></form>'
    mail=c.execute('select body,created_at from mail_log where to_addr=? order by id desc limit 1',(deal['email'],)).fetchone()
    mailb=f'<pre class="mu" style="white-space:pre-wrap">{e(mail["body"])}</pre><p class="mu">{e(mail["created_at"])} · nicht versendet (Log-Treiber)</p>' if mail else '<p class="mu">Noch keine Einladung im Log.</p>'
    dealer_html=(f'<section><h2>Händlerkonto</h2><p>{chip(deal["status"])} {chip(TIER_LABEL.get(deal["price_tier"],deal["price_tier"]))} · {e(deal["email"])}<br>{verified}'
      f'<br><span class="mu">B2B: Firmenprüfung (UID/Einladung) statt Altersprüfung pro Person. Zahlungsart später Rechnung. bexio-Schreibweg ist aus.</span></p>{actions}'
      f'<form class="inline" method="post" action="/haendler/{deal["id"]}/stufe"><select name="tier">{tiers}</select><button class="pri">Stufe speichern</button></form>'
      f'<h3>Sonderpreise</h3><table><tr><th>Produkt</th><th>SKU</th><th>CHF</th></tr>{ovh}</table>'
      f'<form class="inline" method="post" action="/haendler/{deal["id"]}/preis"><select name="sku">{popts}</select><input name="unit_chf" type="number" step="0.05" min="0" placeholder="CHF" required><button class="pri">Override</button></form>'
      f'<h3>Einladungslink</h3>{mailb}</section>')
  else:
    dealer_html=(f'<section><h2>Händlerportal</h2><p class="mu">Einladung mit einmaligem Link. Es wird keine E-Mail verschickt; der Link steht danach hier und unter Steuerung.</p>'
      f'<form class="inline" method="post" action="/kontakt/{cid}/einladung"><input name="email" type="email" value="{e(r["email"] or "")}" placeholder="E-Mail" required>'
      f'<select name="tier">{tiers or "".join(f"<option value={t}>{TIER_LABEL[t]}</option>" for t in TIERS)}</select><button class="pri">Einladung erzeugen</button></form></section>')
  tabk={'Endkunde':'end','Businesskunde':'biz','Interessent':'neu'}.get(r['customer_type'],'weitere')
  b=f'''<section><p><a href="/kunden?tab={tabk}">← Kunden</a></p><h2>{e(r["company_name"] or r["name"])}</h2>{conv}</section><div class="grid2"><section><h2>Stammdaten</h2>{info}</section>
  <section><h2>Notizen & Verlauf</h2><form class="inline" method="post" action="/kontakt/{cid}/notiz"><select name="channel"><option>notiz</option><option>telefon</option><option>email</option><option>whatsapp</option><option>laden</option></select>
  <input name="body" placeholder="Notiz…" style="flex:1" required><button class="pri">Speichern</button></form>{nh}</section>
  <section><h2>Kampagnen</h2>{camp or '<p class="mu">In keiner Kampagne.</p>'}<h3 style="margin-top:12px">Kampagnen-Verlauf</h3>{eh or '<p class="mu">Kein Verlauf.</p>'}</section>
  <section><h2>Aufgaben</h2><form class="inline" method="post" action="/aufgaben/neu"><input type="hidden" name="customer_id" value="{cid}"><input name="title" placeholder="Aufgabe…" required><input type="date" name="due_date"><button class="pri">+</button></form><table>{tk}</table></section></div>
  <section><h2>Bestellungen</h2><table>{oh}</table></section>{dealer_html}'''
  return page(r['company_name'] or r['name'] or 'Kontakt',b,'/kunden')
# ---------- Pipeline / Kampagnen / Aufgaben / Agenten / Steuerung ----------
def pipeline(q):
  c=db(); cols=''
  for s,n in STAGES:
    ds=c.execute('select d.*,co.name con,cu.name cun from deals d left join companies co on co.id=d.company_id left join customers cu on cu.id=d.customer_id where stage=? order by updated_at desc',(s,)).fetchall()
    cards=''.join(f'''<div class="deal"><b>{e(d["title"])}</b><br><span class="mu">{e(d["con"] or d["cun"])} · {chf(d["value_chf"])}</span>
      <form method="post" action="/pipeline/{d["id"]}/stufe"><select name="stage" onchange="this.form.submit()">{''.join(f'<option value="{v}" {"selected" if v==s else ""}>{t}</option>' for v,t in STAGES)}</select></form></div>''' for d in ds)
    cols+=f'<div class="col"><h3>{n} ({len(ds)})</h3>{cards or "<p class=mu>–</p>"}</div>'
  form='''<form class="inline" method="post" action="/pipeline/neu"><input name="title" placeholder="Titel" required><input name="company" placeholder="Firma (Wiederverkäufer)"><input name="value_chf" type="number" step="0.05" placeholder="Wert CHF"><button class="pri">Deal anlegen</button></form>'''
  return page('Pipeline',f'<section><h2>B2B-Pipeline</h2>{form}<div class="board">{cols}</div></section>','/pipeline')
def kampagnen(q):
  c=db(); out=''
  for ca in c.execute('select * from campaigns order by id').fetchall():
    cnt=dict(c.execute('select status,count(*) from campaign_members where campaign_id=? group by status',(ca['id'],)).fetchall())
    k=kpis([(t,cnt.get(v,0),0) for v,t in STATI])
    mem=c.execute("select m.*,cu.name,cu.company_name,cu.city,cu.priority,cu.customer_type from campaign_members m join customers cu on cu.id=m.customer_id where campaign_id=? order by case substr(cu.priority,1,1) when 'A' then 1 when 'B' then 2 when 'C' then 3 else 4 end,cu.name",(ca['id'],)).fetchall()
    tr=''.join(f'<tr><td>{prio(m["priority"])}</td><td><a href="/kontakt/{m["customer_id"]}">{e(m["company_name"] or m["name"])}</a></td><td>{e(m["city"])}</td><td>{chip(m["customer_type"])}</td><td>{chip(dict(STATI)[m["status"]],"neu")}</td><td class="mu">{e(m["updated_at"])}</td></tr>' for m in mem)
    out+=(f'<section><h2>{e(ca["name"])}</h2><p>{chip(ca["status"])} {chip("aktiv","ok") if ca["active"] else chip("inaktiv","no")} <span class="mu">{e(ca["description"])}</span></p>'
      f'<p><button disabled title="Kein Versandanbieter angebunden">✉ Versand nicht konfiguriert</button> <span class="mu">Kein Mail-/SMS-Versand angebunden; Status wird manuell im Kontakt gepflegt.</span></p>{k}'
      f'<h3 style="margin-top:14px">Teilnehmer ({len(mem)})</h3><table><tr><th>Prio</th><th>Shop</th><th>Ort</th><th>Typ</th><th>Status</th><th>Geändert</th></tr>{tr or empty("Keine Teilnehmer.",6)}</table></section>')
  return page('Kampagnen',f'<section><h2>Akquise-KPIs</h2>{kpis(prospect_kpis(c))}</section>'+(out or '<section><p class="mu">Keine Kampagnen.</p></section>'),'/kampagnen')
def aufgaben(q):
  rows=db().execute('select t.*,cu.name cn from tasks t left join customers cu on cu.id=t.customer_id order by done,due_date is null,due_date').fetchall()
  tr=''.join(f'''<tr><td>{"✅" if t["done"] else "⬜"} {e(t["title"])}</td><td>{f'<a href="/kontakt/{t["customer_id"]}">{e(t["cn"])}</a>' if t["customer_id"] else ""}</td><td>{e(t["due_date"])}</td><td>{e(t["assignee"])}</td>
   <td>{"" if t["done"] else f'<form method="post" action="/aufgaben/{t["id"]}/erledigt"><button>Erledigt</button></form>'}</td></tr>''' for t in rows) or empty('Noch keine Aufgaben.',5)
  return page('Aufgaben','<section><h2>Aufgaben</h2><form class="inline" method="post" action="/aufgaben/neu"><input name="title" placeholder="Neue Aufgabe…" required style="width:320px"><input type="date" name="due_date"><input name="assignee" placeholder="Zuständig"><button class="pri">Hinzufügen</button></form>'
    f'<table><tr><th>Aufgabe</th><th>Kontakt</th><th>Fällig</th><th>Zuständig</th><th></th></tr>{tr}</table></section>','/aufgaben')
def agenten(q):
  return page('Agenten','''<section><h2>Agenten</h2><div class="grid2"><div class="card"><b>Newsletter-Bot</b> <span class="mu">○ in Vorbereitung</span><p class="mu">Noch nicht eingerichtet. Später nur für Kontakte mit bestätigter Einwilligung (Double-Opt-in), Entwürfe immer zur Freigabe.</p></div>
  <div class="card"><b>Verkaufs-Bot</b> <span class="mu">○ in Vorbereitung</span><p class="mu">Noch nicht eingerichtet. Später z. B. Nachfass-Entwürfe für Kampagnen an potenzielle Neukunden – nur Entwürfe, kein automatischer Versand.</p></div></div></section>''','/agenten')
def steuerung(q):
  c=db(); sec='gesetzt' if os.environ.get('CRM_WEBHOOK_SECRET') else 'NICHT gesetzt → alle Webhooks antworten 503'
  tr=''.join(f'<tr><td><code>POST /webhook/{k}</code></td><td>{v}</td><td><code>{", ".join(REQ[k])}</code></td></tr>' for k,v in WEBHOOKS.items())
  ev=c.execute('select * from webhook_events order by id desc limit 20').fetchall()
  eh=''.join(f'<tr><td>{e(x["received_at"])}</td><td>{e(x["source"])}</td><td>{e(x["event_id"])}</td><td>{e(x["status"])}</td></tr>' for x in ev) or empty('Noch keine Events.',4)
  sup=c.execute('select * from suppliers order by name').fetchall()
  sh=''.join(f'<tr><td>{e(s["name"])}</td><td>{e(s["contact_person"])}</td><td>{e(s["email"])}</td><td>{e(s["assortment"])}</td><td>{e(s["lead_time_days"])}</td></tr>' for s in sup) or empty('Noch keine Lieferanten.',5)
  mails=c.execute('select * from mail_log order by id desc limit 15').fetchall()
  mh=''.join(f'<tr><td>{e(m["created_at"])}</td><td>{e(m["to_addr"])}</td><td>{e(m["subject"])}</td><td><pre class="mu" style="white-space:pre-wrap;margin:0">{e(m["body"])}</pre></td></tr>' for m in mails) or empty('Noch keine Mails.',4)
  return page('Steuerung',f'''<section><h2>Webhooks</h2><p class="mu">Header <code>X-Bernvapes-Secret</code> = <code>CRM_WEBHOOK_SECRET</code> ({sec}). Nur lokal (127.0.0.1), nichts öffentlich verbunden.</p><table><tr><th>Endpunkt</th><th>Zweck</th><th>Pflichtfelder</th></tr>{tr}</table>
  <h3 style="margin-top:14px">Letzte Events (nur Metadaten)</h3><table>{eh}</table></section>
  <section><h2>Daten-Skripte</h2><p class="mu"><code>python3 migrate.py</code> (Schema) · <code>python3 classify_contacts.py [--refresh]</code> (Typen/Tags aus bexio-Gruppen, nur lesend) · <code>python3 import_prospects.py [datei.csv]</code> (Scout-Ergebnisse, wiederholbar mit Dedup) · Versand: nicht konfiguriert</p></section>
  <section><h2>Lieferanten ({len(sup)})</h2><form class="inline" method="post" action="/lieferanten/neu"><input name="name" placeholder="Name" required><input name="contact_person" placeholder="Kontaktperson"><input name="email" placeholder="E-Mail"><input name="assortment" placeholder="Sortiment"><input name="lead_time_days" type="number" placeholder="Lieferzeit Tage"><button class="pri">+</button></form>
  <table><tr><th>Name</th><th>Kontakt</th><th>E-Mail</th><th>Sortiment</th><th>Lieferzeit</th></tr>{sh}</table></section>
  <section><h2>Mail-Log (nichts wird versendet)</h2><p class="mu">Treiber <code>{e(os.environ.get("EMAIL_DRIVER") or "log")}</code>. Einladungslinks für den lokalen Test stehen hier.</p><table><tr><th>Zeit</th><th>An</th><th>Betreff</th><th>Text</th></tr>{mh}</table></section>''','/steuerung')
def haendler(q):
  c=db(); rows=c.execute("select d.*,cu.name cn from dealer_accounts d left join customers cu on cu.id=d.customer_id order by case d.status when 'pending' then 0 when 'invited' then 1 else 2 end, d.id desc").fetchall()
  tr=''
  for drow in rows:
    act=''
    if drow['status']!='approved':
      act+=f'<form class="i" method="post" action="/haendler/{drow["id"]}/aktion"><input type=hidden name=a value=approve><button class="pri">Freigeben</button></form>'
    if drow['status'] not in ('rejected','disabled'):
      act+=f'<form class="i" method="post" action="/haendler/{drow["id"]}/aktion"><input type=hidden name=a value=reject><button>Ablehnen</button></form>'
    tr+=f'<tr><td><a href="/kontakt/{drow["customer_id"]}">{e(drow["company_name"] or drow["cn"])}</a></td><td>{e(drow["email"])}</td><td>{e(drow["uid"])}</td><td>{chip(drow["status"])}</td><td>{e(TIER_LABEL.get(drow["price_tier"], drow["price_tier"]))}</td><td>{chip("Firma geprüft","ok") if drow["company_verified_at"] else chip("offen","neu")}</td><td>{act}</td></tr>'
  return page('Händler',f'<section><h2>Händlerkonten</h2><p class="mu">Selbstregistrierte Konten bleiben <b>pending</b>, bis sie freigegeben sind. Eingeladene Konten werden nach Passwort und TOTP freigeschaltet. Preise sieht nur ein freigegebenes Konto.</p><table><tr><th>Firma</th><th>E-Mail</th><th>UID</th><th>Status</th><th>Stufe</th><th>Firma</th><th></th></tr>{tr or empty("Noch keine Händlerkonten.",7)}</table></section>','/haendler')
def preise(q):
  rows=db().execute('select * from products order by bottle_ml, name').fetchall()
  tr=''.join(
    f'<form id="pf{p["id"]}" method="post" action="/preise/{p["id"]}"></form>'
    f'<tr><td>{e(p["name"])}<br><span class="mu">{e(p["sku"])} · {e(p["bottle_ml"])} ml{" · Beispielpreis" if p["sample_price"] else ""}</span></td>'
    f'<td><input form="pf{p["id"]}" name="price_einstieg" type="number" step="0.05" value="{p["price_einstieg"]:.2f}" style="width:90px"></td>'
    f'<td><input form="pf{p["id"]}" name="price_haendler" type="number" step="0.05" value="{p["price_haendler"]:.2f}" style="width:90px"></td>'
    f'<td><input form="pf{p["id"]}" name="price_grosshaendler" type="number" step="0.05" value="{p["price_grosshaendler"]:.2f}" style="width:90px"></td>'
    f'<td><button form="pf{p["id"]}" class="pri">Speichern</button></td></tr>' for p in rows)
  return page('Preise','<section><h2>Preisstufen</h2><p class="mu">Einstieg, Händler, Grosshändler. Die ausgelieferten Zahlen sind Beispielpreise für den lokalen Test und keine Ladenpreise. Sonderpreise pro Shop stehen am Händlerkonto. Sichtbar im Portal nur nach Login und Freigabe.</p>'
    f'<table><tr><th>Produkt</th><th>Einstieg</th><th>Händler</th><th>Grosshändler</th><th></th></tr>{tr}</table></section>','/preise')
def konten(q):
  typ=(q.get('typ') or ['b2c'])[0].strip().lower()
  if typ not in ('b2c','b2b','alle'): typ='b2c'
  c=db()
  rows=[]
  if typ!='b2b':
    for r in c.execute('select customer_id,email,name,created_at,last_login_at from customer_accounts').fetchall():
      rows.append(('B2C', r['email'], r['name'] or '', r['created_at'], r['last_login_at'], r['customer_id'], 'aktiv'))
  if typ!='b2c':
    for r in c.execute('select customer_id,email,company_name,created_at,last_login_at,status from dealer_accounts').fetchall():
      rows.append(('B2B', r['email'], r['company_name'] or '', r['created_at'], r['last_login_at'], r['customer_id'], r['status']))
  rows.sort(key=lambda x: x[3] or '', reverse=True)
  def _who(cid, who):
    if not cid:
      return e(who)
    return '<a href="/kontakt/%s">%s</a>' % (cid, e(who))
  def _when(value):
    shown = e((value or '')[:16])
    return shown or '<span class="mu">–</span>'
  tr=''.join(
    '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
      chip(kind, 'ok' if kind=='B2C' else 'neu'), _who(cid, who), e(email), chip(status), _when(created), _when(last))
    for kind,email,who,created,last,cid,status in rows)
  tabs=''.join('<a href="/konten?typ=%s" class="%s">%s</a>' % (key, 'on' if key==typ else '', label) for key,label in (('b2c','B2C'),('b2b','B2B'),('alle','Alle')))
  return page('Konten', '<section><h2>Kundenkonten</h2><div class="tabs">%s</div><p class="mu">Standard ist B2C (sofort aktiv, Altersbestätigung nur Checkbox). B2B bleibt in der Liste und ist auf der Website aus, solange B2B_ENABLED nicht gesetzt ist.</p><table><tr><th>Typ</th><th>Name</th><th>E-Mail</th><th>Status</th><th>Registriert</th><th>Letzter Login</th></tr>%s</table></section>' % (tabs, tr or empty('Noch keine Konten.', 6)), '/konten')
GET={'/':uebersicht,'/bestellungen':bestellungen,'/kunden':kunden,'/konten':konten,'/haendler':haendler,'/preise':preise,'/pipeline':pipeline,'/kampagnen':kampagnen,'/aufgaben':aufgaben,'/agenten':agenten,'/steuerung':steuerung}
