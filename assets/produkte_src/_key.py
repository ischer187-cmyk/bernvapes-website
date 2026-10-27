# Produktfotos (weisser Studiohintergrund) freistellen — nur Hintergrund, der mit dem Bildrand verbunden ist,
# damit Glanzlichter auf Kappen/Labels NICHT transparent werden. Weiss-Saum wird per Unmultiply entfernt.
import cv2, numpy as np, glob, os, sys
src=sys.argv[1]; dst=sys.argv[2]
def key(path):
    bgr=cv2.imread(path); a=bgr.astype(int); H,W,_=a.shape
    lum=a.mean(2); sat=a.max(2)-a.min(2)
    cand=((lum>196)&(sat<34)).astype(np.uint8)      # auch weiche Studio-Schatten gelten als Hintergrund
    n,lab=cv2.connectedComponents(cand,connectivity=4)
    border=set(np.unique(np.concatenate([lab[0,:],lab[-1,:],lab[:,0],lab[:,-1]])))
    border.discard(0)
    bg=np.isin(lab,list(border))
    sil=~bg
    # Flasche ist zeilenweise konvex: pro Zeile alles zwischen linker und rechter Kante opak (schliesst Leckagen ins weisse Label)
    xl=np.full(H,-1); xr=np.full(H,-1)
    for y in range(H):
        xs=np.where(sil[y])[0]
        if len(xs): xl[y]=xs.min(); xr[y]=xs.max()
    rows=np.where(xl>=0)[0]
    # Körper: gerade Seiten → häufigste Kantenposition ist die wahre Kante
    wd=xr-xl; body=rows[wd[rows]>0]
    def mode(v): v=v[v>=0]; vals,cnt=np.unique(v,return_counts=True); return vals[np.argmax(cnt)]
    ml,mr=mode(xl[body]),mode(xr[body]); mw=mr-ml
    # Körperbereich = von der ersten bis zur letzten Zeile, die (fast) volle Breite hat
    full=rows[wd[rows]>=0.93*mw]; y0,y1=full.min(),full.max()
    alpha=np.zeros((H,W),np.uint8)
    for y in rows:
        if y0<=y<=y1: alpha[y,ml:mr+1]=255                         # Körper: feste Kanten
        elif y<y0: alpha[y,xl[y]:xr[y]+1]=255                       # Kappe: eigene Kontur (darf breiter sein als der Körper)
        else: alpha[y,max(xl[y],ml):min(xr[y],mr)+1]=255          # Boden: eigene Kontur, nie breiter als der Körper (Schattenreste)
    # kleine Fitzel (Schattenreste) entfernen: nur grösste Komponente behalten
    n2,lab2,stats,_=cv2.connectedComponentsWithStats(alpha,connectivity=8)
    if n2>2:
        big=1+np.argmax(stats[1:,cv2.CC_STAT_AREA]); alpha=((lab2==big).astype(np.uint8))*255
    alpha=cv2.erode(alpha,np.ones((3,3),np.uint8))
    alpha=cv2.GaussianBlur(alpha,(0,0),0.7).astype(float)/255
    rgb=bgr[:,:,::-1].astype(float); A=np.clip(alpha,0.02,1)[:,:,None]
    fixed=np.clip((rgb-(1-A)*255)/A,0,255)
    rgb=np.where(alpha[:,:,None]<0.98,fixed,rgb)
    return np.dstack([rgb,alpha*255]).astype(np.uint8)
from PIL import Image
for p in sorted(glob.glob(src+'/*.jpg')):
    im=Image.fromarray(key(p),'RGBA'); im=im.crop(im.getbbox())
    k=os.path.basename(p).replace('Bernvapes_','').replace('.jpg','').lower().replace('-','_')
    s=1200/im.height; im2=im.resize((max(1,round(im.width*s)),1200),Image.LANCZOS)
    canvas=Image.new('RGBA',(im2.width+10,1210),(0,0,0,0)); canvas.alpha_composite(im2,(5,0))
    canvas.save(f'{dst}/{k}.webp',quality=92,method=4); print(k,canvas.size)
