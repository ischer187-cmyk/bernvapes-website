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
  /* Ease-out-Quart: kleine Inputs stark, grosse flachen ab (Scroll→Scrub) */
  const easeOutQuart=t=>{t=clamp(t,0,1);return 1-Math.pow(1-t,4);};
  const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const mobile=()=>innerWidth<(window.BV_MOBILE_BP||900);

  /* ---------- globale Maus (geglättet) ---------- */
  const mouse={x:0,y:0,tx:0,ty:0,active:false};
  addEventListener('pointermove',e=>{ mouse.tx=(e.clientX/innerWidth)*2-1; mouse.ty=(e.clientY/innerHeight)*2-1; mouse.active=true; },{passive:true});
  addEventListener('pointerleave',()=>{mouse.active=false});

  /* ---------- World (WebGL) ---------- */
  const VS=`attribute vec2 p;varying vec2 v;void main(){v=vec2(p.x*.5+.5,.5-p.y*.5);gl_Position=vec4(p,0.,1.);}`;
  const FS=`precision mediump float;varying vec2 v;uniform sampler2D t;uniform vec2 res,img,m,sun;uniform float time,zoom,cool,dark,glow;uniform vec4 rig;
  void main(){
    float ra=res.x/res.y, ri=img.x/img.y;
    vec2 s=(ra>ri)?vec2(1.0,ri/ra):vec2(ra/ri,1.0);
    float z=1.08*zoom;
    /* Starre Zone (data-rigid, Bild-Koordinaten x0,y0,x1,y1, z.B. Münster): dort wird der Versatz an der Unterkante der Zone
       ausgewertet → das Objekt verschiebt sich nur als Ganzes (keine Scherung/Neigung durch Tiefe, Wolkendrift oder Wind) */
    vec2 u0=vec2(0.5,0.52)+(v-0.5)*s/z;
    float rg=(rig.z>rig.x)?smoothstep(rig.x-0.015,rig.x,u0.x)*smoothstep(rig.z+0.015,rig.z,u0.x)*smoothstep(rig.y-0.03,rig.y,u0.y)*smoothstep(rig.w+0.02,rig.w,u0.y):0.0;
    vec2 vv=vec2(v.x,mix(v.y,0.5+(rig.w-0.52)*z/s.y,rg));
    float depth=smoothstep(0.10,0.95,vv.y);                /* 0 = fern (oben) … 1 = nah (unten) */
    vec2 par=m*(depth-0.38)*0.018;                          /* Parallaxe: vorne mehr, hinten weniger */
    float sway=sin(time*0.9+v.x*7.0)*0.0024*depth*depth;    /* Wind im Vordergrund */
    float drift=sin(time*0.06)*0.013*(1.0-depth)*smoothstep(0.36,0.0,vv.y); /* Wolken driften sichtbar hin und her (begrenzt) */
    vec2 off=vec2(par.x+sway+drift,par.y*0.55);
    vec2 uv=vec2(0.5,0.52)+(v-0.5)*s/z+off;
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
      const pr=gl.createProgram(); gl.attachShader(pr,sh(gl.VERTEX_SHADER,VS)); gl.attachShader(pr,sh(gl.FRAGMENT_SHADER,FS)); gl.linkProgram(pr); gl.useProgram(pr);
      const buf=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,buf); gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);
      const loc=gl.getAttribLocation(pr,'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc,2,gl.FLOAT,false,0,0);
      this.u={res:gl.getUniformLocation(pr,'res'),img:gl.getUniformLocation(pr,'img'),m:gl.getUniformLocation(pr,'m'),time:gl.getUniformLocation(pr,'time'),zoom:gl.getUniformLocation(pr,'zoom'),cool:gl.getUniformLocation(pr,'cool'),dark:gl.getUniformLocation(pr,'dark'),sun:gl.getUniformLocation(pr,'sun'),glow:gl.getUniformLocation(pr,'glow'),rig:gl.getUniformLocation(pr,'rig')};
      const sunA=(canvas.dataset.sun||'').split(',').map(parseFloat); this.sun=(sunA.length===2&&!sunA.some(isNaN))?sunA:null;
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
      gl.uniform2f(this.u.sun,this.sun?this.sun[0]:0,this.sun?this.sun[1]:0); gl.uniform1f(this.u.glow,this.sun?1:0); const rr=this.rig||(this.rig=(this.c.dataset.rigid||'0,0,0,0').split(',').map(Number)); gl.uniform4f(this.u.rig,rr[0],rr[1],rr[2],rr[3]);
      gl.drawArrays(gl.TRIANGLE_STRIP,0,4);
    }
  }
  World.all=[];
  window.BVWorld=World;

  /* ---------- Fox-Scrub (Bildsequenz mit Alpha) ---------- */
  class FoxScrub{
    constructor(canvas,base,count){
      this.c=canvas; this.ctx=canvas.getContext('2d'); this.frames=[]; this.count=count; this.loaded=0; this.idx=-1; this.target=0; this.cur=0; this.ready=false;
      this.c.style.opacity='0'; this.c.style.transform='scale(.96)'; this.c.style.transformOrigin='50% 42%';
      this.c.style.transition='opacity .7s ease, transform .8s cubic-bezier(.16,.84,.28,1)';
      const reveal=()=>{ if(this.ready) return; const im=this.frames[0]; if(!im||!im.naturalWidth) return; this.ready=true; this.draw(0,true); this.c.style.opacity='1'; this.c.style.transform='scale(1)'; };
      /* Nur ein Fenster der Sequenz dekodieren. 85 Full-HD-Frames auf einmal
         verdrängen die Produktbilder (Apple Pie, Mango Lassi, Quartier, Berg). */
      this._load=(i)=>{
        if(i<0||i>=count) return null;
        let im=this.frames[i];
        if(im&&im.getAttribute('data-on')==='1') return im;
        if(!im){ im=new Image(); this.frames[i]=im; }
        if(im.getAttribute('data-busy')==='1') return im;
        im.decoding='async'; im.setAttribute('data-busy','1');
        let tries=0; const raw=`${base}${String(i).padStart(3,'0')}.webp`;
        const src=window.BV?BV(raw):raw;
        const go=()=>{ im.src=tries?src+(src.indexOf('?')>=0?'&':'?')+'r='+tries:src; };
        im.onload=()=>{ im.setAttribute('data-on','1'); im.removeAttribute('data-busy'); this.loaded++; if(i===0) reveal(); };
        im.onerror=()=>{ im.removeAttribute('data-busy'); if(++tries<4) setTimeout(go, 280*tries); };
        go();
        return im;
      };
      this._window=(i)=>{
        for(let k=i-2;k<=i+5;k++) this._load(k);
        this._load(0);
        for(let k=1;k<count;k++){
          if(Math.abs(k-i)>12 && this.frames[k]){
            const old=this.frames[k]; old.onload=old.onerror=null; old.src=''; this.frames[k]=null;
          }
        }
      };
      this._load(0);
      const bv=function(u){ return window.BV?BV(u):u; };
      this.win=new Image(); this.win.onload=()=>this.draw(this.idx,true); this.win.src=bv(base+'window.webp');   /* Fenster in Fuchs-Silhouette (hart, für den Stand) */
      this.winSoft=new Image(); this.winSoft.src=bv(base+'window_soft.webp');                                     /* weiche Variante, blendet mit der Bewegung ein */
      this.black=1;
      this.resize(); addEventListener('resize',()=>{this.resize(); this.draw(this.idx,true);});
    }
    resize(){ const dpr=Math.min(devicePixelRatio||1,1.5); this.c.width=Math.round(innerWidth*dpr); this.c.height=Math.round(innerHeight*dpr); }
    draw(pos,force){
      if(!this.ready&&!force) return;
      const max=this.count-1;
      const raw=clamp(pos,0,max);
      const i0=Math.floor(raw+1e-4);
      const frac=Math.min(1, Math.max(0, raw-i0));
      let i=i0;
      if(!force && Math.abs((this._raw==null? -1:this._raw)-raw)<0.012 && i===this.idx && this.lastScale===this.scale&&this.lastBlack===this.black&&this.lastVg===this.vignette&&this.lastGlow===this.glow&&this.lastFire===this.fire&&this.lastSoft===this.soft&&this.lastFA===this.frameAlpha) return;
      this._raw=raw; this._frac=frac; this._i1=Math.min(max, i0+1);
      this.lastVg=this.vignette; this.lastGlow=this.glow; this.lastFire=this.fire; this.lastSoft=this.soft; this.lastFA=this.frameAlpha;
      if(this._window) this._window(i);
      let im=this.frames[i];
      if(!im||!im.complete||!im.naturalWidth){ const z=this.frames[0]; if(z&&z.naturalWidth) im=z; else return; }
      this.idx=i; this.lastScale=this.scale; this.lastBlack=this.black; const W=this.c.width,H=this.c.height; const ctx=this.ctx;
      const s=Math.min(W/im.naturalWidth,H/im.naturalHeight)*(this.scale||1); const w=im.naturalWidth*s,h=im.naturalHeight*s, x=(W-w)/2, y=(H-h)/2-H*0.15*Math.max(0,Math.min(1,this.black==null?1:this.black));   /* Intro: Kopf ~15 % höher (Platz für Wortmarke darunter), gleitet beim Aufbrechen zurück in die Mitte; contain: ganzer Kopf immer sichtbar */
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
      ctx.globalAlpha=this.frameAlpha==null?1:this.frameAlpha; ctx.drawImage(im,x,y,w,h);
      /* Augenhöhlen der Standframes sind transparente Löcher. Hinter dem Mesh
         mit dunklem Metall schliessen, solange der Kopf noch ganz ist. */
      if(i<30 && this.win){
        ctx.save(); ctx.globalCompositeOperation='destination-over';
        eyes.forEach(([ex,ey])=>{ const rad=w*0.055; const g=ctx.createRadialGradient(ex,ey,rad*0.15,ex,ey,rad);
          g.addColorStop(0,'#3a322c'); g.addColorStop(0.7,'#6a5848'); g.addColorStop(1,'rgba(90,70,55,0)');
          ctx.fillStyle=g; ctx.beginPath(); ctx.arc(ex,ey,rad,0,6.2832); ctx.fill(); });
        ctx.restore();
      }
      const nxt=this.frames[this._i1];
      if(this._frac>0.02 && nxt && nxt.complete && nxt.naturalWidth && this._i1!==i){
        ctx.globalAlpha=(this.frameAlpha==null?1:this.frameAlpha)*this._frac;
        ctx.drawImage(nxt,x,y,w,h);
      }
      ctx.globalAlpha=1;
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
    tick(now){
      if(!this.ready) return;
      const dt=Math.min(0.05, ((now||performance.now())-(this._tickT||now||performance.now()))/1000);
      this._tickT=now||performance.now();
      const k=reduce?1:(1-Math.exp(-dt/0.16));
      this.cur+=(this.target-this.cur)*k;
      if(Math.abs(this.target-this.cur)<0.0006) this.cur=this.target;
      /* Frames 0–28 are the same still head. A short hold, then the unique frames,
         so a slow scroll moves instead of sitting still and then jumping. */
      const u=clamp(this.cur,0,1), hold=28, span=this.count-1, share=0.07;
      const frame=u<=share ? (u/share)*0.35 : hold+((u-share)/(1-share))*(span-hold);
      this.draw(frame);
    }
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
    constructor(c){ this.c=c; this.ctx=c.getContext('2d'); this.blades=[]; this.resize(); addEventListener('resize',()=>this.resize());
      const cols=['#9a7a4a','#b08a52','#7d6238','#c39a5c','#6b5a3a','#a8864f'];
      let seed=7; const rnd=()=>{ seed=(seed*9301+49297)%233280; return seed/233280; };
      for(let t=0;t<16;t++){ const x=0.01+rnd()*0.98, n=3+Math.floor(rnd()*4), base=0.0+rnd()*0.04;   /* Büschel */
        for(let i=0;i<n;i++) this.blades.push({x:x+(rnd()-0.5)*0.035, h:0.03+rnd()*0.05, w:0.003+rnd()*0.004, lean:(rnd()-0.5)*0.5, c:cols[Math.floor(rnd()*cols.length)], ph:rnd()*6.28, y:base*rnd()}); }
      this.blades.sort((a,b)=>a.h-b.h); }
    resize(){ const dpr=Math.min(devicePixelRatio||1,1.5); const r=this.c.getBoundingClientRect(); this.c.width=Math.max(2,Math.round(r.width*dpr)); this.c.height=Math.max(2,Math.round(r.height*dpr)); }
    render(now,cool){ const W=this.c.width,H=this.c.height,ctx=this.ctx; ctx.clearRect(0,0,W,H); const t=now/1000, mx=mouse.x;
      for(const b of this.blades){ const bx=b.x*W, by=H*(1-b.y), h=b.h*H, w=b.w*W;
        const sway=Math.sin(t*1.1+b.ph+b.x*9)*0.18 + Math.sin(t*2.3+b.ph)*0.05 + mx*0.35;   /* Wind + Maus */
        const tipx=bx+(b.lean+sway)*h, tipy=by-h; const mid=by-h*0.5;
        ctx.fillStyle=cool?'#c9d6e6':b.c; ctx.globalAlpha=0.95;
        ctx.beginPath(); ctx.moveTo(bx-w,by); ctx.quadraticCurveTo(bx-w*0.6+(tipx-bx)*0.3,mid,tipx,tipy); ctx.quadraticCurveTo(bx+w*0.6+(tipx-bx)*0.3,mid,bx+w,by); ctx.closePath(); ctx.fill();
        ctx.fillStyle='rgba(0,0,0,.18)'; ctx.beginPath(); ctx.moveTo(bx,by); ctx.quadraticCurveTo(bx+(tipx-bx)*0.3,mid,tipx,tipy); ctx.quadraticCurveTo(bx+w*0.6+(tipx-bx)*0.3,mid,bx+w,by); ctx.closePath(); ctx.fill(); }
      ctx.globalAlpha=1; }
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
  let loopsReady=false;
  addEventListener('scroll',()=>{ loopsReady=true; },{passive:true,once:true});
  function initBeasts(root){
    const touch=mobile();
    root.querySelectorAll('.beast').forEach(b=>{
      const art=b.querySelector('.art'), loop=b.querySelector('img.loop');
      let armed=false;
      /* Animierte Loops (~3 MB) bleiben ohne src, bis Hover (Desktop) oder Sichtbarkeit/Tap (Mobil). */
      const play=(restart)=>{ if(loop){ if(!armed){ if(loop.dataset.src) loop.src=loop.dataset.src; armed=true; } else if(restart && loop.src){ const s=loop.src; loop.src=''; loop.src=s; } } b.classList.add('playing'); };
      const stop=()=>{ b.classList.remove('playing'); };
      b.addEventListener('mouseenter',()=>play(true)); b.addEventListener('mouseleave',()=>{stop(); if(art) art.style.transform='';});
      b.addEventListener('mousemove',e=>{ if(reduce||!art) return; const r=b.getBoundingClientRect(); const x=(e.clientX-r.left)/r.width-.5, y=(e.clientY-r.top)/r.height-.5; art.style.transform=`rotateY(${x*12}deg) rotateX(${-y*8}deg)`; });
      b.addEventListener('click',()=>{
        if(b.dataset.label){ if(touch) play(true); openLB(b.dataset.label,b.dataset.bottle); }
        else if(touch){ b.classList.contains('playing')?stop():play(true); }
      });
      if(touch && loop && 'IntersectionObserver' in window){
        const show=()=>{
          if(!loopsReady) return;
          const r=b.getBoundingClientRect();
          const vis=Math.max(0, Math.min(r.bottom, innerHeight)-Math.max(r.top,0));
          if(r.height && vis/r.height>=0.35) play(false);
        };
        const io=new IntersectionObserver(es=>{ es.forEach(en=>{ if(en.isIntersecting) show(); else stop(); }); },{threshold:0.35});
        io.observe(b);
        addEventListener('scroll', show, {passive:true});
      }
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
        if(bot) bot.style.translate=`${mx*9*d}px ${my*4*d}px`;          /* Flasche: eigene Ebene, etwas näher */
        if(ing) ing.style.translate=`${mx*16*d}px ${my*6*d}px`;          /* Zutaten: ganz vorne */
        if(gh)  gh.style.translate=`${-mx*8*d}px ${-my*3*d}px`;          /* Logo-Geist: dahinter, bewegt sich weniger */
      }); };
  }

  /* ---------- Lightbox ---------- */
  const lb=document.getElementById('lb');
  function openLB(label,bottle,meta){ if(!lb) return; lb.querySelector('.poster').src=label; const bo=lb.querySelector('.bot'); if(bottle){bo.src=bottle;bo.style.display='';} else bo.style.display='none'; const cb=lb.querySelector('.tocart'); if(cb){ if(meta&&meta.id){cb.hidden=false;cb.dataset.cart=meta.id;cb.dataset.name=meta.name||'';}else cb.hidden=true; } lb.classList.add('open'); document.body.style.overflow='hidden'; }
  function closeLB(){ if(!lb) return; lb.classList.remove('open'); document.body.style.overflow=''; }
  if(lb){ lb.querySelector('.close').addEventListener('click',closeLB); lb.addEventListener('click',e=>{if(e.target===lb)closeLB();}); addEventListener('keydown',e=>{if(e.key==='Escape')closeLB();}); }
  document.querySelectorAll('.bottle[data-label],.bottle3[data-label]').forEach(b=>b.addEventListener('click',e=>{ if(e.target.closest('.tocart,.preorder')) return; const host=b.closest('.pcol,.beast'); const fromLine=!!b.closest('#flaschen'); const btn=!fromLine&&host&&host.querySelector('.tocart'); openLB(b.dataset.label,b.dataset.bottle,btn?{id:btn.dataset.cart,name:btn.dataset.name}:null); }));

  /* ---------- Szenen aufsetzen ---------- */
  const worlds={}; const parallaxFns=[];
  document.querySelectorAll('.scene').forEach(sc=>{
    const cv=sc.querySelector('canvas.world'); if(cv) worlds[sc.id]=new World(cv,cv.dataset.src,{strength:parseFloat(cv.dataset.strength||1)});
    initBeasts(sc); parallaxFns.push(beastParallax(sc));
    /* Winter-Welt (zweiter Canvas, blendet über) + Schnee */
    const cw=sc.querySelector('canvas.world.winter'); if(cw){ worlds[sc.id+'_w']=new World(cw,cw.dataset.src,{strength:parseFloat(cw.dataset.strength||1)}); }
    const snow=sc.querySelector('canvas.snow'); if(snow) sc._snow=new Snow(snow);
    const gr=sc.querySelector('canvas.grass'); if(gr) sc._grass=new Grass(gr);
    initFlash(sc);
    /* Sortenliste: Hover/Klick hebt die Flasche am Berg hervor, die anderen treten zurück */
    const lg=sc.querySelector('.legend');
    if(lg){ const all=()=>[...sc.querySelectorAll('.beast[data-key]')];
      const hi=k=>{ all().forEach(b=>{ b.classList.toggle('hi',b.dataset.key===k); b.classList.toggle('dim',!!k&&b.dataset.key!==k&&b.dataset.season===(sc.classList.contains('cool')?'w':'s')); }); };
      lg.querySelectorAll('li').forEach(li=>{ li.addEventListener('mouseenter',()=>hi(li.dataset.for)); li.addEventListener('mouseleave',()=>{ const on=lg.querySelector('li.on'); hi(on?on.dataset.for:null); });
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
      if(mobile()){ p=hero._touchP||0; }   // Mobile: der Hero ist nicht lang. Ziehen scrubbt den Kopf.
      else p=sceneProgress(hero);
      if(window.BV_FORCE_P!=null) p=window.BV_FORCE_P;          /* Debug/Test */
      /* Scroll→Scrub mit Ease-out-Quart + Tempo-Deckel:
         Delta d = Lücke zwischen echtem Scroll und sichtbarem Fortschritt.
         x=min(|d|/MAX,1), Schritt=sign(d)*MAX*(1-(1-x)^4)*k — langsame Bewegungen
         wirken fast voll, schnelle Flicks flachen ab; maxv begrenzt weiter die Geschwindigkeit.
         FoxScrub.tick() glättet zusätzlich per Lerp. */
      const dt=Math.min(0.05,(now-(hero._t||now))/1000); hero._t=now;
      if(hero._ps==null||window.BV_FORCE_P!=null||reduce) hero._ps=p;
      else{
        /* Immer ein Stück Richtung Ziel, auch bei sehr kleinem Scroll. Kein Tempo-Deckel, der stehen bleibt. */
        const k=1-Math.exp(-dt/0.14);
        hero._ps+=(p-hero._ps)*k;
        if(Math.abs(p-hero._ps)<0.0004) hero._ps=p;
      }
      p=hero._ps;
      const ss=t=>t*t*(3-2*t);                        // smoothstep
      const a=clamp(p/0.40,0,1);                      // Phase A: Maske löst sich auf (Kamera steht) — kürzerer Scrollweg
      const f=clamp((p-0.40)/0.22,0,1);               // Phase B: erst wenn der Kopf ganz verflogen ist: Kamera fährt in die Welt, Schwarz blendet aus
      /* Weiches Einblenden der Papierwelt: Crossfade über den Anfang von Phase B (kein harter Cut / Schwarzblitz) */
      const worldIn=ss(clamp(f/0.34,0,1));
      if(fox){ fox.target=a; fox.scale=1.0;
        /* Maske wird durchlässig, sobald die meisten Stücke fliegen (a≈0.75): erst halb, mit der Kamerafahrt ganz */
        fox.black=1-ss(clamp((a-0.74)/0.26,0,1))*0.55-worldIn*0.45;
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
      if(heroWorld){
        heroWorld.zoom=1.0+ ss(f)*0.34; window.heroZoom=heroWorld.zoom;
        /* leichte Abdunkelung nur am Beginn der Kamerafahrt, weich hochgefahren mit worldIn */
        heroWorld.dark=f>0?(1-worldIn)*0.28:0;
      }
      /* Div-Schwarz weich ausfaden sobald der erste Fuchs-Frame da ist (statt hartem Cut) */
      const wantBlk=(fox&&fox.idx>=0)?0:1;
      hero._blk=(hero._blk==null)?wantBlk:lerp(hero._blk,wantBlk,reduce?1:0.08);
      black.style.opacity=hero._blk;
      brand.style.opacity=clamp(1-a*3.5,0,1); brand.style.transform=`translateY(${a*70}px)`;
      const b=clamp((p-0.60)/0.2,0,1);                // Phase C: Welt steht, Tiere kommen
      hero.classList.toggle('phase-b',b>0.05); beasts.classList.toggle('in',b>0.1);
      hero.classList.toggle('world-in', worldIn>0.82);
      if(b>0.5&&!hero._flashed){ hero._flashed=true; beasts.classList.add('labels'); setTimeout(()=>beasts.classList.remove('labels'),3200); }
      if(hint) hint.style.opacity=p>0.9?0:1;
      if(nav){ nav.classList.toggle('show',p>0.12); nav.classList.toggle('solid',p>0.5); }
    }
    hero._update=updateHero;
    const pin=hero.querySelector('.pin');
    if(pin){
      pin.addEventListener('pointerdown',e=>{
        if(!mobile()||e.button>0||e.target.closest('a,button,.beast,.toggle')) return;
        hero._drag={y:e.clientY,p:hero._touchP||0,id:e.pointerId};
        try{ pin.setPointerCapture(e.pointerId); }catch(err){}
      });
      pin.addEventListener('pointermove',e=>{
        if(!hero._drag||hero._drag.id!==e.pointerId) return;
        hero._touchP=clamp(hero._drag.p+(hero._drag.y-e.clientY)/(innerHeight*1.15),0,1);
      });
      const end=e=>{ if(hero._drag&&(!e||hero._drag.id===e.pointerId)) hero._drag=null; };
      pin.addEventListener('pointerup',end);
      pin.addEventListener('pointercancel',end);
    }
  }

  /* ---------- Haupt-Loop ---------- */
  function frame(now){
    window.BV_TICKS=(window.BV_TICKS||0)+1;
    mouse.x=lerp(mouse.x,mouse.active?mouse.tx:0,0.06); mouse.y=lerp(mouse.y,mouse.active?mouse.ty:0,0.06);
    if(hero) hero._update(now);
    if(fox) fox.tick(now);
    World.all.forEach(w=>w.render(now));
    document.querySelectorAll('.scene:not(#hero)').forEach(sc=>{ const p=sceneProgress(sc); const bs=sc.querySelector('.beasts'); if(bs) bs.classList.toggle('in',(sc.id==='quartiere'?((sc.getBoundingClientRect().top<innerHeight*0.4&&sc.getBoundingClientRect().bottom>innerHeight*0.3)?(sc._inAt=sc._inAt||now,now-sc._inAt>450):(sc._inAt=0,false)):p>0.08)||mobile());   /* Quartier: Flaschen erscheinen ~0.45 s nach Einstieg (Scroll oder #quartiere-Anker) von selbst (auch via #quartiere-Anker), nicht erst nach 8 % Pin-Scroll */ const w=worlds[sc.id]; if(w){ w.zoom=1.0+p*0.08; sc._bvZoom=w.zoom; } const ww=worlds[sc.id+'_w']; if(ww){ ww.zoom=1.0+p*0.08; } const vis=sc.getBoundingClientRect().bottom>0&&sc.getBoundingClientRect().top<innerHeight; if(sc._snow) sc._snow.render(now,vis); if(sc._grass&&vis&&!mobile()) sc._grass.render(now,sc.classList.contains('cool')); if(!mobile()){ placeOnImage(sc); if(sc.querySelector('svg.lifts')&&(window.BV_TICKS%20===0)) drawLifts(sc); } });
    parallaxFns.forEach(f=>f());
    if(hero&&!mobile()){ hero.querySelectorAll('.clouds img').forEach(c=>{ const d=parseFloat(c.style.getPropertyValue('--d')||1); c.style.transform=`translate(${-mouse.x*14*d}px,${-mouse.y*6*d}px)`; }); }   /* Wolken: ferne Ebene, bewegt sich wenig */
    requestAnimationFrame(frame);
  }
  /* Produktbilder nie verwerfen. Fehlschlag erneut versuchen, Quelle merken. */
  function guardImg(img){
    if(!img||img.dataset.guard) return; img.dataset.guard='1';
    const src=img.getAttribute('src'); if(!src) return;
    img.dataset.src0=src; let n=0;
    img.addEventListener('error',()=>{ if(++n>4) return; const base=src.split('?')[0]; setTimeout(()=>{ img.src=base+'?retry='+n; }, 350*n); });
  }
  document.querySelectorAll('img[src]').forEach(guardImg);
  new MutationObserver(ms=>{ ms.forEach(m=>m.addedNodes&&m.addedNodes.forEach&&m.addedNodes.forEach(node=>{ if(node.tagName==='IMG') guardImg(node); else if(node.querySelectorAll) node.querySelectorAll('img[src]').forEach(guardImg); })); }).observe(document.body,{childList:true,subtree:true});

  window.BV_FRAME=frame;   /* Debug/Test */
  requestAnimationFrame(frame);
})();

/* ===== BV Bärgtier-Tafel: Infotafel in die Richtung mit dem meisten Platz klappen (oben/rechts/links/unten) ===== */
(function(){
  const sec=document.getElementById('bergtiere'); if(!sec) return;
  const nav=document.querySelector('.nav');
  const vis=f=>{const s=getComputedStyle(f);return s.opacity!=='0'&&s.display!=='none'&&s.visibility!=='hidden'};
  const ov=(a,b)=>Math.max(0,Math.min(a.r,b.r)-Math.max(a.l,b.l))*Math.max(0,Math.min(a.b,b.b)-Math.max(a.t,b.t));
  function place(f){
    const pl=f.querySelector('.plaque'); if(!pl) return;
    const pin=f.closest('.pin')||sec, P=pin.getBoundingClientRect();
    const top=Math.max(P.top,nav?nav.getBoundingClientRect().bottom:0)+6, R={l:P.left+6,r:P.right-6,t:top,b:P.bottom-6};
    const F=f.getBoundingClientRect(), w=pl.offsetWidth, h=pl.offsetHeight, cx=F.left+F.width/2;
    const g=F.height*.32, sx=F.width*.26;   /* Platz für die beim Hover um 1.32 wachsende Flasche */
    const C={up:{l:cx-w/2,r:cx+w/2,b:F.top-g,t:F.top-g-h},down:{l:cx-w/2,r:cx+w/2,t:F.bottom+10,b:F.bottom+10+h},
      right:{l:F.right+sx,r:F.right+sx+w,t:F.top+F.height*.18,b:F.top+F.height*.18+h},left:{r:F.left-sx,l:F.left-sx-w,t:F.top+F.height*.18,b:F.top+F.height*.18+h}};
    const nb=[...sec.querySelectorAll('.beast,.title,.legend')].filter(n=>n!==f&&vis(n)).map(n=>{const r=n.getBoundingClientRect();return {l:r.left,r:r.right,t:r.top,b:r.bottom}});
    let best='up',bs=Infinity;
    ['up','right','left','down'].forEach((d,i)=>{const c=C[d];
      const out=Math.max(0,R.t-c.t)+Math.max(0,c.b-R.b)+Math.max(0,R.l-c.l)+Math.max(0,c.r-R.r);
      const s=out*w*10+nb.reduce((a,n)=>a+ov(c,n),0)+i;   /* raus aus dem Bild = schlimmer als Überdecken; Reihenfolge = Vorliebe */
      if(s<bs){bs=s;best=d}});
    f.dataset.dir=best;
  }
  sec.querySelectorAll('.beast').forEach(f=>{
    f.addEventListener('mouseenter',()=>place(f)); f.addEventListener('focusin',()=>place(f));
    new MutationObserver(()=>{if(f.classList.contains('hi')) place(f)}).observe(f,{attributes:true,attributeFilter:['class']});
  });
})();

/* ===== BV Quartier-Schalter: neben der Münsterspitze im freien Himmel, folgt der Hintergrund-Skalierung =====
   Bild-Koordinaten (wald.webp): freier Himmel rechts der Spitze x 0.45–0.565, vertikale Mitte y 0.215.
   Abbildung wie im Welt-Shader: v = 0.5 + (uv-(0.5,0.52))*z/s, z = 1.08*zoom, s = Cover-Verhältnis. */
(function(){
  const sec=document.getElementById('quartiere'), tg=sec&&sec.querySelector('.toggle'), cv=sec&&sec.querySelector('canvas.world'); if(!tg||!cv) return;
  const IMG=[2400,1028], X0=0.45, X1=0.565, YC=0.215;
  tg.classList.add('at-muenster');
  function place(){
    const pin=tg.offsetParent||sec.querySelector('.pin'), W=pin.clientWidth, H=pin.clientHeight;
    if(W<=900){tg.classList.remove('at-muenster');tg.style.left=tg.style.top=tg.style.transform='';return}
    tg.classList.add('at-muenster');
    const w=(window.BVWorld&&BVWorld.all||[]).find(o=>o.c===cv||o.css&&sec.contains(o.css));
    const z=1.08*((w&&w.zoom)||1), ra=W/H, ri=IMG[0]/IMG[1], s=ra>ri?[1,ri/ra]:[ra/ri,1];
    const sx=u=>(0.5+(u-0.5)*z/s[0])*W, sy=u=>(0.5+(u-0.52)*z/s[1])*H;
    const x0=sx(X0);
    const maxW=Math.min(340, Math.max(180, W-24));
    tg.style.maxWidth=maxW+'px';
    tg.style.width=maxW+'px';
    const left=Math.max(12, Math.min(x0, W-maxW-12));
    tg.style.left=left+'px';
    tg.style.top=Math.max(88, sy(YC)-8)+'px';
    tg.style.transform='none';
  }
  let last='';(function loop(){const w=(window.BVWorld&&BVWorld.all||[]).find(o=>o.c===cv);const key=innerWidth+'x'+innerHeight+':'+(w&&w.zoom);if(key!==last){last=key;place()}requestAnimationFrame(loop)})();
  addEventListener('resize',place);
})();

/* Peek-a-boo: ab und zu lugt kurz (≈3 s) ein anderes Logo-Tier vom Bildrand herein und zieht sich wieder zurück.
   Embleme = aus den Etiketten freigestellt – Ordner assets/web/peek, je ~150 px: Quartier-Tiere schwarz, Bärgtiere Kupfer.
   Pro Szene zufällig alle 20–45 s, nur solange die Szene sichtbar ist (IntersectionObserver), nie zwei gleichzeitig.
   Spots nur an Rändern/unteren Ecken; jeder Kandidat wird gegen Titel, Plaketten, Buttons, Tiere/Flaschen, Toggle, Nav geprüft.
   Aus bei prefers-reduced-motion, document.hidden, ≤900 px. Test: window.__peekRun('hero'|'quartiere'|'bergtiere'[, 'tiername'[, 'l'|'r'|'b'|'k']]). */
(function(){
  if(!('animate' in Element.prototype)) return;
  const RM=matchMedia('(prefers-reduced-motion:reduce)');
  const Q=['assets/web/peek/monbijou_marder.webp?v=0d1b88f8d2','assets/web/peek/schanzen_kater.webp?v=bec7c08af7','assets/web/peek/breitschplatz_hirsch.webp?v=0ec3d92ba9','assets/web/peek/matte_eule.webp?v=f521cb4202','assets/web/peek/laengass_dachs.webp?v=6eeeab3298','assets/web/peek/bollwerk_koeter.webp?v=88f1501a8b','assets/web/peek/wyler_falke.webp?v=c6d4620052'];
  const B=['assets/web/peek/gipfel_adler.webp?v=cff2e8affc','assets/web/peek/nebel_wolf.webp?v=1824bde537','assets/web/peek/steinschlag_bock.webp?v=67713b6c70','assets/web/peek/waldwiesen_biene.webp?v=4e139fb2a7','assets/web/peek/wildwasser_bieber.webp?v=a84d31dc56','assets/web/peek/absturz_milan.webp?v=0f081dbee8','assets/web/peek/waldbrand_salamander.webp?v=669ada0e0f','assets/web/peek/erdbeben_elch.webp?v=a051f17a43'];
  /* Ergänzt 24.11.: Fuchs (altes Logo, schwarz) für Quartier/Hero, Nöii-Linie-Embleme (Chipmunk, Elefant, Lemur, Panda; Kraftpapier-Gold) im Hero */
  const N=['assets/web/peek/chipmunk.webp?v=1cf9079fa9','assets/web/peek/elefant.webp?v=f72bd7d925','assets/web/peek/lemur.webp?v=7dc456505d','assets/web/peek/panda.webp?v=01b97d8bf1','assets/web/peek/fuchs.webp?v=7f22117fd1','assets/web/peek/monbijou_marder.webp?v=0d1b88f8d2'];
  const Q2=Q.concat(['assets/web/peek/fuchs.webp?v=7f22117fd1']);
  /* edges: l/r = seitlicher Rand (at = Höhe 0..1 der Szene), b = Unterkante (at = x 0..1), k = hinter einer Flasche hervor (at = Höhe auf der Flasche) */
  const CFG={
    hero:{set:N,edges:[['l',.3,.56],['r',.3,.56],['k',.12,.34]]},
    quartiere:{set:Q2,edges:[['r',.3,.62],['l',.6,.8],['b',.03,.97],['k',.1,.32],['k',.1,.32]]},
    bergtiere:{set:B,edges:[['r',.3,.62],['b',.25,.97],['k',.12,.34]]}
  };
  const BLOCK='.title,.plaque,.tocart,.toggle,.hint,.beast,.brand,.lg-fox,button,a,nav,.nav';
  const R=(a,b)=>a+Math.random()*(b-a);
  let busy=false;
  function blockers(pin){
    const out=[],nv=document.getElementById('nav');
    if(nv){const r=nv.getBoundingClientRect();out.push({l:-1e4,r:1e4,t:-1e4,b:r.bottom+8});}
    const PA=pin.clientWidth*pin.clientHeight;
    pin.querySelectorAll(BLOCK).forEach(e=>{const r=e.getBoundingClientRect();if(r.width&&r.height&&r.width*r.height<PA*.5&&getComputedStyle(e).visibility!=='hidden')out.push({l:r.left-14,r:r.right+14,t:r.top-14,b:r.bottom+14,e:e});});
    return out;
  }
  function spot(sec,pin,w,h,only){
    const P=pin.getBoundingClientRect(),bl=blockers(pin),E=CFG[sec.id].edges.filter(e=>!only||e[0]===only);
    for(let i=0;i<40;i++){
      const e=E[Math.floor(Math.random()*E.length)],a=R(e[1],e[2]);
      let r;
      if(e[0]==='k'){ /* hinter einer Flasche hervor: Tier startet ganz verdeckt hinter der Flasche und lugt seitlich raus */
        const bs=[...pin.querySelectorAll('.beast')].filter(b=>b.offsetParent&&+getComputedStyle(b).opacity>.6);if(!bs.length)continue;
        const host=bs[Math.floor(Math.random()*bs.length)],bo=(host.querySelector('.bottle3')||host).getBoundingClientRect();
        const kh=Math.min(h,bo.width*.85*h/w),kw=kh*w/h;if(kh<44)continue;
        const sd=Math.random()<.5?1:-1,y=bo.top+bo.height*a;
        r=sd>0?{l:bo.right-kw*.45,r:bo.right+kw*.55,t:y,b:y+kh}:{l:bo.left-kw*.55,r:bo.left+kw*.45,t:y,b:y+kh};
        const vis=sd>0?{l:bo.right,r:r.r,t:r.t,b:r.b}:{l:r.l,r:bo.left,t:r.t,b:r.b};
        if(r.l<P.left||r.r>P.right||r.t<P.top+60)continue;
        if(bl.some(b=>!host.contains(b.e)&&!(b.e&&b.e.contains&&b.e.contains(host))&&vis.l<b.r&&vis.r>b.l&&vis.t<b.b&&vis.b>b.t))continue;
        return {edge:'k',sd:sd,x:r.l-P.left,y:r.t-P.top,w:kw,h:kh};
      }
      if(e[0]==='l'){const y=P.top+P.height*a-h/2;r={l:P.left,r:P.left+w*.6,t:y,b:y+h};}
      else if(e[0]==='r'){const y=P.top+P.height*a-h/2;r={l:P.right-w*.6,r:P.right,t:y,b:y+h};}
      else{const x=P.left+P.width*a-w/2;r={l:x,r:x+w,t:P.bottom-h*.62,b:P.bottom};}
      if(r.l<P.left-1||r.r>P.right+1||r.t<P.top)continue;
      if(bl.some(b=>r.l<b.r&&r.r>b.l&&r.t<b.b&&r.b>b.t))continue;
      return {edge:e[0],x:r.l-P.left,y:r.t-P.top};
    }
    return null;
  }
  const last={};
  function run(id,name,only){
    const sec=document.getElementById(id),cfg=CFG[id];
    if(!sec||!cfg||busy||RM.matches||innerWidth<=900||document.hidden)return false;
    if(id==='hero'&&!sec.classList.contains('phase-b'))return false;
    if(document.querySelector('.lb.open'))return false;
    const pin=sec.querySelector('.pin');if(!pin)return false;
    const pr=pin.getBoundingClientRect();if(pr.top>innerHeight*.25||pr.bottom<innerHeight*.75)return false; /* Szene muss den Viewport füllen */
    let layer=pin.querySelector(':scope > .peek');
    if(!layer){layer=document.createElement('div');layer.className='peek';layer.setAttribute('aria-hidden','true');pin.insertBefore(layer,pin.querySelector(':scope > .beasts'));}
    const pool=name?cfg.set.filter(u=>u.indexOf('/'+name)>-1):cfg.set.filter(u=>u!==last[id]);
    const src=pool[Math.floor(Math.random()*pool.length)];if(!src)return false;
    busy=true;last[id]=src;
    const img=new Image();img.alt='';img.decoding='async';img.src=src;
    const done=()=>{img.remove();busy=false;};
    img.decode().then(()=>{
      const H=pin.clientHeight,h=Math.round(Math.max(64,Math.min(112,H*.12))),w=Math.round(h*img.naturalWidth/img.naturalHeight);
      const s=spot(sec,pin,w,h,only);if(!s){done();return;}
      img.style.width=(s.w||w)+'px';img.style.height=(s.h||h)+'px';img.className='peek-'+s.edge;
      let k;
      if(s.edge==='k'){
        const d=(s.w)*.55*s.sd,rz=6*s.sd;
        img.style.left=s.x+'px';img.style.top=s.y+'px';
        k=[{transform:'translateX('+(-d)+'px) rotate(0deg)'},{transform:'translateX(0) rotate('+rz+'deg)',offset:.24},{transform:'translateX('+(-d*.12)+'px) rotate('+(rz*.4)+'deg)',offset:.5},{transform:'translateX(0) rotate('+(rz*.9)+'deg)',offset:.72},{transform:'translateX('+(-d)+'px) rotate(0deg)'}];
      }else if(s.edge==='b'){
        const rz=R(-7,7),dy=h*.62;
        img.style.left=s.x+'px';img.style.top=(H-dy)+'px';
        k=[{transform:'translateY('+dy+'px) rotate('+rz+'deg)'},{transform:'translateY(0) rotate('+(rz*.4)+'deg)',offset:.22},{transform:'translateY(3px) rotate('+(-rz*.6)+'deg)',offset:.5},{transform:'translateY(0) rotate('+(rz*.3)+'deg)',offset:.74},{transform:'translateY('+dy+'px) rotate('+rz+'deg)'}];
      }else{
        const sg=s.edge==='l'?1:-1,d=w*.6*sg;
        img.style.top=s.y+'px';img.style[s.edge==='l'?'left':'right']=(-w*.4)+'px';
        k=[{transform:'translateX('+(-d)+'px) rotate('+(-14*sg)+'deg)'},{transform:'translateX(0) rotate('+(9*sg)+'deg)',offset:.22},{transform:'translateX('+(-3*sg)+'px) rotate('+(4*sg)+'deg)',offset:.5},{transform:'translateX(0) rotate('+(10*sg)+'deg)',offset:.74},{transform:'translateX('+(-d)+'px) rotate('+(-14*sg)+'deg)'}];
      }
      layer.appendChild(img);
      const an=img.animate(k,{duration:R(2600,3200),easing:'cubic-bezier(.45,0,.35,1)',fill:'both'});
      an.onfinish=an.oncancel=done;
    }).catch(done);
    return true;
  }
  window.__peekRun=run;
  if(RM.matches)return;
  Object.keys(CFG).forEach(id=>{
    const sec=document.getElementById(id);if(!sec)return;
    let vis=false,t=0;
    const tick=()=>{t=0;if(!vis)return;t=setTimeout(tick,run(id)?R(15000,32000):R(4000,9000));}; /* 24.11.: etwas öfter, weiterhin selten und nie zwei gleichzeitig */
    new IntersectionObserver(es=>{es.forEach(en=>{vis=en.isIntersecting;
      if(vis&&!t)t=setTimeout(tick,R(7000,16000));if(!vis&&t){clearTimeout(t);t=0;}});},{threshold:0}).observe(sec);
  });
})();

/* Mobile-Menü (Variante B, ≤760 px): Der Knopf #navmenu kommt aus account.js.
   Hier: Scroll sperren, solange das Menü offen ist, Escape schliesst, Sprachwahl im Menü zeigen. */
(function(){
  const nav=document.getElementById('nav')||document.querySelector('.nav'); if(!nav) return;
  const root=document.documentElement, mq=matchMedia('(max-width:760px)');
  const sync=()=>{ const open=mq.matches&&nav.classList.contains('menu-open'); root.classList.toggle('bv-menu-open',open);
    const b=document.getElementById('navmenu'); if(b) b.setAttribute('aria-expanded',open?'true':'false'); };
  new MutationObserver(sync).observe(nav,{attributes:true,attributeFilter:['class']});
  addEventListener('keydown',e=>{ if(e.key==='Escape'&&nav.classList.contains('menu-open')){ nav.classList.remove('menu-open'); const b=document.getElementById('navmenu'); if(b) b.focus(); } });
  (mq.addEventListener?mq.addEventListener('change',sync):mq.addListener(sync));
  sync();
})();
