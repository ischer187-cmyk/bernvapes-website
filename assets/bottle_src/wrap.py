from PIL import Image, ImageFilter
import numpy as np, math, sys, os
BASE=Image.open("bottle_src/bottle_base.png").convert("RGBA"); W,H=BASE.size
X0,X1,Y0,Y1=22,331,470,1480            # Körperzone
CX=(X0+X1)/2; R=(X1-X0)/2
PHI=math.pi*1.06                        # Winkel, den das Label um die Flasche abdeckt
def wrap_label(label_path, out_name, vpos=0.5):
    lab=Image.open(label_path).convert("RGB")
    unrolled_w=R*PHI                   # abgewickelte Breite in px
    lh=int(unrolled_w*lab.height/lab.width)
    lab=lab.resize((int(unrolled_w)+1,lh),Image.LANCZOS); L=np.array(lab).astype(np.float32)
    zone_h=Y1-Y0; top=int(Y0+(zone_h-lh)*vpos); top=max(Y0,top); bottom=min(Y1,top+lh)
    layer=np.zeros((H,W,4),dtype=np.float32)
    xs=np.arange(int(X0),int(X1)+1); t=np.clip((xs-CX)/R,-1,1); th=np.arcsin(t)
    u=0.5+th/PHI; sx=np.clip((u*(lab.width-1)).astype(int),0,lab.width-1)
    shade=0.52+0.48*np.cos(th)                               # Rundung
    spec=np.exp(-((t+0.42)/0.17)**2)*0.22+np.exp(-((t-0.62)/0.1)**2)*0.08   # Glanzstreifen
    rows=np.arange(top,bottom); sy=np.clip(rows-top,0,lab.height-1)
    block=L[sy][:,sx,:]                                      # (rows, cols, 3)
    block=block*shade[None,:,None]+255*spec[None,:,None]
    layer[top:bottom,xs[0]:xs[-1]+1,:3]=np.clip(block,0,255)
    # Alpha nur innerhalb der Flasche
    balpha=np.array(BASE.getchannel("A")).astype(np.float32)/255
    am=np.zeros((H,W),dtype=np.float32); am[top:bottom,xs[0]:xs[-1]+1]=1
    # Kanten des Labels oben/unten leicht weich
    layer[...,3]=am*balpha*255
    lay=Image.fromarray(layer.astype(np.uint8),"RGBA")
    full=BASE.copy(); full.alpha_composite(lay)
    os.makedirs("web/bottles2",exist_ok=True)
    full.save(f"web/bottles2/{out_name}.webp","WEBP",quality=88,method=4)
    lay.save(f"web/bottles2/{out_name}_label.webp","WEBP",quality=88,method=4)
    return full
if __name__=="__main__":
    wrap_label(sys.argv[1],sys.argv[2])
