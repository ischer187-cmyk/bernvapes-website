# Chroma-Key (grün oder magenta) → RGBA. Benutzung: key(np_rgb, 'g'|'m') -> np_rgba
import numpy as np, cv2
def key(a, mode):
    a=a.astype(np.int32); r,g,b=a[...,0],a[...,1],a[...,2]
    if mode=='g': d=g-np.maximum(r,b)
    else: d=np.minimum(r,b)-g
    alpha=1-np.clip((d-25)/(80-25),0,1)
    out=a.copy()
    if mode=='g':
        m=d>8; out[...,1]=np.where(m,np.minimum(g,np.maximum(r,b)+8),g)
    else:
        m=d>8; lim=g+8; out[...,0]=np.where(m,np.minimum(r,np.maximum(lim,r-d)),r); out[...,2]=np.where(m,np.minimum(b,np.maximum(lim,b-d)),b)
    al=(alpha*255).astype(np.uint8)
    # nur grösste Komponenten behalten, Kante leicht einziehen
    n,lab,st,_=cv2.connectedComponentsWithStats((al>128).astype(np.uint8),connectivity=8)
    keep=np.zeros_like(al,bool)
    for i in range(1,n):
        if st[i,cv2.CC_STAT_AREA]>0.002*al.size: keep|=(lab==i)
    keep=cv2.dilate(keep.astype(np.uint8),np.ones((5,5),np.uint8))>0
    al=np.where(keep,al,0).astype(np.uint8)
    al=cv2.erode(al,np.ones((3,3),np.uint8)); al=cv2.GaussianBlur(al,(0,0),0.6)
    return np.dstack([np.clip(out,0,255).astype(np.uint8),al])
