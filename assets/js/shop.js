/* Shop-Haken. Kein Backend: Katalog aus products.json, Chorb nur im Browser. */
(function(){
  const KEY='bv-cart';
  const cart=[];
  let catalog=[];
  const bySku=new Map();
  function load(){ try{ const s=JSON.parse(sessionStorage.getItem(KEY)||'[]'); if(Array.isArray(s)) cart.splice(0,cart.length,...s); }catch(e){} }
  function save(){ try{ sessionStorage.setItem(KEY, JSON.stringify(cart)); }catch(e){} }
  function find(sku){ return bySku.get(sku)||null; }
  function emit(){ save(); document.querySelectorAll('[data-cart-count]').forEach(el=>{ el.textContent=String(cart.reduce((n,l)=>n+l.qty,0)); }); document.dispatchEvent(new CustomEvent('bv-cart',{detail:cart.slice()})); paint(); }
  function add(sku, qty){
    qty=qty||1; const item=find(sku); if(!item) return false;
    const line=cart.find(l=>l.sku===sku);
    if(line) line.qty+=qty; else cart.push({sku, qty, name:item.name, kind:item.kind});
    emit(); return true;
  }
  function remove(sku){ const i=cart.findIndex(l=>l.sku===sku); if(i<0) return; cart.splice(i,1); emit(); }
  function paint(){
    document.querySelectorAll('[data-cart-lines]').forEach(ul=>{
      ul.replaceChildren(...cart.map(l=>{
        const li=document.createElement('li');
        const item=find(l.sku);
        li.textContent=`${l.qty} × ${l.name}`+(item&&item.ml?` · ${item.ml} ml`:'');
        const b=document.createElement('button'); b.type='button'; b.textContent='wäg';
        b.addEventListener('click',()=>remove(l.sku));
        li.append(b); return li;
      }));
    });
    document.querySelectorAll('[data-cart-empty]').forEach(el=>{ el.hidden=cart.length>0; });
  }
  function openCart(){ const d=document.getElementById('cart'); if(!d) return; d.hidden=false; const c=d.querySelector('[data-cart-close]'); if(c) c.focus(); }
  function closeCart(){ const d=document.getElementById('cart'); if(d) d.hidden=true; }
  load();
  window.BVShop={
    get cart(){ return cart.map(l=>({...l})); },
    products(){ return catalog.slice(); },
    add, remove,
    clear(){ cart.splice(0,cart.length); emit(); },
    open: openCart
  };
  document.addEventListener('click',e=>{
    const t=e.target.closest('[data-cart-add],[data-cart-open],[data-cart-close]');
    if(!t) return;
    if(t.hasAttribute('data-cart-open')){ e.preventDefault(); openCart(); }
    else if(t.hasAttribute('data-cart-close')) closeCart();
    else if(t.dataset.sku) add(t.dataset.sku,1);
  });
  addEventListener('keydown',e=>{ if(e.key==='Escape') closeCart(); });
  fetch('assets/data/products.json').then(r=>r.json()).then(data=>{
    catalog=[...(data.products||[]),...(data.addons||[]),...(data.hardware||[])];
    catalog.forEach(p=>bySku.set(p.sku,p));
    document.querySelectorAll('.bottle3, .beast.grp .bottle3').forEach(el=>{
      const img=el.querySelector('img.base'); if(!img) return;
      const src=img.getAttribute('src')||'';
      const hit=catalog.find(p=>p.image&&src.endsWith(p.image.split('/').pop()));
      if(hit) el.dataset.sku=hit.sku;
    });
    const box=document.querySelector('[data-shop-extras]');
    if(box){
      [...(data.addons||[]),...(data.hardware||[])].forEach(p=>{
        const b=document.createElement('button'); b.type='button'; b.dataset.cartAdd=''; b.dataset.sku=p.sku;
        b.textContent=p.name+(p.nicotineMgPerMl?` · ${p.nicotineMgPerMl} mg/ml`:'');
        box.append(b);
      });
    }
    emit();
  }).catch(()=>{ emit(); });
})();
