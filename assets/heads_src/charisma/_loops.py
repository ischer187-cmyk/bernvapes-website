# Video (Chroma) → animiertes, transparentes WebP + passendes Standbild (gleicher Ausschnitt)
import sys, numpy as np, cv2
sys.path.insert(0,'../grumpy'); from _key import key
from PIL import Image
n,mode=sys.argv[1],sys.argv[2]; OUT='../../web/loops_charisma/'
still=key(np.array(Image.open(f'{n}_key.png').convert('RGB')),mode); S=still.shape[0]
cap=cv2.VideoCapture(f'{n}.mp4'); frames=[]; i=0
while True:
    ok,f=cap.read()
    if not ok: break
    if i%2==0: frames.append(key(cv2.cvtColor(f,cv2.COLOR_BGR2RGB),mode))
    i+=1
V=frames[0].shape[0]
# gemeinsamer Ausschnitt: Vereinigung aller Alphas (im Video-Massstab) + Standbild
u=np.zeros((V,V),bool)
for f in frames: u|=f[...,3]>20
u|=cv2.resize(still[...,3],(V,V))>20
ys,xs=np.where(u); pad=6; x0,x1,y0,y1=max(xs.min()-pad,0),min(xs.max()+pad,V),max(ys.min()-pad,0),min(ys.max()+pad,V)
W=600; H=round(W*(y1-y0)/(x1-x0))
out=[Image.fromarray(f[y0:y1,x0:x1],'RGBA').resize((W,H),Image.LANCZOS) for f in frames]
out[0].save(OUT+f'{n}.webp',save_all=True,append_images=out[1:],duration=83,loop=0,quality=72,method=4)
k=S/V; st=Image.fromarray(still,'RGBA').crop((round(x0*k),round(y0*k),round(x1*k),round(y1*k))); st.save(OUT+f'{n}_still.webp',quality=92,method=5)
print(n,len(out),(W,H),st.size,round(W/H,3))
