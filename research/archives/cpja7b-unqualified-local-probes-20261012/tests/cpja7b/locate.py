from pathlib import Path
from PIL import Image,ImageOps
import numpy as np
P=Path("/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/runs/desktop-probe-01/sample-00.png")
B=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
original=np.frombuffer((B/"state4-ceramic-frame0-dpr2.gpu-rgba.bin").read_bytes(),dtype=np.uint8).reshape(384,512,4)
screen=np.asarray(Image.open(P).convert("RGBA"),dtype=np.uint8)
ss=[("raw",screen),("flip",screen[::-1])]
expected=original.copy()
secondary=expected.copy()
secondary[:,:16]=np.array([0,0,0,255],dtype=np.uint8)
for screen_name,im in ss:
    h,w=im.shape[0]-384+1,im.shape[1]-512+1
    for target_name,target in [("primary",expected),("secondary",secondary)]:
        scores=np.zeros((h,w),dtype=np.int16)
        for dy in (40,80,120,160,200,260,320,350):
            for dx in (10,50,120,180,250,300,370,440,480):
                sub=im[dy:dy+h,dx:dx+w]
                scores+=np.all(sub==target[dy,dx],axis=2).astype(np.int16)
        best=np.unravel_index(int(scores.argmax()),scores.shape)
        candidates=np.argwhere(scores>=scores.max()-1)
        print(screen_name,target_name,"BEST_EQ",int(scores.max()),"of",72,"TOP",(int(best[1]),int(best[0])),"CANDIDATES",len(candidates))
        tested=[]
        for y,x in candidates[:2000]:
            crop=im[y:y+384,x:x+512]
            d=int(np.count_nonzero(np.any(crop!=target,axis=2)))
            tested.append((d,int(x),int(y)))
        print("MIN_FULL_DIFF",sorted(tested)[:6])

