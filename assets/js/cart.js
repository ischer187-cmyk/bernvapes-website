/* Client-Warenkorb. localStorage. Zur Kasse öffnet kasse.html (PostFinance Payment Page).
   Knöpfe auf jeder Produktkarte und in den Detailansichten (Lightbox, Tier-Modal). */
(function(){
  var KEY='bv-cart';
  function load(){ try{ var v=JSON.parse(localStorage.getItem(KEY)); return Array.isArray(v)?v:[]; }catch(e){ return []; } }
  function save(items){ try{ localStorage.setItem(KEY, JSON.stringify(items)); }catch(e){} render(); }
  function slug(s){ return (s||'sorte').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,''); }
  function count(items){ return items.reduce(function(n,it){ return n+(it.qty||1); },0); }
  function t(s){ return (window.bvI18n&&bvI18n.t)?bvI18n.t(s):s; }
  function money(n){ return (window.BV_SHIPPING&&BV_SHIPPING.money)?BV_SHIPPING.money(n):('CHF '+Number(n).toFixed(2)); }
  function fold(value){
    var s=(value||'').toLowerCase().replace(/·/g,' ');
    s=s.replace(/ä/g,'ae').replace(/ö/g,'oe').replace(/ü/g,'ue').replace(/ß/g,'ss');
    try{ s=s.normalize('NFD').replace(/[\u0300-\u036f]/g,''); }catch(e){}
    return s.replace(/[^a-z0-9]+/g,' ').trim();
  }
  function fromKey(value){
    var k=(value||'').toLowerCase().trim().replace(/_(100|60)ml$/,'');
    k=k.replace(/_otr/g,' uf ys');
    return fold(k);
  }
  var priceBy={}, catalogReady=false;
  function unitOf(it){
    if(!catalogReady) return null;
    var keys=[fold(it.id), fromKey(it.id), fold(it.name), fromKey(it.name)];
    for(var i=0;i<keys.length;i++) if(priceBy[keys[i]]!=null) return priceBy[keys[i]];
    return null;
  }
  function goodsTotal(items){
    var sub=0;
    for(var i=0;i<items.length;i++){
      var u=unitOf(items[i]);
      if(u==null) return null;
      sub+=u*(items[i].qty||1);
    }
    return Math.round(sub*100)/100;
  }
  function loadCatalog(){
    fetch('/b2b-api/customer/catalog',{headers:{'Accept':'application/json'},credentials:'same-origin'})
      .then(function(r){ return r.json(); })
      .then(function(data){
        (data.products||[]).forEach(function(p){
          var price=Number(p.price_chf);
          [fold(p.sku), fold(p.name), fromKey(p.sku), fromKey(p.name)].forEach(function(k){ if(k) priceBy[k]=price; });
        });
        if(window.BV_SHIPPING && data.shipping_fee_chf!=null){
          BV_SHIPPING.SHIPPING_FEE_CHF=Number(data.shipping_fee_chf);
          BV_SHIPPING.FREE_SHIPPING_THRESHOLD_CHF=Number(data.free_shipping_threshold_chf);
          if(data.vat_rate!=null) BV_SHIPPING.VAT_RATE=Number(data.vat_rate);
        }
        catalogReady=true;
        render();
      }).catch(function(){});
  }
  function setQty(id, qty){
    var next=[];
    load().forEach(function(it){
      if(it.id!==id){ next.push(it); return; }
      if(qty>=1 && qty<=99){ it.qty=qty; next.push(it); }
    });
    save(next);
  }

  function add(id,name,opts){
    if(!id) return;
    var pre=!!(opts&&opts.preorder);
    var items=load(), f=null;
    for(var i=0;i<items.length;i++) if(items[i].id===id) f=items[i];
    if(f){ f.qty=(f.qty||1)+1; if(pre) f.preorder=true; }
    else items.push({id:id,name:name||id,qty:1,preorder:pre});
    save(items);
    toast(pre);
  }

  var toastEl, panel, listEl, emptyEl, badge, btn;
  function toast(pre){
    if(!toastEl) return;
    toastEl.hidden=false;
    toastEl.textContent=pre?'Vorbstellt – d Bstellig chunnt bald':'Im Warechorb – d Bstellig chunnt bald';
    clearTimeout(toastEl._t);
    toastEl._t=setTimeout(function(){ toastEl.hidden=true; }, 2800);
  }
  function render(){
    var items=load(), n=count(items);
    if(badge){ badge.textContent=String(n); badge.hidden=n<1; }
    if(!listEl) return;
    listEl.innerHTML='';
    items.forEach(function(it){
      var li=document.createElement('li');
      var nm=document.createElement('span');
      nm.className='cartline';
      var title=document.createElement('span');
      title.appendChild(document.createTextNode(it.name));
      var unit=unitOf(it);
      if(unit!=null) title.appendChild(document.createTextNode(' · '+money(unit*(it.qty||1))));
      if(it.preorder){
        title.appendChild(document.createTextNode(' · '));
        var mark=document.createElement('i'); mark.className='cartpre'; mark.textContent=t('Vorbstellig');
        title.appendChild(mark);
      }
      nm.appendChild(title);
      var qty=document.createElement('span'); qty.className='cartqty';
      var minus=document.createElement('button'); minus.type='button'; minus.className='cart-q'; minus.textContent='−';
      minus.setAttribute('aria-label',t('Weniger'));
      minus.addEventListener('click',function(){ setQty(it.id,(it.qty||1)-1); });
      var n=document.createElement('span'); n.textContent=String(it.qty||1);
      var plus=document.createElement('button'); plus.type='button'; plus.className='cart-q'; plus.textContent='+';
      plus.setAttribute('aria-label',t('Mehr'));
      plus.addEventListener('click',function(){ setQty(it.id,(it.qty||1)+1); });
      qty.appendChild(minus); qty.appendChild(n); qty.appendChild(plus);
      var rm=document.createElement('button'); rm.type='button'; rm.className='cart-rm'; rm.textContent=t('Wegneh');
      rm.addEventListener('click',function(){
        var next=load().filter(function(x){ return x.id!==it.id; });
        save(next);
      });
      li.appendChild(nm); li.appendChild(qty); li.appendChild(rm); listEl.appendChild(li);
    });
    if(emptyEl) emptyEl.hidden=items.length>0;
    var go=panel&&panel.querySelector('.cartgo'); if(go) go.hidden=items.length<1;
    paintShipping(items);
  }
  function paintShipping(items){
    var box=panel&&panel.querySelector('.cartsum');
    if(!box) return;
    var subEl=box.querySelector('.cart-sub'), shipEl=box.querySelector('.cart-ship'), totEl=box.querySelector('.cart-tot');
    var hint=box.querySelector('.cartship'), bar=box.querySelector('.shipbar i');
    if(!items.length){ box.hidden=true; return; }
    box.hidden=false;
    var goods=goodsTotal(items);
    if(goods==null || !window.BV_SHIPPING){
      if(subEl) subEl.textContent='…';
      if(shipEl) shipEl.textContent='…';
      if(totEl) totEl.textContent='…';
      if(hint) hint.textContent='';
      if(bar) bar.style.width='0%';
      return;
    }
    var fee=BV_SHIPPING.feeFor(goods);
    if(subEl) subEl.textContent=money(fee.subtotal);
    if(shipEl) shipEl.textContent=fee.free?t('Gratis'):money(fee.shipping);
    if(totEl) totEl.textContent=money(fee.total);
    if(hint) hint.textContent=BV_SHIPPING.hint(fee.free, fee.remaining);
    var thr=Number(BV_SHIPPING.FREE_SHIPPING_THRESHOLD_CHF)||1;
    if(bar) bar.style.width=Math.max(0, Math.min(100, fee.subtotal/thr*100)).toFixed(1)+'%';
  }
  function openPanel(on){
    if(!panel) return;
    panel.hidden=!on;
    btn.setAttribute('aria-expanded', on?'true':'false');
    if(on){ var f=panel.querySelector('button, [href]'); if(f) f.focus(); }
  }

  function ensureUi(){
    var sw=document.querySelector('.langsw');
    btn=document.createElement('button');
    btn.type='button'; btn.className='navcart'; btn.setAttribute('aria-haspopup','dialog'); btn.setAttribute('aria-expanded','false');
    btn.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6h15l-1.5 9h-12z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M6 6 5 3H2" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="9" cy="20" r="1.3" fill="currentColor"/><circle cx="18" cy="20" r="1.3" fill="currentColor"/></svg><span class="sr">Warechorb</span><span class="navcart-n" hidden>0</span>';
    badge=btn.querySelector('.navcart-n');
    if(sw&&sw.parentElement){
      if(sw.classList.contains('fixed')){
        var cluster=document.createElement('div'); cluster.className='navcluster fixed';
        sw.parentElement.insertBefore(cluster, sw); sw.classList.remove('fixed');
        cluster.appendChild(btn); cluster.appendChild(sw);
      }else sw.parentElement.insertBefore(btn, sw);
    }else { btn.classList.add('fixed'); document.body.appendChild(btn); }
    panel=document.createElement('div');
    panel.className='cartpanel'; panel.setAttribute('role','dialog'); panel.setAttribute('aria-modal','false'); panel.hidden=true;
    panel.innerHTML='<div class="carthead"><b>Warechorb</b><button type="button" class="cartx" aria-label="Schliesse">✕</button></div><p class="cartempty">Nüt drin</p><ul></ul><div class="cartsum" hidden><p><span>Zwischensumme</span><span class="cart-sub"></span></p><p><span>Versand</span><span class="cart-ship"></span></p><p><b>Total</b><b class="cart-tot"></b></p><p class="cartship" aria-live="polite"></p><div class="shipbar" aria-hidden="true"><i></i></div></div><button type="button" class="cartclear">Leere</button><p class="cartnote">Testzahlung über PostFinance.</p><a class="btn cartgo" href="kasse.html">Zur Kasse</a>';
    document.body.appendChild(panel);
    listEl=panel.querySelector('ul'); emptyEl=panel.querySelector('.cartempty');
    toastEl=document.createElement('div'); toastEl.className='carttoast'; toastEl.setAttribute('role','status'); toastEl.setAttribute('aria-live','polite'); toastEl.hidden=true;
    document.body.appendChild(toastEl);
    btn.addEventListener('click',function(){ openPanel(panel.hidden); });
    panel.querySelector('.cartx').addEventListener('click',function(){ openPanel(false); btn.focus(); });
    panel.querySelector('.cartclear').addEventListener('click',function(){ save([]); });
    addEventListener('keydown',function(e){ if(e.key==='Escape'&&panel&&!panel.hidden){ openPanel(false); btn.focus(); } });
    addEventListener('click',function(e){
      if(panel.hidden) return;
      if(e.target===btn||btn.contains(e.target)||panel.contains(e.target)) return;
      openPanel(false);
    });
    render();
  }

  function button(id,name){
    var b=document.createElement('button');
    b.type='button'; b.className='tocart'; b.dataset.cart=id; b.dataset.name=name;
    b.textContent='I Warechorb';
    b.addEventListener('click',function(e){ e.preventDefault(); e.stopPropagation(); add(id, name); });
    return b;
  }
  function nameOf(host){
    var n=host.querySelector('.flavor, .lbl, figcaption, .who');
    return n?(n.textContent||'').replace(/\s+/g,' ').trim():'';
  }
  function place(host, id, name){
    if(!host||host.querySelector(':scope > .tocart, .plaque > .tocart')) return;
    var b=button(id,name);
    host.appendChild(b);
  }

  function scan(){
    /* Nur #flaschen .preorder ist eine Vorbestellung. Alle anderen Knöpfe bestellen direkt. */
    document.querySelectorAll('#hero .beast, #quartiere .beast, #bergtiere .beast, .werkstatt .beast, .studies figure').forEach(function(fig){
      var name=nameOf(fig);
      var id=fig.dataset.key||slug(name);
      place(fig, id, name);
    });
    ['#lb .tocart','#tiermodal .tocart'].forEach(function(sel){
      var b=document.querySelector(sel); if(!b||b._cart) return; b._cart=1;
      b.addEventListener('click',function(e){ e.preventDefault(); e.stopPropagation(); add(b.dataset.cart, b.dataset.name); });
    });
    /* Genau ein Knopf pro neuer Flasche. Der Listener sitzt nur hier, einmal. */
    document.querySelectorAll('#flaschen .preorder').forEach(function(b){
      if(b._pre) return; b._pre=1;
      b.addEventListener('click',function(e){
        e.preventDefault();
        e.stopPropagation();
        var col=b.closest('.pcol');
        var name=nameOf(col);
        add(slug(name), name, {preorder:true});
      });
    });
  }

  window.bvCart={add:add, slug:slug, setDetail:function(sel,id,name){
    var b=document.querySelector(sel); if(!b) return; b.dataset.cart=id; b.dataset.name=name;
  }};

  function boot(){ ensureUi(); scan(); loadCatalog(); }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', boot); else boot();
  document.addEventListener('bv-lang', function(){ render(); });
})();
