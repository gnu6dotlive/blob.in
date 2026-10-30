from pathlib import Path
from PIL import Image,ImageOps
import numpy as np
P=Path("/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/runs/desktop-probe-01/sample-00.png")
B=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
expected=np.frombuffer((B/"state4-ceramic-frame0-dpr2.gpu-rgba.bin").read_bytes(),dtype=np.uint8).reshape(384,512,4)
secondary=expected.copy()
secondary[:,:16]=np.array([0,0,0,255],dtype=np.uint8)
im=np.asarray(ImageOps.flip(Image.open(P).convert("RGBA")),dtype=np.uint8)
height=im.shape[0]-384+1
width=im.shape[1]-512+1
print("SCREEN",im.shape,"CANDIDATE_OFFSETS",height,width)
def search_exact(target,anchors):
    ok=np.ones((height,width),dtype=bool)
    for dy,dx in anchors:
        pix=target[dy,dx]
        sub=im[dy:dy+height,dx:dx+width]
        ok &= np.all(sub==pix,axis=2)
        print("ANCHOR",(dx,dy),pix.tolist(),"COUNT",int(ok.sum()))
        if (dy,dx)==anchors[0]:
            scores=[]
            for yy,xx in np.argwhere(ok):
                region=im[yy:yy+384,xx:xx+512]
                d=np.count_nonzero(np.any(region!=target,axis=2))
                scores.append((int(d),int(xx),int(yy)))
            print("FIRST_ANCHOR_BEST",sorted(scores)[:12])
    positions=np.argwhere(ok)
    print("POSITION_CANDIDATES",len(positions),positions[:20].tolist())
    for y,x in positions[:100]:
        region=im[y:y+384,x:x+512]
        diff=np.count_nonzero(np.any(region!=target,axis=2))
        print("EXACT_CANDIDATE",(int(x),int(y)),"DIFF",int(diff))
    return positions
search_exact(secondary,[(175,125),(160,240),(280,370),(350,490)])

