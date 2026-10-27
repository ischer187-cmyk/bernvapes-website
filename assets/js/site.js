/* =========================================================
   BERNVAPES — Papercraft-Welten · Engine
   - World: WebGL-2.5D-Parallaxe für ein Panorama (Maus, Wind, Wolkendrift, Zoom, Eis-Tint)
   - FoxScrub: Bildsequenz mit Alpha, per Scroll gescrubbt (Canvas 2D)
   - Beasts: Tiere in der Welt (Hover-Loop, Tilt, Plaque, Lightbox)
   ========================================================= */
(function(){
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const lerp=(a,b,t)=>a+(b-a)*t;
  const ss01=t=>{t=clamp(t,0,1);return t*t*(3-2*t);};
  const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.querySelectorAll('img[src]').forEach(img=>{ if(img.closest('#hero')) return; if(!img.hasAttribute('loading')) img.loading='lazy'; img.decoding='async'; });
  const navEl=document.getElementById('nav'), navBtn=navEl&&navEl.querySelector('.nav-toggle');
  if(navBtn){ navBtn.addEventListener('click',()=>{ const on=navEl.classList.toggle('open'); navBtn.setAttribute('aria-expanded',on?'true':'false'); });
    navEl.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{ navEl.classList.remove('open'); navBtn.setAttribute('aria-expanded','false'); })); }
  const mobile=()=>innerWidth<(window.BV_MOBILE_BP||900);

  /* ---------- globale Maus (geglättet) ---------- */
  const mouse={x:0,y:0,tx:0,ty:0,active:false};
  addEventListener('pointermove',e=>{ mouse.tx=(e.clientX/innerWidth)*2-1; mouse.ty=(e.clientY/innerHeight)*2-1; mouse.active=true; },{passive:true});
  addEventListener('pointerleave',()=>{mouse.active=false});

  /* ---------- World (WebGL) ---------- */
  const VS=`attribute vec2 p;varying vec2 v;void main(){v=vec2(p.x*.5+.5,.5-p.y*.5);gl_Position=vec4(p,0.,1.);}`;
  const FS=`precision mediump float;varying vec2 v;uniform sampler2D t;uniform vec2 res,img,m,sun;uniform float time,zoom,cool,dark,glow;uniform vec4 tower;
  void main(){
    float ra=res.x/res.y, ri=img.x/img.y;
    vec2 s=(ra>ri)?vec2(1.0,ri/ra):vec2(ra/ri,1.0);
    float depth=smoothstep(0.10,0.95,v.y);                 /* 0 = fern (oben) … 1 = nah (unten) */
    vec2 par=m*(depth-0.38)*0.018;                          /* Parallaxe: vorne mehr, hinten weniger */
    float sway=sin(time*0.9+v.x*7.0)*0.0024*depth*depth;    /* Wind im Vordergrund */
    float drift=sin(time*0.06)*0.013*(1.0-depth)*smoothstep(0.36,0.0,v.y); /* Wolken driften sichtbar hin und her (begrenzt) */
    vec2 off=vec2(par.x+sway+drift,par.y*0.55);
    /* Münster: ein Rechteck, ein Tiefenwert — Fuss und Spitze verschieben sich gleich */
    float depthA=0.30;
    vec2 parA=m*(depthA-0.38)*0.018;
    float swayA=sin(time*0.9+5.95)*0.0024*depthA*depthA;
    vec2 offA=vec2(parA.x+swayA,parA.y*0.55);
    float z=1.08*zoom;
    vec2 base=vec2(0.5,0.52)+(v-0.5)*s/z;
    vec2 uvA=base+offA;
    float inTower=0.0;
    if(tower.z>tower.x){
      float ix=smoothstep(tower.x-0.03,tower.x+0.012,uvA.x)*(1.0-smoothstep(tower.z-0.012,tower.z+0.03,uvA.x));
      float iy=smoothstep(tower.y-0.02,tower.y+0.012,uvA.y)*(1.0-smoothstep(tower.w-0.012,tower.w+0.035,uvA.y));
      inTower=ix*iy;
    }
    vec2 uv=mix(base+off,uvA,inTower);
    vec3 c=texture2D(t,uv).rgb;
    /* Sonne als hinterleuchtete Papierlaterne: pulsierender Kern + warmer Halo, Wolken leicht angestrahlt */
    if(glow>0.0){
      float pulse=0.5+0.5*sin(time*0.75);
      vec2 d2=(uv-sun)*vec2(1.0,img.y/img.x); float d=length(d2);
      float core=smoothstep(0.062,0.030,d);                   /* Scheibe selbst */
      float halo=exp(-d*16.0)*(1.0-core);                     /* weicher Schein ringsum */
      float lum=dot(c,vec3(.299,.587,.114));
      float cl=smoothstep(0.52,0.78,lum)*smoothstep(0.42,0.08,v.y);   /* helle Flächen oben = Wolken */
      /* Strahlen wie ein Lampenschirm von hinten beleuchtet: helle (goldene) Streifen im Himmel glühen, langsam wandernder Lichtkranz */
      float sky=smoothstep(0.50,0.28,uv.y);
      float ang=atan(d2.y,d2.x); float sweep=0.5+0.5*sin(ang*5.0-time*0.35);
      float ray=smoothstep(0.30,0.55,lum)*sky*exp(-d*2.6)*(0.55+0.45*sweep);
      c+= core*vec3(0.50,0.34,0.10)*(0.35+0.65*pulse)*glow;
      c+= halo*vec3(0.55,0.28,0.05)*(0.35+0.45*pulse)*glow;
      c+= ray*vec3(0.34,0.20,0.03)*(0.45+0.55*pulse)*glow;
      c+= cl*vec3(0.14,0.08,0.0)*(0.5+0.5*pulse)*glow;
    }
    /* Eis-Tint (on the rocks) */
    float l=dot(c,vec3(.299,.587,.114));
    vec3 icy=mix(c,vec3(l),0.45)*vec3(0.80,0.92,1.12)+vec3(0.05,0.09,0.15);
    c=mix(c,icy,cool);
    c*= (1.0-dark);
    gl_FragColor=vec4(c,1.0);
  }`;
  class World{
    constructor(canvas,src,opts={}){
      this.c=canvas; this.opts=Object.assign({zoom:1,cool:0,dark:0,strength:1},opts);
      this.zoom=this.opts.zoom; this.cool=this.opts.cool; this.dark=this.opts.dark; this.visible=true; this.ready=false;
      const gl=this.gl=canvas.getContext('webgl',{antialias:false,alpha:false,premultipliedAlpha:false,powerPreference:'high-performance'});
      if(!gl){ this.fallback(src); return; }
      const sh=(t,s)=>{const o=gl.createShader(t);gl.shaderSource(o,s);gl.compileShader(o);return o;};
      const pr=gl.createProgram(); gl.attachShader(pr,sh(gl.VERTEX_SHADER,VS)); gl.attachShader(pr,sh(gl.FRAGMENT_SHADER,FS)); gl.linkProgram(pr);
      if(!gl.getProgramParameter(pr,gl.LINK_STATUS)){ this.fallback(src); return; }
      gl.useProgram(pr);
      const buf=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,buf); gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
      const loc=gl.getAttribLocation(pr,'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc,2,gl.FLOAT,false,0,0);
      this.u={res:gl.getUniformLocation(pr,'res'),img:gl.getUniformLocation(pr,'img'),m:gl.getUniformLocation(pr,'m'),time:gl.getUniformLocation(pr,'time'),zoom:gl.getUniformLocation(pr,'zoom'),cool:gl.getUniformLocation(pr,'cool'),dark:gl.getUniformLocation(pr,'dark'),sun:gl.getUniformLocation(pr,'sun'),glow:gl.getUniformLocation(pr,'glow'),tower:gl.getUniformLocation(pr,'tower')};
      const sunA=(canvas.dataset.sun||'').split(',').map(parseFloat); this.sun=(sunA.length===2&&!sunA.some(isNaN))?sunA:null;
      const twA=(canvas.dataset.tower||'').split(',').map(parseFloat); this.tower=(twA.length===4&&!twA.some(isNaN))?twA:[0,0,0,0];
      const tex=gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D,tex);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
      /* Textur: eingebettete Daten bevorzugen (funktioniert auch bei file://), sonst Datei; bei Fehler CSS-Fallback */
      const key=canvas.dataset.key, data=(window.BV_WORLDS&&key&&window.BV_WORLDS[key])||null;
      const im=new Image();
      im.onload=()=>{ try{ gl.bindTexture(gl.TEXTURE_2D,tex); gl.texImage2D(gl.TEXTURE_2D,0,gl.RGB,gl.RGB,gl.UNSIGNED_BYTE,im); if(gl.getError()!==gl.NO_ERROR) throw new Error('gl'); this.img=[im.naturalWidth,im.naturalHeight]; this.ready=true; this.c.classList.add('ready'); }catch(e){ this.dead=true; this.fallback(src); } };
      im.onerror=()=>{ if(data&&im.src!==src){ im.src=src; } else { this.dead=true; this.fallback(src); } };
      im.src=data||src;
      this.mx=0; this.my=0; this.t0=performance.now();
      new IntersectionObserver(es=>es.forEach(e=>this.visible=e.isIntersecting),{rootMargin:'20%'}).observe(canvas);
      this.resize(); addEventListener('resize',()=>this.resize());
      World.all.push(this);
    }
    /* CSS-Fallback: zwei Ebenen (ganzes Bild + maskierter Vordergrund, der stärker mitwandert) */
    fallback(src){
      const wrap=document.createElement('div'); wrap.className='world world-css';
      const far=document.createElement('img'); far.className='far'; far.onload=()=>{this.img=[far.naturalWidth,far.naturalHeight];}; far.src=src;
      const near=document.createElement('img'); near.src=src; near.className='near';
      wrap.append(far,near); this.c.replaceWith(wrap); this.img=null; this.css=wrap; this.far=far; this.near=near;
      if(!World.all.includes(this)) World.all.push(this);
      this.t0=this.t0||performance.now(); this.visible=true;
      new IntersectionObserver(es=>es.forEach(e=>this.visible=e.isIntersecting),{rootMargin:'20%'}).observe(wrap);
    }
    renderCss(now){
      const k=reduce?1:0.06; const tx=(mouse.active?mouse.tx:Math.sin(now*0.00025)*0.35)*this.opts.strength, ty=(mouse.active?mouse.ty:Math.cos(now*0.0002)*0.25)*this.opts.strength;
      this.mx=lerp(this.mx||0,tx,k); this.my=lerp(this.my||0,ty,k);
      const z=1.08*this.zoom, sway=reduce?0:Math.sin((now-this.t0)*0.0009)*3;
      this.far.style.transform=`translate(${-this.mx*8}px,${-this.my*4}px) scale(${z})`;
      this.near.style.transform=`translate(${-this.mx*24+sway}px,${-this.my*10}px) scale(${z*1.01})`;
      this.css.style.filter=`brightness(${1-this.dark}) ${this.cool>0?`saturate(${1-this.cool*.45}) hue-rotate(${this.cool*-12}deg) brightness(${1+this.cool*.08})`:''}`;
    }
    resize(){ const dpr=Math.min(devicePixelRatio||1,1.5); const r=this.c.getBoundingClientRect(); this.c.width=Math.max(2,Math.round(r.width*dpr)); this.c.height=Math.max(2,Math.round(r.height*dpr)); }
    render(now){
      if(this.css){ if(this.visible) this.renderCss(now); return; }
      if(!this.ready||!this.visible) return; const gl=this.gl;
      const k=reduce?1:0.06;
      const tx=(mouse.active?mouse.tx:Math.sin(now*0.00025)*0.35)*this.opts.strength, ty=(mouse.active?mouse.ty:Math.cos(now*0.0002)*0.25)*this.opts.strength;
      this.mx=lerp(this.mx,tx,k); this.my=lerp(this.my,ty,k);
      gl.viewport(0,0,this.c.width,this.c.height);
      gl.uniform2f(this.u.res,this.c.width,this.c.height); gl.uniform2f(this.u.img,this.img[0],this.img[1]);
      gl.uniform2f(this.u.m,this.mx,this.my); gl.uniform1f(this.u.time,reduce?0:(now-this.t0)/1000);
      gl.uniform1f(this.u.zoom,this.zoom); gl.uniform1f(this.u.cool,this.cool); gl.uniform1f(this.u.dark,this.dark);
      gl.uniform2f(this.u.sun,this.sun?this.sun[0]:0,this.sun?this.sun[1]:0); gl.uniform1f(this.u.glow,this.sun?1:0);
      gl.uniform4f(this.u.tower,this.tower[0],this.tower[1],this.tower[2],this.tower[3]);
      gl.drawArrays(gl.TRIANGLE_STRIP,0,4);
    }
  }
  World.all=[];
  window.BVWorld=World;

  /* ---------- Fox-Scrub (Bildsequenz mit Alpha) ---------- */
  class FoxScrub{
    constructor(canvas,base,count){
      this.c=canvas; this.ctx=canvas.getContext('2d'); this.frames=[]; this.count=count; this.loaded=0; this.idx=-1; this.target=0; this.cur=0;
      for(let i=0;i<count;i++){ const im=new Image(); im.onload=()=>{this.loaded++; if(i===0) this.draw(0,true);}; im.src=`${base}${String(i).padStart(3,'0')}.webp`; this.frames.push(im); }
      this.win=new Image(); this.win.onload=()=>this.draw(this.idx,true); this.win.src=`${base}window.webp`;   /* Fenster in Fuchs-Silhouette (hart, für den Stand) */
      this.winSoft=new Image(); this.winSoft.src=`${base}window_soft.webp`;                                     /* weiche Variante, blendet mit der Bewegung ein */
      this.black=1;
      this.resize(); addEventListener('resize',()=>{this.resize(); this.draw(this.idx,true);});
    }
    resize(){ const dpr=Math.min(devicePixelRatio||1,1.5); this.c.width=Math.round(innerWidth*dpr); this.c.height=Math.round(innerHeight*dpr); }
    draw(i,force){
      i=clamp(Math.round(i),0,this.count-1); if(i===this.idx&&!force&&this.lastScale===this.scale&&this.lastBlack===this.black&&this.lastVg===this.vignette&&this.lastGlow===this.glow&&this.lastFire===this.fire&&this.lastSoft===this.soft&&this.lastFA===this.frameAlpha) return;
      this.lastVg=this.vignette; this.lastGlow=this.glow; this.lastFire=this.fire; this.lastSoft=this.soft; this.lastFA=this.frameAlpha;
      let im=this.frames[i]; let k=i; while((!im||!im.complete||!im.naturalWidth)&&k>0){ k--; im=this.frames[k]; }   /* Fallback: nächster geladener Frame */
      if(!im||!im.complete||!im.naturalWidth) return; i=k;
      this.idx=i; this.lastScale=this.scale; this.lastBlack=this.black; const W=this.c.width,H=this.c.height; const ctx=this.ctx;
      const s=Math.min(W/im.naturalWidth,H/im.naturalHeight)*(this.scale||1); const w=im.naturalWidth*s,h=im.naturalHeight*s, x=(W-w)/2, y=(H-h)/2;   /* contain: ganzer Kopf immer sichtbar */
      ctx.clearRect(0,0,W,H);
      /* 1) Schwarz über alles, 2) Fenster in Fuchs-Silhouette ausstanzen, 3) Fuchs obendrauf → Welt nur dort sichtbar, wo die Maske aufbricht */
      if(this.black>0.001){
        ctx.globalAlpha=this.black; ctx.fillStyle='#000'; ctx.fillRect(0,0,W,H); ctx.globalAlpha=1;
        if(this.win&&this.win.complete&&this.win.naturalWidth){
          ctx.globalCompositeOperation='destination-out'; ctx.drawImage(this.win,x,y,w,h);
          const sw=this.soft||0;   /* weiche Kontur erst mit der Bewegung */
          if(sw>0.001&&this.winSoft&&this.winSoft.complete&&this.winSoft.naturalWidth){ ctx.globalAlpha=sw; ctx.drawImage(this.winSoft,x,y,w,h); ctx.globalAlpha=1; }
          ctx.globalCompositeOperation='source-over'; }
        /* Vignette im Fenster: nur Mitte/Stirn klar, Ränder dunkel — löst sich mit der Blende auf */
        const vg=(this.vignette==null?1:this.vignette)*this.black;
        if(vg>0.001){
          const cx=x+w*0.5, cy=y+h*0.40, r=Math.max(w,h)*0.52;
          const g=ctx.createRadialGradient(cx,cy,r*0.16,cx,cy,r);
          g.addColorStop(0,'rgba(0,0,0,0)'); g.addColorStop(0.55,'rgba(0,0,0,0.55)'); g.addColorStop(1,'rgba(0,0,0,0.96)');
          ctx.globalAlpha=vg; ctx.fillStyle=g; ctx.fillRect(0,0,W,H); ctx.globalAlpha=1;
        }
      }
      /* Augen glühen (kurz vor der Explosion): Glut hinter den Augenhöhlen, danach Bloom obendrauf */
      const g=this.glow||0;
      const eyes=[[817,768],[1103,766]].map(([ex,ey])=>[x+ex/im.naturalWidth*w, y+ey/im.naturalHeight*h]);   /* Bild-Koordinaten (1920×1080) → Canvas */
      const R=w*0.06;
      if(g>0.001){   /* über dem Schwarz, unter dem Frame: scheint durch die Augenlöcher */
        eyes.forEach(([ex,ey])=>{ const gr=ctx.createRadialGradient(ex,ey,0,ex,ey,R*0.9);
          gr.addColorStop(0,`rgba(255,236,170,${g})`); gr.addColorStop(0.45,`rgba(255,170,40,${g*0.85})`); gr.addColorStop(1,'rgba(255,120,20,0)');
          ctx.fillStyle=gr; ctx.fillRect(ex-R,ey-R,R*2,R*2); });
      }
      /* Feuer-Layer zwischen Maske und Welt: bricht aus den Augen, wächst mit dem Loch, verglüht wenn die Maske weg ist */
      const fi=this.fire||0;
      if(fi>0.001){
        ctx.globalCompositeOperation='destination-over';   /* HINTER Schwarz+Fenster → nur durchs Loch sichtbar */
        const cx=(eyes[0][0]+eyes[1][0])/2, cy=(eyes[0][1]+eyes[1][1])/2 - h*0.02;
        const fr=w*(0.10+0.75*(this.fireR||0));
        const gr=ctx.createRadialGradient(cx,cy,0,cx,cy,fr);
        gr.addColorStop(0,`rgba(255,240,190,${fi*0.62})`); gr.addColorStop(0.22,`rgba(255,176,48,${fi*0.55})`); gr.addColorStop(0.55,`rgba(214,60,34,${fi*0.35})`); gr.addColorStop(1,'rgba(120,20,30,0)');
        ctx.fillStyle=gr; ctx.fillRect(cx-fr,cy-fr,fr*2,fr*2);
        /* Flammenzungen: ein paar wandernde Flecken */
        const t=(this.now||0)/1000;
        for(let k=0;k<7;k++){ const an=k*0.9+t*(0.6+k*0.07), rr=fr*(0.35+0.25*Math.sin(t*1.3+k)); const px=cx+Math.cos(an)*rr, py=cy+Math.sin(an)*rr*0.7;
          const g2=ctx.createRadialGradient(px,py,0,px,py,fr*0.28); g2.addColorStop(0,`rgba(255,200,90,${fi*0.32})`); g2.addColorStop(1,'rgba(255,120,30,0)'); ctx.fillStyle=g2; ctx.fillRect(px-fr*0.3,py-fr*0.3,fr*0.6,fr*0.6); }
        ctx.globalCompositeOperation='source-over';
      }
      ctx.globalAlpha=this.frameAlpha==null?1:this.frameAlpha; ctx.drawImage(im,x,y,w,h); ctx.globalAlpha=1;   /* Reste am Ende ausblenden */
      const bl=fi*Math.max(ss01(((this.fireR||0)-0.45)/0.55)*0.5, (this.spill||0)*0.9);   /* Bloom über die Maskenkanten erst, wenn das Loch gross ist — anfangs bleibt alles hinter der Maske */
      if(bl>0.001){
        const cx=(eyes[0][0]+eyes[1][0])/2, cy=(eyes[0][1]+eyes[1][1])/2; const fr=w*(0.18+0.9*(this.fireR||0));
        ctx.globalCompositeOperation='lighter'; const gr=ctx.createRadialGradient(cx,cy,0,cx,cy,fr);
        gr.addColorStop(0,`rgba(255,160,60,${bl*0.30})`); gr.addColorStop(0.5,`rgba(220,70,30,${bl*0.12})`); gr.addColorStop(1,'rgba(200,40,30,0)');
        ctx.fillStyle=gr; ctx.fillRect(cx-fr,cy-fr,fr*2,fr*2); ctx.globalCompositeOperation='source-over';
      }
      if(g>0.001){
        ctx.globalCompositeOperation='lighter';
        eyes.forEach(([ex,ey])=>{ const gr=ctx.createRadialGradient(ex,ey,0,ex,ey,R*2.4);
          gr.addColorStop(0,`rgba(255,190,80,${g*0.55})`); gr.addColorStop(0.35,`rgba(255,140,40,${g*0.22})`); gr.addColorStop(1,'rgba(255,100,20,0)');
          ctx.fillStyle=gr; ctx.fillRect(ex-R*2.4,ey-R*2.4,R*4.8,R*4.8); });
        ctx.globalCompositeOperation='source-over';
      }
    }
    tick(){ this.cur=lerp(this.cur,this.target,reduce?1:0.16); this.draw(this.cur*(this.count-1)); }
  }

  /* ---------- Schnee (leise, wenige Flocken, mit Tiefe) ---------- */
  class Snow{
    constructor(c){ this.c=c; this.ctx=c.getContext('2d'); this.on=false; this.fade=0; this.f=[]; this.resize(); addEventListener('resize',()=>this.resize());
      for(let i=0;i<70;i++) this.f.push(this.spawn(true)); }
    resize(){ const dpr=Math.min(devicePixelRatio||1,1.5); const r=this.c.getBoundingClientRect(); this.c.width=Math.max(2,Math.round(r.width*dpr)); this.c.height=Math.max(2,Math.round(r.height*dpr)); }
    spawn(any){ const z=Math.random(); return {x:Math.random(),y:any?Math.random():-0.02,z,r:0.6+z*2.2,vy:(0.012+z*0.03),ph:Math.random()*6.28,sp:0.4+Math.random()*0.6}; }
    render(now,visible){
      this.fade=lerp(this.fade,this.on?1:0,0.04); if(this.fade<0.01||!visible) { if(this.fade<0.01&&this.lastClear!==1){ this.ctx.clearRect(0,0,this.c.width,this.c.height); this.lastClear=1; } return; }
      this.lastClear=0; const W=this.c.width,H=this.c.height,ctx=this.ctx; const dt=Math.min(0.05,(now-(this.t||now))/1000); this.t=now;
      ctx.clearRect(0,0,W,H); ctx.fillStyle='#fff';
      for(const p of this.f){ p.y+=p.vy*dt*p.sp; p.x+=Math.sin(now*0.0006+p.ph)*0.00025*(0.5+p.z); if(p.y>1.03){ Object.assign(p,this.spawn(false)); }
        ctx.globalAlpha=this.fade*(0.35+0.5*p.z); ctx.beginPath(); ctx.arc(p.x*W,p.y*H,p.r*(W/1600),0,6.28); ctx.fill(); }
      ctx.globalAlpha=1;
    }
  }

  /* ---------- Papier-Gras im Vordergrund (wiegt im Wind und mit der Maus) ---------- */
  class Grass{
    constructor(c){ this.c=c; this.ctx=c.getContext('2d'); this.front=c.dataset.layer==='front'; this.blades=[]; this.drew=false;
      this.resize(); addEventListener('resize',()=>{ this.drew=false; this.resize(); });
      const cols=['#c4a36a','#b08a52','#d7c094','#8d6b3e','#e6d3a8','#6e5430'];
      let seed=this.front?19:7; const rnd=()=>{ seed=(seed*9301+49297)%233280; return seed/233280; };
      const tufts=this.front?16:24;
      for(let t=0;t<tufts;t++){ const x=0.02+rnd()*0.96, n=this.front?3:2;
        for(let i=0;i<n;i++) this.blades.push({x:x+(rnd()-0.5)*0.03, h:this.front?0.075+rnd()*0.05:0.042+rnd()*0.032, w:this.front?0.007+rnd()*0.004:0.004+rnd()*0.0025, lean:(rnd()-0.5)*0.28, c:cols[Math.floor(rnd()*cols.length)], ph:rnd()*6.28}); }
    }
    resize(){ const dpr=Math.min(devicePixelRatio||1,1.25); const r=this.c.getBoundingClientRect(); this.c.width=Math.max(2,Math.round(r.width*dpr)); this.c.height=Math.max(2,Math.round(r.height*dpr)); }
    render(now,cool){ if(reduce){ if(this.drew) return; this.drew=true; }
      const W=this.c.width,H=this.c.height,ctx=this.ctx; ctx.clearRect(0,0,W,H); const t=reduce?0:now/1000;
      const px=(mouse.x+1)/2, py=(mouse.y+1)/2;
      for(const b of this.blades){ const bx=b.x*W, by=H, h=b.h*H, w=Math.max(2,b.w*W);
        let push=0; if(!reduce && py>0.62){ const dx=px-b.x; if(Math.abs(dx)<0.14) push=(dx>0?-1:1)*(0.14-Math.abs(dx))*1.1; }
        const sway=Math.sin(t*0.5+b.ph)*0.1 + Math.sin(t*0.23+b.x*5)*0.04 + push;
        const tipx=bx+(b.lean+sway)*h*0.85, tipy=by-h;
        ctx.fillStyle=cool?'#d5e2ee':b.c; ctx.globalAlpha=this.front?0.92:0.78;
        ctx.beginPath(); ctx.moveTo(bx-w,by); ctx.lineTo(tipx-w*0.35,tipy); ctx.lineTo(tipx+w*0.45,tipy+h*0.08); ctx.lineTo(bx+w*1.15,by); ctx.closePath(); ctx.fill();
        ctx.fillStyle='rgba(255,248,230,.28)'; ctx.beginPath(); ctx.moveTo(bx-w*0.15,by); ctx.lineTo(tipx,tipy+2); ctx.lineTo(tipx+w*0.2,tipy+h*0.2); ctx.lineTo(bx+w*0.25,by); ctx.closePath(); ctx.fill(); }
      ctx.globalAlpha=1; }
  }
  /* Gelegentlich: eine Wolke schiebt sich vor, oder die Berge senken sich ein paar Pixel. */
  function initPaper(sc){
    if(reduce) return;
    const clouds=[...sc.querySelectorAll('.qclouds img')];
    const ridges=sc.querySelector('.ridges');
    if(!clouds.length&&!ridges) return;
    const kick=()=>{
      const r=sc.getBoundingClientRect(); if(r.bottom<0||r.top>innerHeight) return;
      if(clouds.length&&Math.random()<0.62){ const c=clouds[Math.floor(Math.random()*clouds.length)]; c.classList.remove('nudge'); void c.offsetWidth; c.classList.add('nudge'); setTimeout(()=>c.classList.remove('nudge'),3400); }
      else if(ridges){ ridges.classList.remove('dip'); void ridges.offsetWidth; ridges.classList.add('dip'); setTimeout(()=>ridges.classList.remove('dip'),3000); }
    };
    new IntersectionObserver(es=>es.forEach(e=>{ if(e.isIntersecting&&!sc._paper){ sc._paper=true; setTimeout(kick,700); } }),{threshold:0.35}).observe(sc.querySelector('.pin')||sc);
    const loop=()=>{ kick(); setTimeout(loop,20000+Math.random()*20000); };
    setTimeout(loop,18000+Math.random()*12000);
  }
  /* seltenes Wetterleuchten über den Alpen */
  function initFlash(sc){ const el=sc.querySelector('.flash'); if(!el) return; const go=()=>{ if(sc.getBoundingClientRect().bottom>0&&sc.getBoundingClientRect().top<innerHeight){ el.classList.remove('go'); void el.offsetWidth; el.classList.add('go'); } setTimeout(go,14000+Math.random()*26000); }; setTimeout(go,6000+Math.random()*8000); }
  /* Pistenplan: Linien zwischen den Stationen (Flaschen) */
  function drawLifts(sc){ const svg=sc.querySelector('svg.lifts'); if(!svg) return; const pin=sc.querySelector('.pin'); const r=pin.getBoundingClientRect(); const season=sc.classList.contains('cool')?'w':'s';
    const pts=[...sc.querySelectorAll('.beast[data-ix]')].filter(b=>b.dataset.season===season).map(b=>{ const x=parseFloat(b.style.left)/100*r.width, y=(1-parseFloat(b.style.bottom)/100)*r.height; return {x,y}; }).filter(p=>!isNaN(p.x));
    if(pts.length<2){ svg.innerHTML=''; return; }
    pts.sort((a,b)=>b.y-a.y||a.x-b.x);   /* von unten nach oben; Zickzack durch Reihen */
    const rows=[]; pts.forEach(p=>{ const row=rows.find(rw=>Math.abs(rw[0].y-p.y)<r.height*0.1); if(row) row.push(p); else rows.push([p]); });
    const order=[]; rows.forEach((rw,i)=>{ rw.sort((a,b)=>a.x-b.x); if(i%2) rw.reverse(); order.push(...rw); });
    svg.setAttribute('viewBox',`0 0 ${r.width} ${r.height}`);
    svg.innerHTML=`<path d="${order.map((p,i)=>(i?'L':'M')+p.x.toFixed(1)+' '+(p.y-2).toFixed(1)).join(' ')}"/>`+order.map(p=>`<circle cx="${p.x.toFixed(1)}" cy="${(p.y-2).toFixed(1)}" r="3.5"/>`).join('');
  }

  /* ---------- Beasts ---------- */
  function initBeasts(root){
    root.querySelectorAll('.beast').forEach(b=>{
      const art=b.querySelector('.art'), loop=b.querySelector('img.loop');
      let armed=false;
      const name=b.querySelector('.flavor'); if(name&&!b.getAttribute('aria-label')) b.setAttribute('aria-label', name.textContent.trim());
      const play=()=>{ if(loop){ if(!armed){ loop.src=loop.dataset.src; armed=true; } else { const s=loop.src; loop.src=''; loop.src=s; } } b.classList.add('playing'); };
      const stop=()=>{ b.classList.remove('playing'); };
      b.addEventListener('mouseenter',play); b.addEventListener('mouseleave',()=>{stop(); if(art) art.style.transform='';});
      b.addEventListener('mousemove',e=>{ if(reduce||!art) return; const r=b.getBoundingClientRect(); const x=(e.clientX-r.left)/r.width-.5, y=(e.clientY-r.top)/r.height-.5; art.style.transform=`rotateY(${x*12}deg) rotateX(${-y*8}deg)`; });
      b.addEventListener('click',()=>{ if(b.dataset.label) openLB(b.dataset.label,b.dataset.bottle); else if(matchMedia('(hover:none)').matches){ root.querySelectorAll('.beast.touch').forEach(x=>{ if(x!==b) x.classList.remove('touch'); }); b.classList.toggle('touch'); b.classList.contains('playing')?stop():play(); } });
    });
  }
  /* Tiefen-Parallaxe der Tiere (vorne mehr als hinten) */
  function beastParallax(root){
    const items=[...root.querySelectorAll('.beast')].map((b,i)=>{
      const d=parseFloat(b.style.getPropertyValue('--d')||b.dataset.d||1), v=0.85+((i*7)%5)*0.075;   /* pro Gruppe leicht andere Tiefe */
      return {el:b,d:d*v,art:b.querySelector('.art'),bot:b.querySelector('.bottle3'),ing:b.querySelector('.ings'),gh:b.querySelector('.ghost')};
    });
    return ()=>{ if(mobile()||reduce) return; const mx=-mouse.x, my=-mouse.y;   /* gegen die Maus, wie der Welt-Vordergrund */
      items.forEach(({el,d,art,bot,ing,gh})=>{
        el.style.marginLeft=`${mx*26*d}px`; el.style.marginTop=`${my*10*d}px`;
        const bk=el.closest('#hero')?0.22:1;
        if(bot) bot.style.translate=`${mx*9*d*bk}px ${my*4*d*bk}px`;   /* Hero-Flasche bleibt hinter dem Tier */
        if(ing) ing.style.translate=`${mx*16*d}px ${my*6*d}px`;          /* Zutaten: ganz vorne */
        if(gh)  gh.style.translate=`${-mx*8*d}px ${-my*3*d}px`;          /* Logo-Geist: dahinter, bewegt sich weniger */
      }); };
  }

  /* ---------- Lightbox ---------- */
  const lb=document.getElementById('lb');
  function openLB(label,bottle,sku){ if(!lb) return; const poster=lb.querySelector('.poster'); poster.src=label; poster.alt=sku||'Etikette'; const bo=lb.querySelector('.bot'); if(bottle){bo.src=bottle;bo.alt='Flasche';bo.style.display='';} else bo.style.display='none'; const add=lb.querySelector('[data-cart-add]'); if(add){ add.hidden=!sku; add.dataset.sku=sku||''; } lb.classList.add('open'); document.body.style.overflow='hidden'; const c=lb.querySelector('.close'); if(c) c.focus(); }
  function closeLB(){ if(!lb) return; lb.classList.remove('open'); document.body.style.overflow=''; }
  if(lb){ const c=lb.querySelector('.close'); c.setAttribute('role','button'); c.tabIndex=0; c.addEventListener('click',closeLB); c.addEventListener('keydown',e=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); closeLB(); } }); lb.addEventListener('click',e=>{if(e.target===lb)closeLB();}); addEventListener('keydown',e=>{if(e.key==='Escape')closeLB();}); }
  document.querySelectorAll('.bottle[data-label],.bottle3[data-label]').forEach(b=>{
    if(!b.hasAttribute('tabindex')) b.tabIndex=0;
    if(!b.hasAttribute('role')) b.setAttribute('role','button');
    const act=()=>openLB(b.dataset.label,b.dataset.bottle,b.dataset.sku||'');
    b.addEventListener('click',e=>{ e.stopPropagation(); act(); });
    b.addEventListener('keydown',e=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); act(); } });
  });
  const flav=document.getElementById('flaschen');
  if(flav){ flav.querySelectorAll('.bottle3[data-flavor]').forEach(b=>{
    b.addEventListener('mouseenter',()=>{ flav.dataset.tint=b.dataset.flavor; });
    b.addEventListener('mouseleave',()=>{ delete flav.dataset.tint; });
    if(matchMedia('(hover:none)').matches) b.addEventListener('click',()=>{ flav.querySelectorAll('.bottle3.touch').forEach(x=>{ if(x!==b) x.classList.remove('touch'); }); b.classList.toggle('touch'); flav.dataset.tint=b.dataset.flavor; });
  }); }

  /* ---------- Szenen aufsetzen ---------- */
  const worlds={}; const parallaxFns=[];
  document.querySelectorAll('.scene').forEach(sc=>{
    const cv=sc.querySelector('canvas.world'); if(cv) worlds[sc.id]=new World(cv,cv.dataset.src,{strength:parseFloat(cv.dataset.strength||1)});
    initBeasts(sc); parallaxFns.push(beastParallax(sc));
    /* Winter-Welt (zweiter Canvas, blendet über) + Schnee */
    const cw=sc.querySelector('canvas.world.winter'); if(cw){ worlds[sc.id+'_w']=new World(cw,cw.dataset.src,{strength:parseFloat(cw.dataset.strength||1)}); }
    const snow=sc.querySelector('canvas.snow'); if(snow) sc._snow=new Snow(snow);
    sc._grass=[...sc.querySelectorAll('canvas.grass')].map(gr=>new Grass(gr));
    initPaper(sc);
    const preload=()=>{ sc.querySelectorAll('img[src]').forEach(im=>{ if(im.dataset.pre) return; im.dataset.pre='1'; const p=new Image(); p.src=im.src; }); };
    if(sc.id==='hero') preload();
    else new IntersectionObserver(es=>es.forEach(e=>{ if(e.isIntersecting) preload(); }),{rootMargin:'30%'}).observe(sc);
    initFlash(sc);
    /* Sortenliste: Hover/Klick hebt die Flasche am Berg hervor, die anderen treten zurück */
    const lg=sc.querySelector('.legend');
    if(lg){ const all=()=>[...sc.querySelectorAll('.beast[data-key]')];
      const hi=k=>{ all().forEach(b=>{ b.classList.toggle('hi',b.dataset.key===k); b.classList.toggle('dim',!!k&&b.dataset.key!==k&&b.dataset.season===(sc.classList.contains('cool')?'w':'s')); }); };
      lg.querySelectorAll('li').forEach(li=>{ li.tabIndex=0; li.addEventListener('mouseenter',()=>hi(li.dataset.for)); li.addEventListener('mouseleave',()=>{ const on=lg.querySelector('li.on'); hi(on?on.dataset.for:null); });
        li.addEventListener('keydown',e=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); li.click(); } });
        li.addEventListener('click',()=>{ const was=li.classList.contains('on'); lg.querySelectorAll('li.on').forEach(x=>x.classList.remove('on')); if(!was) li.classList.add('on'); hi(was?null:li.dataset.for); }); });
      all().forEach(b=>{ b.addEventListener('mouseenter',()=>{ lg.querySelectorAll('li').forEach(li=>li.classList.toggle('hot',li.dataset.for===b.dataset.key)); }); b.addEventListener('mouseleave',()=>lg.querySelectorAll('li.hot').forEach(li=>li.classList.remove('hot'))); });
    }
    const tg=sc.querySelector('.toggle');
    if(tg){ tg.addEventListener('click',()=>{ const on=tg.classList.toggle('on'); sc.classList.toggle('cool',on); tg.setAttribute('aria-pressed',on);
      sc.querySelectorAll('.beast[data-ice]').forEach(b=>{ const im=b.querySelector('img.still'); if(im) im.src=on?b.dataset.ice:b.dataset.warm; });
      if(sc._snow) sc._snow.on=on; sc.querySelectorAll('.beast.hi,.beast.dim').forEach(b=>b.classList.remove('hi','dim')); sc.querySelectorAll('.legend li.on').forEach(x=>x.classList.remove('on')); }); }
  });
  // Scroll-Fortschritt pro Szene → Tiere einfliegen lassen
  function sceneProgress(sc){ const r=sc.getBoundingClientRect(); const total=sc.offsetHeight-innerHeight; return total>0?clamp(-r.top/total,0,1):(r.top<innerHeight*0.6?1:0); }


  /* Tiere/Flaschen in Bild-Koordinaten platzieren (data-ix/iy = % des Panoramas) */
  function placeOnImage(sc){
    const w=worlds[sc.id]; const pin=sc.querySelector('.pin'); if(!w||!pin||!w.img) return;
    const r=pin.getBoundingClientRect(); const ra=r.width/r.height, ri=w.img[0]/w.img[1];
    const sx=(ra>ri)?1:ra/ri, sy=(ra>ri)?ri/ra:1, z=1.08*(w.zoom||1);
    sc.querySelectorAll('.beast[data-ix]').forEach(b=>{
      const ux=parseFloat(b.dataset.ix)/100, uy=parseFloat(b.dataset.iy)/100;
      const vx=0.5+(ux-0.5)*z/sx, vy=0.5+(uy-0.52)*z/sy;
      b.style.left=(vx*100)+'%'; b.style.bottom=((1-vy)*100)+'%';
    });
    stackDepth(sc);
  }
  function stackDepth(sc){
    sc.querySelectorAll('.beast.grp.bot').forEach(b=>{
      const bottom=parseFloat(b.style.bottom);
      if(Number.isNaN(bottom)) return;
      b.style.setProperty('--z', String(Math.max(6, Math.round(50-bottom))));
    });
  }

  /* ---------- Hero ---------- */
  const hero=document.getElementById('hero');
  let fox=null, heroWorld=null;
  if(hero){
    const fc=hero.querySelector('canvas.fox'); fox=new FoxScrub(fc,fc.dataset.base,parseInt(fc.dataset.count,10));
    heroWorld=worlds['hero']; const brand=hero.querySelector('.brand'), black=hero.querySelector('.black'), beasts=hero.querySelector('.beasts'), hint=hero.querySelector('.hint');
    const nav=document.getElementById('nav');
    let autoP=0, autoStart=null;
    function updateHero(now){
      let p;
      if(mobile()){ if(autoStart===null) autoStart=now; p=clamp((now-autoStart)/4200,0,1); }   // Mobile: Entrance läuft automatisch ab
      else p=sceneProgress(hero);
      if(window.BV_FORCE_P!=null) p=window.BV_FORCE_P;          /* Debug/Test */
      /* Tempo-Regler: der sichtbare Fortschritt folgt dem Scroll zeitbasiert und mit Höchstgeschwindigkeit —
         ein schneller Flick zieht die Explosion nicht in einem Ruck durch (min. ~2.2 s für die Auflöse-Phase), langsames Drehen bleibt direkt. */
      const dt=Math.min(0.05,(now-(hero._t||now))/1000); hero._t=now;
      if(hero._ps==null||window.BV_FORCE_P!=null||reduce) hero._ps=p;
      else{ const d=p-hero._ps, maxv=0.18*dt;            /* max 18 % des Hero-Scrollwegs pro Sekunde */
        const step=Math.sign(d)*Math.min(Math.abs(d)*Math.min(1,dt*7), maxv); hero._ps+=step;
        if(Math.abs(p-hero._ps)<0.0005) hero._ps=p; }
      p=hero._ps;
      const ss=t=>t*t*(3-2*t);                        // smoothstep
      const a=clamp(p/0.40,0,1);                      // Phase A: Maske löst sich auf (Kamera steht) — kürzerer Scrollweg
      const f=clamp((p-0.40)/0.22,0,1);               // Phase B: erst wenn der Kopf ganz verflogen ist: Kamera fährt in die Welt, Schwarz blendet aus
      if(fox){ fox.target=a; fox.scale=1.0;
        /* Maske wird durchlässig, sobald die meisten Stücke fliegen (a≈0.75): erst halb, mit der Kamerafahrt ganz */
        fox.black=1-ss(clamp((a-0.74)/0.26,0,1))*0.55-ss(clamp(f/0.6,0,1))*0.45;
        fox.vignette=1-ss(clamp((a-0.45)/0.5,0,1));
        fox.soft=ss(clamp((a-0.35)/0.4,0,1));            /* Maskenkontur: im Stand hart, wird mit der Bewegung weich */
        fox.frameAlpha=1-ss(clamp((a-0.90)/0.10,0,1));   /* letzte Reste (Ohrspitzen) ausblenden */
        /* Augen: funkeln lange — leuchten vor der Explosion auf und halten, bis der Kopf grösstenteils weg ist */
        const up=ss(clamp((a-0.02)/0.11,0,1)), down=1-ss(clamp((a-0.58)/0.22,0,1));
        fox.glow=up*down*(0.86+0.14*Math.sin(now*0.013)*Math.sin(now*0.0071));
        /* Feuer: zündet, wenn der grösste Teil der Stücke verflogen ist, Spitze bei a≈0.85, dann verglüht es weich mit der Kamerafahrt */
        fox.fireR=ss(clamp((a-0.62)/0.38,0,1));
        fox.fire=ss(clamp((a-0.62)/0.2,0,1))*(1-ss(clamp((f-0.05)/0.7,0,1)))*(0.92+0.08*Math.sin(now*0.021));
        fox.spill=1-fox.black;                            /* Licht nach aussen, sobald die Maske durchlässig wird */
        fox.now=now; }
      if(heroWorld){ heroWorld.zoom=1.0+ ss(f)*0.34; heroWorld.dark=0; }
      black.style.opacity=(fox&&fox.idx>=0)?0:1;   /* bis der erste Frame gezeichnet ist, bleibt der Div-Schwarz */
      brand.style.opacity=clamp(1-a*3.5,0,1); brand.style.transform=`translateY(${a*70}px)`;
      const b=clamp((p-0.60)/0.2,0,1);                // Phase C: Welt steht, Tiere kommen
      hero.classList.toggle('phase-b',b>0.05); beasts.classList.toggle('in',b>0.1);
      if(b>0.5&&!hero._flashed){ hero._flashed=true; beasts.classList.add('labels'); setTimeout(()=>beasts.classList.remove('labels'),3200); }
      if(hint) hint.style.opacity=p>0.9?0:1;
      if(nav){ nav.classList.toggle('show',p>0.12); nav.classList.toggle('solid',p>0.5); }
    }
    hero._update=updateHero;
  }

  /* ---------- Haupt-Loop ---------- */
  function frame(now){
    if(document.hidden){ requestAnimationFrame(frame); return; }
    window.BV_TICKS=(window.BV_TICKS||0)+1;
    mouse.x=lerp(mouse.x,mouse.active?mouse.tx:0,0.06); mouse.y=lerp(mouse.y,mouse.active?mouse.ty:0,0.06);
    if(hero) hero._update(now);
    if(fox) fox.tick();
    World.all.forEach(w=>w.render(now));
    document.querySelectorAll('.scene:not(#hero)').forEach(sc=>{ const p=sceneProgress(sc); const bs=sc.querySelector('.beasts'); if(bs) bs.classList.toggle('in',p>0.08||mobile()); const w=worlds[sc.id]; if(w){ w.zoom=1.0+p*0.08; } const ww=worlds[sc.id+'_w']; if(ww){ ww.zoom=1.0+p*0.08; } const vis=sc.getBoundingClientRect().bottom>0&&sc.getBoundingClientRect().top<innerHeight; if(sc._snow) sc._snow.render(now,vis); if(sc._grass&&vis) sc._grass.forEach(g=>{ if(mobile()&&g.front) return; g.render(now,sc.classList.contains('cool')); }); if(!mobile()){ placeOnImage(sc); if(sc.querySelector('svg.lifts')&&(window.BV_TICKS%20===0)) drawLifts(sc); } else stackDepth(sc); });
    parallaxFns.forEach(f=>f());
    if(hero&&!mobile()){ hero.querySelectorAll('.clouds img').forEach(c=>{ const d=parseFloat(c.style.getPropertyValue('--d')||1); c.style.transform=`translate(${-mouse.x*14*d}px,${-mouse.y*6*d}px)`; }); }   /* Wolken: ferne Ebene, bewegt sich wenig */
    requestAnimationFrame(frame);
  }
  window.BV_FRAME=frame;   /* Debug/Test */
  requestAnimationFrame(frame);
})();
