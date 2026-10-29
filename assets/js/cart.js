/* Minimaler Client-Warenkorb. localStorage, kein Checkout, keine Zahlung.
   Knöpfe auf jeder Produktkarte und in den Detailansichten (Lightbox, Tier-Modal). */
(function(){
  var KEY='bv-cart';
  function load(){ try{ var v=JSON.parse(localStorage.getItem(KEY)); return Array.isArray(v)?v:[]; }catch(e){ return []; } }
  function save(items){ try{ localStorage.setItem(KEY, JSON.stringify(items)); }catch(e){} render(); }
  function slug(s){ return (s||'sorte').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,''); }
  function count(items){ return items.reduce(function(n,it){ return n+(it.qty||1); },0); }
  function t(s){ return (window.bvI18n&&bvI18n.t)?bvI18n.t(s):s; }

  function add(id,name){
    if(!id) return;
    var items=load(), f=null;
    for(var i=0;i<items.length;i++) if(items[i].id===id) f=items[i];
    if(f) f.qty=(f.qty||1)+1; else items.push({id:id,name:name||id,qty:1});
    save(items);
    toast();
  }

  var toastEl, panel, listEl, emptyEl, badge, btn;
  function toast(){
    if(!toastEl) return;
    toastEl.hidden=false;
    toastEl.textContent='Im Warechorb – d Bstellig chunnt bald';
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
      var nm=document.createElement('span'); nm.textContent=it.name+'  ×'+(it.qty||1);
      var rm=document.createElement('button'); rm.type='button'; rm.className='cart-rm'; rm.textContent='Wegneh';
      rm.addEventListener('click',function(){
        var next=load().filter(function(x){ return x.id!==it.id; });
        save(next);
      });
      li.appendChild(nm); li.appendChild(rm); listEl.appendChild(li);
    });
    if(emptyEl) emptyEl.hidden=items.length>0;
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
    panel.innerHTML='<div class="carthead"><b>Warechorb</b><button type="button" class="cartx" aria-label="Schliesse">✕</button></div><p class="cartempty">Nüt drin</p><ul></ul><button type="button" class="cartclear">Leere</button><p class="cartnote">Im Warechorb – d Bstellig chunnt bald</p>';
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
    document.querySelectorAll('#flaschen .pcol').forEach(function(col){
      var name=nameOf(col); place(col, slug(name), name);
    });
    document.querySelectorAll('#hero .beast, #quartiere .beast, #bergtiere .beast, .werkstatt .beast, .studies figure').forEach(function(fig){
      var name=nameOf(fig);
      var id=fig.dataset.key||slug(name);
      place(fig, id, name);
    });
    ['#lb .tocart','#tiermodal .tocart'].forEach(function(sel){
      var b=document.querySelector(sel); if(!b||b._cart) return; b._cart=1;
      b.addEventListener('click',function(e){ e.preventDefault(); e.stopPropagation(); add(b.dataset.cart, b.dataset.name); });
    });
  }

  window.bvCart={add:add, slug:slug, setDetail:function(sel,id,name){
    var b=document.querySelector(sel); if(!b) return; b.dataset.cart=id; b.dataset.name=name;
  }};

  function boot(){ ensureUi(); scan(); }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', boot); else boot();
  document.addEventListener('bv-lang', function(){ render(); });
})();
