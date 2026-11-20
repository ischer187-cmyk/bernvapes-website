/* Drei weisse Low-Poly-Füchse. Nie gleichzeitig, 2.8 s Pause, einmal pro Sichtbarkeit.
   Blick (Hero): deckendes WebP mit echtem Alpha, fährt hinter der Bergkante hoch und wieder runter.
   Die anderen beiden bleiben beim Canvas-Colorkey des MP4. */
(function(){
  var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  var GAP=2800, V='72c5bfb47f55155f';
  var BLICK_WAIT=7000, blickReadyAt=0, blickWaitDone=false;
  function blickGate(){
    var h=document.getElementById('hero');
    var beasts=h&&h.querySelector('.beasts');
    if(!h||!h.classList.contains('world-in')||!beasts||!beasts.classList.contains('in')) return false;
    if(blickWaitDone) return true;
    if(!blickReadyAt) blickReadyAt=performance.now()+BLICK_WAIT;
    if(performance.now()<blickReadyAt) return false;
    blickWaitDone=true;
    return true;
  }
  var slots=[
    {id:'blick', sel:'#hero', gate:blickGate},
    {id:'pfote', sel:'#bergtiere'}
  ];
  var playing=null, pauseUntil=0, played={}, raf=0;

  function mount(s){
    var sec=document.querySelector(s.sel); if(!sec) return;
    var pin=sec.querySelector('.pin')||sec;
    var poster='assets/web/fox3/'+(s.id==='blick'?'fox_cut_full':s.id)+'.webp?v='+V;
    var el=document.createElement('div');
    el.className='wfox wfox-'+s.id;
    el.setAttribute('aria-hidden','true');
    if(s.id==='blick'){
      el.innerHTML='<div class="wfox-mask"><img alt="" src="assets/web/fox3/blick_solid.webp?v='+V+'"></div>';
    }else if(reduce||s.id==='pfote'){
      el.innerHTML='<img class="wfox-still" alt="" src="'+poster+'">';
    }else{
      el.innerHTML='<canvas></canvas><video muted playsinline preload="none" src="assets/web/fox3/'+s.id+'.mp4?v='+V+'"></video>';
    }
    pin.appendChild(el);
    s.el=el; s.sec=sec; s.video=el.querySelector('video'); s.canvas=el.querySelector('canvas');
  }

  function ratio(sec){
    var r=sec.getBoundingClientRect(), vh=innerHeight||1;
    var overlap=Math.min(r.bottom,vh)-Math.max(r.top,0);
    return Math.max(0,overlap)/Math.min(vh, Math.max(1,r.height));
  }
  function hide(s){
    if(s.peek){ try{s.peek.cancel();}catch(e){} s.peek=null; }
    if(s.hold){ clearTimeout(s.hold); s.hold=0; }
    if(s.el) s.el.classList.remove('on');
    var img=s.el&&s.el.querySelector('img');
    if(img&&s.id==='blick') img.style.transform='translateY(70%)';
    if(s.video){ s.video.pause(); try{s.video.currentTime=0;}catch(e){} }
  }
  function playBlick(s){
    var img=s.el.querySelector('img');
    img.style.transform='translateY(70%)';
    var up=img.animate(
      [{transform:'translateY(70%)'},{transform:'translateY(0%)'}],
      {duration:1700,easing:'cubic-bezier(.16,.84,.28,1)',fill:'forwards'}
    );
    s.peek=up;
    up.onfinish=function(){
      if(playing!==s) return;
      s.hold=setTimeout(function(){
        if(playing!==s) return;
        var down=img.animate(
          [{transform:'translateY(0%)'},{transform:'translateY(70%)'}],
          {duration:1500,easing:'cubic-bezier(.4,.05,.75,1)',fill:'forwards'}
        );
        s.peek=down;
        down.onfinish=function(){ if(playing===s) finish(s); };
      }, 1300);
    };
  }
  function finish(s){ hide(s); if(playing===s){ playing=null; cancelAnimationFrame(raf); } pauseUntil=performance.now()+GAP; played[s.id]=1; }

  function draw(){
    var s=playing; if(!s||!s.video||!s.canvas) return;
    var v=s.video, c=s.canvas;
    if(v.readyState>=2 && v.videoWidth){
      if(c.width!==v.videoWidth){ c.width=v.videoWidth; c.height=v.videoHeight; }
      var ctx=c.getContext('2d',{willReadFrequently:true});
      ctx.drawImage(v,0,0,c.width,c.height);
      var img=ctx.getImageData(0,0,c.width,c.height), d=img.data, w=c.width, h=c.height;
      function px(x,y){var i=(y*w+x)*4; return [d[i],d[i+1],d[i+2]];}
      var cs=[px(2,2),px(w-3,2),px(2,h-3),px(w-3,h-3)];
      var bg=[0,0,0]; cs.forEach(function(p){bg[0]+=p[0];bg[1]+=p[1];bg[2]+=p[2];});
      var light=bg[0]/4>150;
      for(var i=0;i<d.length;i+=4){
        var r=d[i],g=d[i+1],b=d[i+2], kill;
        if(light) kill=Math.min(r,g,b)>=240;
        else kill=Math.max(Math.abs(r-bg[0]/4),Math.abs(g-bg[1]/4),Math.abs(b-bg[2]/4))<=30;
        if(kill) d[i+3]=0;
      }
      ctx.putImageData(img,0,0);
    }
    if(v.ended){ finish(s); return; }
    raf=requestAnimationFrame(draw);
  }

  function play(s){
    playing=s; s.el.classList.add('on');
    if(s.id==='blick'){ if(!reduce) playBlick(s); else { var img=s.el.querySelector('img'); if(img) img.style.transform='translateY(0%)'; } return; }
    if(reduce||!s.video) return;
    try{ s.video.currentTime=0; }catch(e){}
    var p=s.video.play(); if(p&&p.catch) p.catch(function(){});
    cancelAnimationFrame(raf); raf=requestAnimationFrame(draw);
  }

  function tick(){
    slots.forEach(function(s){
      if(!s.sec) return;
      if(ratio(s.sec)<0.22){ delete played[s.id]; if(playing!==s) hide(s); }
    });
    if(reduce){
      var best=null;
      slots.forEach(function(s){
        if(!s.sec||(s.gate&&!s.gate())) return;
        var r=ratio(s.sec);
        if(r>0.4 && (!best||r>best.r)) best={s:s,r:r};
      });
      slots.forEach(function(s){
        if(!s.el) return;
        s.el.classList.toggle('on', !!(best&&best.s===s));
        if(s.id==='blick'){ var img=s.el.querySelector('img'); if(img) img.style.transform=s.el.classList.contains('on')?'translateY(0%)':'translateY(70%)'; }
      });
      return;
    }
    if(playing){
      if(ratio(playing.sec)<0.18){ hide(playing); playing=null; cancelAnimationFrame(raf); }
      return;
    }
    if(performance.now()<pauseUntil) return;
    for(var i=0;i<slots.length;i++){
      var s=slots[i];
      if(!s.sec||played[s.id]) continue;
      if(s.gate&&!s.gate()) continue;
      if(ratio(s.sec)>0.42){ play(s); break; }
    }
  }

  slots.forEach(mount);

  /* ---------- Quartiere-Fuchs: Alpha-Sprite (laufen_seq.webp), läuft HINTER den Flaschen auf dem runden Boden ----------
     Loch im Kopf: der alte Canvas-Colorkey hat jedes fast weisse Pixel (>=240) gelöscht, auch die hellen Flächen am weissen Fuchs.
     Jetzt: Alpha einmalig offline aus dem Umriss (Flood-Fill) gebaut, kein Colorkey mehr.
     Bewegung: Schrittphase = zurückgelegte Strecke (Füsse rutschen nicht), Bahn = Bogen der runden Bodenfläche,
     Ping-Pong: taucht hinter Flasche 7 auf, läuft nach links, verschwindet hinter Flasche 1, Pause, kommt zurück (gespiegelt). */
  (function(){
    var sec=document.getElementById('quartiere'); if(!sec) return;
    var pin=sec.querySelector('.pin'); if(!pin) return;
    var el=document.createElement('div'); el.className='qfox'; el.setAttribute('aria-hidden','true');
    var cv=document.createElement('canvas'); el.appendChild(cv); pin.insertBefore(el,pin.querySelector('.beasts')||null);
    var FW=262, FH=167, COLS=10, F0=6, FN=25;
    var img=new Image(); img.src='assets/web/fox3/laufen_seq.webp?v='+V;
    var ctx=cv.getContext('2d'); cv.width=FW; cv.height=FH;
    var frame=-1;
    function drawFrame(k){ if(k===frame||!img.complete||!img.naturalWidth) return; frame=k; ctx.clearRect(0,0,FW,FH); var f=F0+k; ctx.drawImage(img,(f%COLS)*FW,Math.floor(f/COLS)*FH,FW,FH,0,0,FW,FH); }
    function bottles(){ var xs=[]; sec.querySelectorAll('.beast[data-season="s"]').forEach(function(b){ xs.push(parseFloat(b.style.left)/100); }); xs.sort(function(a,b){return a-b;}); return xs; }
    var dir=-1, u=0, last=0, wait=1500, dist=0;
    function pos(u,W,H,xa,xb){ var x=xa+(xb-xa)*u, arc=Math.sin(Math.PI*u); return {x:x*W, y:H*(0.752-0.058*arc), s:1-0.16*arc}; }
    function loop(now){
      requestAnimationFrame(loop);
      if(!last) last=now; var dt=Math.min(100,now-last); last=now;
      var r=pin.getBoundingClientRect(), vis=r.bottom>0&&r.top<innerHeight&&sec.getBoundingClientRect().top<innerHeight*0.5&&sec.getBoundingClientRect().bottom>innerHeight*0.3;
      var mob=matchMedia('(max-width:900px)').matches;
      if(mob||!vis||sec.classList.contains('cool')&&false){ el.style.display=(mob?'none':'block'); el.style.opacity=0; window.__qfox=null; return; }
      el.style.display='block';
      var xs=bottles(); if(xs.length<2){ return; }
      var xa=dir<0?xs[xs.length-1]:xs[0], xb=dir<0?xs[0]:xs[xs.length-1];
      var W=pin.clientWidth, H=pin.clientHeight;
      var wpx=Math.max(120,Math.min(260,W*0.15));
      if(reduce){ var q=pos(0.5,W,H,xs[0],xs[xs.length-1]); place(q,wpx,1,W); drawFrame(0); el.style.opacity=1; window.__qfox=null; return; }
      if(wait>0){ wait-=dt; el.style.opacity=0; window.__qfox=null; return; }
      var speed=0.09; /* Pfad-Anteil pro s */
      u+=speed*dt/1000*(0.9/Math.max(.3,Math.abs(xb-xa)));
      if(u>=1){ u=0; dir=-dir; wait=2800; el.style.opacity=0; window.__qfox=null; return; }
      var p=pos(u,W,H,xa,xb), w=wpx*p.s;
      dist+=speed*dt/1000*(0.9/Math.max(.3,Math.abs(xb-xa)))*Math.abs(xb-xa)*W;
      var cyc=w*1.15; drawFrame(Math.floor((dist/cyc)*FN)%FN);
      var edge=Math.min(1,u/0.07,(1-u)/0.07);    /* taucht hinter der Flasche auf/ab */
      el.style.opacity=edge;
      place(p,wpx,dir,W);
      window.__qfox={x:p.x,y:p.y,w:w,on:true};
    }
    function place(p,wpx,d,W){ var w=wpx*p.s, h=w*FH/FW; el.style.width=w+'px'; el.style.height=h+'px';
      el.style.transform='translate('+(p.x-w/2)+'px,'+(p.y-h)+'px) scaleX('+(d>0?-1:1)+')'; }
    requestAnimationFrame(loop);
  })();
  setInterval(tick, 360);
  window.__foxSlots=slots;
})();
