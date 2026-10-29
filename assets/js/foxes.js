/* Drei weisse Low-Poly-Füchse. Nie gleichzeitig, 2.8 s Pause, einmal pro Sichtbarkeit.
   H.264 wird im Canvas per Colorkey freigestellt (VP9-Alpha schreibt dieser ffmpeg-Build nicht).
   Standbilder sind transparente WebPs. prefers-reduced-motion zeigt nur das Standbild. */
(function(){
  var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  var GAP=2800, V='20261029c';
  var slots=[
    {id:'blick', sel:'#hero', gate:function(){var h=document.getElementById('hero');return !!(h&&h.classList.contains('world-in'));}},
    {id:'laufen', sel:'#quartiere'},
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
    if(reduce){
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
    if(s.el) s.el.classList.remove('on');
    if(s.video){ s.video.pause(); try{s.video.currentTime=0;}catch(e){} }
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
      slots.forEach(function(s){ if(s.el) s.el.classList.toggle('on', !!(best&&best.s===s)); });
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
  setInterval(tick, 360);
  window.__foxSlots=slots;
})();
