from pathlib import Path
from PIL import Image,ImageOps
import numpy as np
R=Path("/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/runs/desktop-tiled-probe/sample-00.png")
B=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw/state4-ceramic-frame0-dpr2.gpu-rgba.bin")
screen=np.asarray(ImageOps.flip(Image.open(R).convert("RGBA")),dtype=np.uint8)
ref=np.frombuffer(B.read_bytes(),np.uint8).reshape(384,512,4)
sec=ref.copy()
sec[:,:16]=[0,0,0,255]
for x,expected,name in [(92,ref,"PRIMARY"),(810,sec,"SECONDARY")]:
    actual=screen[190:574,x:x+512]
    diff=np.abs(actual.astype(np.int16)-expected.astype(np.int16))
    maxrgb=diff[:,:,:3].max(axis=2)
    print(name,"MAX_RGB",diff.max(axis=(0,1)).tolist(),"P99",np.percentile(diff,99,axis=(0,1)).tolist(),
          "over3",int((maxrgb>3).sum()),"over5",int((maxrgb>5).sum()),
          "over10",int((maxrgb>10).sum()),"mean",float(diff[:,:,:3].mean()))

