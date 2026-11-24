/* BVBirds: Origami-Vögel (Schwalbe, Kranich, Taube, Rabe, Origami-Adler) + abgenommener Bärgtier-Adler fliegen sanft in Bild-Koordinaten (2400×1028) über den Welten.
   Overlay pro Sektion wird wie der Welt-Shader abgebildet (cover, Zoom 1.08·zoom, Zentrum 0.5/0.52; wie .lokgrat / .berglife).
   Läuft nur, solange die Sektion sichtbar und der Tab aktiv ist. Flügelschlag = CSS-Sprite steps(4). Aus bei prefers-reduced-motion.
   Vogel: {t:'schwalbe|dohle|taube|rabe|adler2|adler', cx,cy,rx,ry (Ellipse, Bild-px), T (Umlaufzeit s), ph (Startphase 0–1), dir (±1), h (Höhe Bild-px), m (1 = auch ≤900px)}
   Test: window.__birds() → {hero,bergtiere,quartiere} = Anzahl aktuell fliegender Vögel. */
(function(){
 if(matchMedia('(prefers-reduced-motion:reduce)').matches){window.__birds=function(){return{hero:0,bergtiere:0,quartiere:0};};return;}
 var AR={schwalbe:.838,dohle:.953,adler:.777,taube:.652,rabe:.767,adler2:1.095};
 /* Typen: schwalbe, dohle (= Origami-Kranich), taube, rabe, adler2 (neuer Origami-Adler) aus assets/web/birds/;
    adler = abgenommener Bärgtier-Adler aus assets/web/birds_fix/ (Sprite + Flugbahn NICHT ändern).
    Pro Bereich eine eigene Mischung, leicht versetzt in Zeit (T/ph) und Höhe (cy/h). */
 var CFG={
  /* Hero: erst nach dem Intro (Welt + Flaschen da), nie über dem explodierenden Fuchskopf */
  hero:{warp:1,gate:function(){var h=document.getElementById('hero'),bs=h&&h.querySelector('.beasts');return !!(h&&h.classList.contains('world-in')&&bs&&bs.classList.contains('in'));},b:[
   {t:'schwalbe',cx:1180,cy:340,rx:380,ry:118,T:34,ph:.05,dir:1,h:44,m:1},
   {t:'schwalbe',cx:1200,cy:362,rx:270,ry:84,T:27,ph:.58,dir:-1,h:38},
   {t:'taube',cx:1010,cy:300,rx:470,ry:70,T:48,ph:.32,dir:1,h:52},
   {t:'adler2',cx:1650,cy:250,rx:240,ry:40,T:70,ph:.75,dir:-1,h:60}]},
  /* Adler (Bärgtier): von Dominic abgenommen, Sprite + Flugbahn NICHT ändern */
  bergtiere:{b:[
   {t:'adler',cx:1500,cy:125,rx:360,ry:72,T:62,ph:.1,dir:1,h:86,m:1},
   {t:'dohle',cx:1880,cy:335,rx:190,ry:44,T:38,ph:.42,dir:-1,h:65},
   {t:'rabe',cx:2060,cy:430,rx:140,ry:34,T:29,ph:.8,dir:1,h:52}]},
  quartiere:{b:[
   {t:'taube',cx:1400,cy:310,rx:300,ry:60,T:31,ph:.12,dir:1,h:47,m:1},
   {t:'taube',cx:1310,cy:290,rx:210,ry:46,T:24,ph:.63,dir:-1,h:40},
   {t:'schwalbe',cx:1470,cy:232,rx:430,ry:44,T:44,ph:.36,dir:1,h:39},
   {t:'rabe',cx:980,cy:250,rx:260,ry:38,T:52,ph:.9,dir:-1,h:49}]}
 };
 var FLAP={schwalbe:.28,dohle:.44,adler:.6,taube:.36,rabe:.48,adler2:.6},secs=[],TAU=Math.PI*2;
 function mk(id,c){var sec=document.getElementById(id),pin=sec&&sec.querySelector('.pin');if(!pin)return;
  var cv=pin.querySelector('canvas.world'),o=document.createElement('div');o.className='bv-birds';o.setAttribute('aria-hidden','true');
  var s={id:id,sec:sec,pin:pin,cv:cv,o:o,warp:c.warp,gate:c.gate,vis:false,w:null,list:[],n:0};
  c.b.forEach(function(d){var e=document.createElement('div'),i=document.createElement('i');e.className='bv-bird';e.style.height=d.h+'px';e.style.width=d.h*AR[d.t]+'px';
   i.className='bv-'+d.t;i.style.animationDuration=FLAP[d.t]+'s';i.style.animationDelay=(-Math.random()*FLAP[d.t]).toFixed(2)+'s';e.appendChild(i);o.appendChild(e);
   s.list.push({d:d,e:e,a:d.ph,sx:d.dir,on:true});});
  pin.appendChild(o);secs.push(s);
  if('IntersectionObserver' in window)new IntersectionObserver(function(en){s.vis=en[en.length-1].isIntersecting;go();},{threshold:0}).observe(sec);else{s.vis=true;}
 }
 var raf=0,last=0;
 function act(s){return s.vis&&!document.hidden&&(!s.gate||s.gate());}
 function watch(s){return s.vis&&!document.hidden;}
 function go(){if(!raf&&secs.some(watch)){last=0;raf=requestAnimationFrame(tick);}}
 function tick(now){raf=0;var dt=last?Math.min(.1,(now-last)/1000):0;last=now;var any=false;
  secs.forEach(function(s){if(!watch(s)){s.o.classList.add('off');return;}any=true;var g=act(s);s.o.classList.remove('off');s.o.classList.toggle('gated',!g);if(g)frame(s,dt);});
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
 function init(){Object.keys(CFG).forEach(function(id){mk(id,CFG[id]);});fitAR();go();}
 /* Austausch: neue Sprites einfach als assets/web/birds/<vogel>_sprite.webp ablegen (4 Frames nebeneinander, Blick nach rechts),
    dann scripts/cachebust.py. Seitenverhältnis wird hier aus der Datei gelesen, nichts im Code anpassen.
    Austauschbar: schwalbe, dohle, taube, rabe, adler2. Der Adler liegt getrennt in assets/web/birds_fix/adler_sprite.webp (AR fix .777) und bleibt wie er ist. */
 function fitAR(){Object.keys(AR).filter(function(t){return t!=='adler';}).forEach(function(t){var tmp=document.createElement('i');tmp.className='bv-'+t;tmp.style.display='none';document.body.appendChild(tmp);
  var m=/url\(["']?([^"')]+)/.exec(getComputedStyle(tmp).backgroundImage||'');tmp.remove();if(!m)return;
  var im=new Image();im.onload=function(){if(!im.naturalHeight)return;AR[t]=im.naturalWidth/4/im.naturalHeight;
   secs.forEach(function(s){s.list.forEach(function(b){if(b.d.t===t)b.e.style.width=b.d.h*AR[t]+'px';});});};im.src=m[1];});}
 window.BVBirds={sections:secs};
 window.__birds=function(){var r={hero:0,bergtiere:0,quartiere:0};secs.forEach(function(s){r[s.id]=act(s)?(s.n||0):0;});return r;};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
