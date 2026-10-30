#!/usr/bin/env python3
"""Independent CP-JA7C oracle: reconstructs all facts directly, never imports runner."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps

REGIONS=((92,190,604,574),(810,190,1322,574))

def require(ok,code):
    if not ok: raise AssertionError(code)

def sha(b):
    return hashlib.sha256(b).hexdigest()

def read_region(full,box):
    x0,y0,x1,y1=box
    return full[y0:y1,x0:x1]

def pixel_metrics(actual,reference):
    d=np.abs(actual.astype(np.int16)-reference.astype(np.int16))
    return (int(np.any(d[:,:,:3]>3,axis=2).sum()),
            int(np.count_nonzero(d[:,:,3])),
            list(map(int,d.max(axis=(0,1)))))

def audit(root,baseline,receipt):
    screen_paths=sorted(root.glob("sample-*.png"))
    require(len(screen_paths)==8 and
            [p.name for p in screen_paths]==[f"sample-{i:02}.png" for i in range(8)],
            "EIGHT_UNALTERED_SAMPLE_NAMES_REQUIRED")
    app=(root/"viewer.stdout").read_text(errors="replace")
    client=(root/"viewer.stderr").read_text(errors="replace")
    server=(root/"weston-timeline-proto.log").read_text(errors="replace")
    compositor=(root/"weston.stdout").read_text(errors="replace")
    stages=json.loads(receipt.read_text())["stages"]
    require(len(stages)==5,"CANONICAL_STAGES_NOT_FIVE")
    refs=[]
    for material in ("ceramic","gel","metal","paper"):
        for j in (0,1):
            raw=(baseline/f"state4-{material}-frame{j}-dpr2.gpu-rgba.bin").read_bytes()
            require(len(raw)==512*384*4,"CANONICAL_FRAME_BYTES")
            refs.append((sha(raw), np.frombuffer(raw,np.uint8).reshape(384,512,4).copy()))
    records=re.findall(
        r"CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+) stage=(\d+) elapsed_us=(\d+)"
        r" received_to_submit_us=(\d+) epoch=(\d+) scene_sha256=([0-9a-f]{64})"
        r" rgba_sha256=([0-9a-f]{64}) dimensions=(\d+)x(\d+)", app)
    require(len(records)==120 and [int(r[0]) for r in records]==list(range(120)),
            "SOURCE_SEQUENCE_GAP_DUPLICATE")
    for r in records:
        seq=int(r[0])
        stage=int(r[1])
        require(stage==min(seq,4) and int(r[4])==stage and
                r[5]==stages[stage]["scene_sha256"] and
                r[7:]==("512","384"), "SOURCE_SCENE_OR_DIMENSION_DRIFT")
        if seq>=5:
            require(r[6]==refs[((seq-5)//12)%8][0],
                    "CANONICAL_FRAME_SHA_MISMATCH")
    samples=[]
    for idx,p in enumerate(screen_paths):
        with Image.open(p) as im:
            require(im.size==(1536,1024),"COMPOSITOR_CAPTURE_SIZE_CHANGED")
            full=np.asarray(ImageOps.flip(im.convert("RGBA")),dtype=np.uint8)
        ref_sha,ref=refs[idx]
        secondary=ref.copy()
        secondary[:,:16,:]=[0,0,0,255]
        left,right=(read_region(full,box) for box in REGIONS)
        primary_errors=pixel_metrics(left,ref)
        secondary_errors=pixel_metrics(right,secondary)
        require(primary_errors[:2]==(0,0) and secondary_errors[:2]==(0,0),
                "COMPOSITOR_PIXEL_BOUNDS_EXCEEDED_"+str(idx))
        require(pixel_metrics(left,secondary)[0]>0 and
                pixel_metrics(right,ref)[0]>0,
                "PRIMARY_SECONDARY_SURFACES_ALIASED_"+str(idx))
        samples.append({"index":idx,"phase":"dual_visible",
                        "png_sha256":sha(p.read_bytes()),"canonical_sha256":ref_sha,
                        "primary_max_rgba_delta":primary_errors[2],
                        "secondary_max_rgba_delta":secondary_errors[2]})
    from qchain_cpja7db_oracle_tail import verify_native
    return verify_native(root,client,app,server,compositor,samples)

def main():
    p=argparse.ArgumentParser()
    for key in ("run","baseline","receipt","out"):
        p.add_argument("--"+key,required=True,type=Path)
    a=p.parse_args()
    require(not a.out.exists(),"REFUSE_OVERWRITE")
    report=audit(a.run,a.baseline,a.receipt)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"screenshots",len(report["screenshots"]),
          "typed_acks",report["acknowledged"])

if __name__=="__main__":
    main()
