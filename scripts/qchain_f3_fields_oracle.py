#!/usr/bin/env python3
"""Independent F3 GPU readback comparator against canonical archives and fresh CPU fields."""
import argparse
from array import array
import hashlib
import json
from math import isfinite
from pathlib import Path

def sha(b): return hashlib.sha256(b).hexdigest()
def require(ok, msg):
    if not ok: raise ValueError(msg)
def float_data(path):
    b=path.read_bytes()
    require(len(b)==512*384*4, "BAD_F32_LENGTH")
    a=array("f"); a.frombytes(b)
    return a
def evaluate(probe, cpu, receipt):
    proofs=json.loads(receipt.read_text())["stages"]
    require(len(proofs)==5,"STAGE_COUNT")
    out=[]
    for i in range(5):
        stem=f"scene-{i:02}"
        raw=(cpu/f"{stem}.scene.txt").read_bytes()
        require(sha(raw)==proofs[i]["scene_sha256"],"SCENE_HASH_CHANGED")
        reference=(cpu/f"{stem}.f2-mask.bin").read_bytes()
        device=(probe/f"{stem}.gpu-mask.bin").read_bytes()
        cpu_mask=(probe/f"{stem}.cpu-mask.bin").read_bytes()
        require(len(device)==len(reference)==196608,"BAD_MASK_LENGTH")
        require(device==cpu_mask==reference,"F3_GPU_BINARY_MASK_MISMATCH")
        ref_f3=(cpu/f"{stem}.f3-rgba.bin").read_bytes()
        require((probe/f"{stem}.cpu-rgba.bin").read_bytes()==ref_f3,"F3_CPU_RGBA_DRIFT")
        gpu=(probe/f"{stem}.gpu-rgba.bin").read_bytes()
        require(len(gpu)==len(ref_f3)==786432,"F3_RGBA_LENGTH")
        difference=[abs(x-y) for x,y in zip(gpu,ref_f3)]
        require(max(difference)<=8,"F3_RGBA_OUT_OF_BUDGET")
        fields={}
        for channel in ("height","heat","normal-z"):
            a=float_data(probe/f"{stem}.cpu-{channel}.f32")
            b=float_data(probe/f"{stem}.gpu-{channel}.f32")
            require(all(isfinite(x) for x in a) and all(isfinite(x) for x in b),"F3_NONFINITE")
            errors=[abs(x-y) for x,y in zip(a,b)]
            maximum=max(errors)
            require(maximum<=0.003,"F3_FIELD_OUT_OF_BUDGET")
            fields[channel]={"max_abs":maximum,"mean_abs":sum(errors)/len(errors)}
        out.append({"stage":i,"scene_sha256":proofs[i]["scene_sha256"],
                    "mask_exact":True,"gpu_rgba_different_bytes":sum(x!=0 for x in difference),
                    "gpu_rgba_max_channel":max(difference),"fields":fields})
    return {"schema":"gnu6.qchain.f3_independent_readback.v1","verdict":
      "QCHAIN_F3_GPU_READBACK_BINARY_MASK_EXACT_FIELDS_BOUNDED_PASS",
      "source":"Vulkan/WGSL GPU readback; independent Python comparator",
      "exact_rgba":False,"field_tolerance_max_abs":0.003,"stages":out}
def main():
    a=argparse.ArgumentParser()
    for key in ("probe","cpu","receipt","out"): a.add_argument("--"+key,type=Path,required=True)
    args=a.parse_args()
    require(not args.out.exists(),"REFUSE_OVERWRITE")
    result=evaluate(args.probe,args.cpu,args.receipt)
    args.out.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],"stages",len(result["stages"]))
if __name__=="__main__": main()
