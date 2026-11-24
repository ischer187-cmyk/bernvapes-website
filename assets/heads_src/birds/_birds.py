# Sprite-Sheets (4 Frames, Greenscreen) -> freigestellte Einzelframes, Sprite-Strip + animierte WebP-Loops
import sys, os, time, numpy as np, cv2
from PIL import Image
sys.path.insert(0,'../grumpy'); SRC=sys.argv[1] if len(sys.argv)>1 else '.'; from _key import key
OUT='../../web/birds'; os.makedirs(OUT,exist_ok=True)
BIRDS=dict(x.split(':') for x in (sys.argv[2].split(',') if len(sys.argv)>2 else ['schwalbe:70','dohle:110','adler:150'])); BIRDS={k:int(v) for k,v in BIRDS.items()}
H=400  # Ausgabehöhe px pro Frame
for n,ms in BIRDS.items():
    a=np.asarray(Image.open(SRC+'/'+n+'_sheet.png').convert('RGB'))
    k=key(a,'g'); al=k[...,3]
    num,lab,st,_=cv2.connectedComponentsWithStats((al>60).astype(np.uint8),connectivity=8)
    comps=sorted([i for i in range(1,num)],key=lambda i:-st[i,cv2.CC_STAT_AREA])
    # Komponenten den 4 Spalten zuordnen (nach x-Zentrum)
    W=a.shape[1]; cols=[[] for _ in range(4)]
    for i in comps:
        if st[i,cv2.CC_STAT_AREA]<300: continue
        cx=st[i,0]+st[i,2]/2; cols[min(3,int(cx/(W/4)))].append(i)
    frames=[]
    for c in cols:
        m=np.isin(lab,c); m=cv2.dilate(m.astype(np.uint8),np.ones((7,7),np.uint8))>0
        f=k.copy(); f[...,3]=np.where(m,f[...,3],0)
        ys,xs=np.where(f[...,3]>128)
        frames.append([f,None,None,xs.min(),ys.min(),ys.max(),xs.max()])
    # Anker: Kopf aus Frame 1 (Schnabelspitze = rechtester Punkt) per Template-Matching in allen Frames suchen
    f0=frames[0]; a0=f0[0]; ys,xs=np.where(a0[...,3]>128); xr=xs.max(); yr=int(np.median(ys[xs>=xr-3]))
    tw,th=int(a.shape[0]*0.09),int(a.shape[0]*0.07)
    tpl=(a0[yr-th:yr+th//2, xr-tw:xr+4,:3].astype(np.float32)*(a0[yr-th:yr+th//2, xr-tw:xr+4,3:]/255.))
    for fr in frames:
        x0_,y0_,y1_,x1_=fr[3],fr[4],fr[5],fr[6]
        bx0=max(0,x0_-tw); by0=max(0,y0_-th)
        img=(fr[0][by0:y1_+th, bx0:x1_+10,:3].astype(np.float32)*(fr[0][by0:y1_+th, bx0:x1_+10,3:]/255.)).astype(np.float32)
        sc=0.5
        r=cv2.matchTemplate(cv2.resize(img,None,fx=sc,fy=sc),cv2.resize(tpl.astype(np.float32),None,fx=sc,fy=sc),cv2.TM_CCOEFF_NORMED); _,_,_,(mx,my)=cv2.minMaxLoc(r)
        fr[1]=bx0+int(mx/sc)+tw; fr[2]=by0+int(my/sc)+th
    frames=[tuple(fr) for fr in frames]
    # gemeinsame Box relativ zum Anker
    L=max(xr-x0 for f,xr,yr,x0,y0,y1,xm in frames)+8; T=max(yr-y0 for f,xr,yr,x0,y0,y1,xm in frames)+8
    B=max(y1-yr for f,xr,yr,x0,y0,y1,xm in frames)+8; R=max(8,max(xm-xr for f,xr,yr,x0,y0,y1,xm in frames)+8)
    cw,ch=L+R,T+B; ims=[]
    for f,xr,yr,*_ in frames:
        can=np.zeros((ch,cw,4),np.uint8)
        sx,sy=xr-L,yr-T
        src=f[max(0,sy):sy+ch, max(0,sx):sx+cw]
        can[max(0,-sy):max(0,-sy)+src.shape[0], max(0,-sx):max(0,-sx)+src.shape[1]]=src
        im=Image.fromarray(can,'RGBA'); im=im.resize((round(cw*H/ch),H),Image.LANCZOS); ims.append(im)
    w=ims[0].width
    for j,im in enumerate(ims): im.save(f'{OUT}/{n}_f{j+1}.png')
    strip=Image.new('RGBA',(w*4,H)); [strip.paste(im,(j*w,0)) for j,im in enumerate(ims)]
    strip.save(f'{OUT}/{n}_sprite.webp',quality=88,method=6)
    # Loop: hoch -> level -> runter -> halb hoch
    ims[0].save(f'{OUT}/{n}.webp',save_all=True,append_images=ims[1:],duration=ms,loop=0,quality=85,method=6,disposal=2)
    # Gleit-Variante: 2 Schläge, dann Flügel waagrecht halten
    seq=[0,1,2,3,0,1,2,3,1]; dur=[ms]*8+[ms*14]
    ims[0].save(f'{OUT}/{n}_gleiten.webp',save_all=True,append_images=[ims[i] for i in seq[1:]],duration=dur,loop=0,quality=85,method=6,disposal=2)
    print(n,'frame',w,'x',H,'ratio',round(w/H,3))
