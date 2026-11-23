import sys, numpy as np, cv2
from PIL import Image
for n in sys.argv[1:]:
    bgr=cv2.imread(f'flasche_{n}.png'); a=bgr.astype(int); H,W,_=a.shape
    lum=a.mean(2); sat=a.max(2)-a.min(2)
    cand=((lum>205)&(sat<30)).astype(np.uint8)
    nn,lab=cv2.connectedComponents(cand,connectivity=4)
    border=set(np.unique(np.concatenate([lab[0,:],lab[-1,:],lab[:,0],lab[:,-1]]))); border.discard(0)
    sil=~np.isin(lab,list(border)); al=np.zeros((H,W),np.uint8)
    for y in range(H):
        xs=np.where(sil[y])[0]
        if len(xs): al[y,xs.min():xs.max()+1]=255
    n2,l2,st,_=cv2.connectedComponentsWithStats(al,connectivity=8); big=1+np.argmax(st[1:,cv2.CC_STAT_AREA]); al=((l2==big)*255).astype(np.uint8)
    al=cv2.erode(al,np.ones((3,3),np.uint8)); alf=cv2.GaussianBlur(al,(0,0),0.8).astype(float)/255
    rgb=bgr[:,:,::-1].astype(float); A=np.clip(alf,0.02,1)[:,:,None]; fx=np.clip((rgb-(1-A)*255)/A,0,255); rgb=np.where(alf[:,:,None]<0.98,fx,rgb)
    im=Image.fromarray(np.dstack([rgb,alf*255]).astype(np.uint8),'RGBA'); im=im.crop(im.getbbox())
    s=1600/im.height; im=im.resize((round(im.width*s),1600),Image.LANCZOS); im.save(f'../../web/loops_charisma/flasche_{n}.webp',quality=92,method=5)
    q=np.array(im).astype(int); c=(q[:,:,:3].max(2)-q[:,:,:3].min(2))[:,int(im.width*.2):int(im.width*.8)].mean(1); r=np.where(c>28)[0]; r=r[r>320]
    print(n,im.size,'label',round(r.min()/1600,3),round(r.max()/1600,3))
