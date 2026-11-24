/* BVBirds: Low-Poly-Papercraft-Vögel (Schwalbe, Dohle, Adler) fliegen sanft in Bild-Koordinaten (2400×1028) über den Welten.
   Overlay pro Sektion wird wie der Welt-Shader abgebildet (cover, Zoom 1.08·zoom, Zentrum 0.5/0.52; wie .lokgrat / .berglife).
   Läuft nur, solange die Sektion sichtbar und der Tab aktiv ist. Flügelschlag = CSS-Sprite steps(4). Aus bei prefers-reduced-motion.
   Vogel: {t:'schwalbe|dohle|adler', cx,cy,rx,ry (Ellipse, Bild-px), T (Umlaufzeit s), ph (Startphase 0–1), dir (±1), h (Höhe Bild-px), m (1 = auch ≤900px)}
   Test: window.__birds() → {hero,bergtiere,quartiere} = Anzahl aktuell fliegender Vögel. */
(function(){
 if(matchMedia('(prefers-reduced-motion:reduce)').matches){window.__birds=function(){return{hero:0,bergtiere:0,quartiere:0};};return;}
 var AR={schwalbe:.698,dohle:.705,adler:.777};
 var CFG={
  hero:{warp:1,b:[
   {t:'schwalbe',cx:1180,cy:345,rx:400,ry:125,T:34,ph:.05,dir:1,h:36,m:1},
   {t:'schwalbe',cx:1185,cy:350,rx:285,ry:88,T:26,ph:.55,dir:-1,h:32},
   {t:'schwalbe',cx:1175,cy:350,rx:500,ry:140,T:46,ph:.3,dir:1,h:30},
   {t:'dohle',cx:1570,cy:300,rx:170,ry:34,T:40,ph:.2,dir:-1,h:44}]},
  bergtiere:{b:[
   {t:'adler',cx:1500,cy:125,rx:360,ry:72,T:62,ph:.1,dir:1,h:86,m:1},
   {t:'dohle',cx:1900,cy:350,rx:150,ry:38,T:34,ph:.4,dir:-1,h:42},
   {t:'dohle',cx:2110,cy:455,rx:110,ry:30,T:30,ph:.8,dir:1,h:38}]},
  quartiere:{b:[
   {t:'schwalbe',cx:1380,cy:300,rx:280,ry:62,T:30,ph:.1,dir:1,h:34,m:1},
   {t:'schwalbe',cx:1330,cy:285,rx:200,ry:48,T:22,ph:.6,dir:-1,h:30},
   {t:'dohle',cx:1450,cy:225,rx:420,ry:42,T:58,ph:.35,dir:1,h:42}]}
 };
 var FLAP={schwalbe:.28,dohle:.44,adler:.6},secs=[],TAU=Math.PI*2;
 function mk(id,c){var sec=document.getElementById(id),pin=sec&&sec.querySelector('.pin');if(!pin)return;
  var cv=pin.querySelector('canvas.world'),o=document.createElement('div');o.className='bv-birds';o.setAttribute('aria-hidden','true');
  var s={id:id,sec:sec,pin:pin,cv:cv,o:o,warp:c.warp,vis:false,w:null,list:[],n:0};
  c.b.forEach(function(d){var e=document.createElement('div'),i=document.createElement('i');e.className='bv-bird';e.style.height=d.h+'px';e.style.width=d.h*AR[d.t]+'px';
   i.className='bv-'+d.t;i.style.animationDuration=FLAP[d.t]+'s';i.style.animationDelay=(-Math.random()*FLAP[d.t]).toFixed(2)+'s';e.appendChild(i);o.appendChild(e);
   s.list.push({d:d,e:e,a:d.ph,sx:d.dir,on:true});});
  pin.appendChild(o);secs.push(s);
  if('IntersectionObserver' in window)new IntersectionObserver(function(en){s.vis=en[en.length-1].isIntersecting;go();},{threshold:0}).observe(sec);else{s.vis=true;}
 }
 var raf=0,last=0;
 function act(s){return s.vis&&!document.hidden;}
 function go(){if(!raf&&secs.some(act)){last=0;raf=requestAnimationFrame(tick);}}
 function tick(now){raf=0;var dt=last?Math.min(.1,(now-last)/1000):0;last=now;var any=false;
  secs.forEach(function(s){if(!act(s)){s.o.classList.add('off');return;}any=true;s.o.classList.remove('off');frame(s,dt);});
  if(any)raf=requestAnimationFrame(tick);}
 function frame(s,dt){var W=s.pin.clientWidth,H=s.pin.clientHeight,ra=W/H,ri=2400/1028,sx=ra>ri?1:ra/ri,sy=ra>ri?ri/ra:1,zm=1;
  if(s.id==='hero')zm=window.heroZoom||1;else{if(!s.w&&window.BVWorld)s.w=BVWorld.all.find(function(x){return x.c===s.cv;});zm=(s.w&&s.w.zoom)||s.sec._bvZoom||1;}
  var z=1.08*zm,bw=W*z/sx,bh=H*z/sy,narrow=W<=900,n=0;
  s.o.style.transform='translate('+(W*(.5-.5*z/sx))+'px,'+(H*(.5-.52*z/sy))+'px) scale('+(bw/2400)+','+(bh/1028)+')';
  s.list.forEach(function(b){var d=b.d,on=!narrow||!!d.m;if(on!==b.on){b.on=on;b.e.style.display=on?'':'none';}if(!on)return;n++;
   b.a=(b.a+dt/d.T)%1;var th=b.a*TAU*d.dir,x=d.cx+d.rx*Math.cos(th),y=d.cy+d.ry*Math.sin(th),
    vx=-Math.sin(th)*d.rx*d.dir,vy=Math.cos(th)*d.ry*d.dir;
   if(s.warp&&window.BVHeroWarp){var w=BVHeroWarp(x,y);x+=w[0];y+=w[1];}
   var tgt=Math.max(-1,Math.min(1,vx/(d.rx*.35)));b.sx+=(tgt-b.sx)*Math.min(1,dt*6);
   var depth=.92+.08*Math.sin(th*d.dir),bank=Math.max(-1,Math.min(1,vy/(d.ry+1)))*7*(b.sx>=0?1:-1)+Math.sin(b.a*TAU*3+d.ph*9)*2;
   b.e.style.transform='translate('+(x-d.h*AR[d.t]/2).toFixed(1)+'px,'+(y-d.h/2).toFixed(1)+'px) rotate('+bank.toFixed(1)+'deg) scale('+(b.sx*depth).toFixed(3)+','+depth.toFixed(3)+')';});
  s.n=n;}
 document.addEventListener('visibilitychange',go);
 function init(){['hero','bergtiere','quartiere'].forEach(function(id){mk(id,CFG[id]);});go();}
 window.BVBirds={sections:secs};
 window.__birds=function(){var r={hero:0,bergtiere:0,quartiere:0};secs.forEach(function(s){r[s.id]=act(s)?(s.n||0):0;});return r;};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
