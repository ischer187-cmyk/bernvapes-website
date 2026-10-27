# Matt-Stich: Glanzlichter weich komprimieren (Kappe + Label), Kappe leicht glätten. Eingabe/Ausgabe: web/produkte/*.webp
import numpy as np, glob, sys
from PIL import Image, ImageFilter
import cv2
for p in sorted(glob.glob('web/produkte/*.webp')):
    im=Image.open(p).convert('RGBA'); a=np.array(im).astype(float); H,W,_=a.shape
    rgb=a[:,:,:3]; al=a[:,:,3]
    lum=rgb@np.array([.299,.587,.114])
    # weiche Lichterkompression: ab 150 flacher, Maximum ~215
    knee=150.0; comp=np.where(lum>knee, knee+(lum-knee)*0.42, lum)
    gain=np.where(lum>1,comp/np.maximum(lum,1),1.0)[:,:,None]
    out=rgb*gain
    # Kappe (obere 22 %): zusätzlich leicht glätten, damit die Rillen-Highlights nicht blockig sind
    capH=int(H*0.22); cap=out[:capH].astype(np.uint8); cap=cv2.bilateralFilter(cap,7,40,5); out[:capH]=cap
    # leichte Entsättigung der Lichter (Plastikglanz), Papier-Look
    o=np.dstack([np.clip(out,0,255),al]).astype(np.uint8)
    Image.fromarray(o,'RGBA').save(p,quality=92,method=4)
print('ok')
