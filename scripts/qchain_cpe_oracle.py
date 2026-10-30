#!/usr/bin/env python3
"""CP-E independent oracle: source-locked GPU-resident outputs vs CP-D/CPU."""
import argparse
import csv
import hashlib
import json
import math
import struct
from pathlib import Path
from PIL import Image

MATERIALS=("ceramic","gel","metal","paper")
FIELD_NAMES=("height","heat","normal-z")
def check(ok, message):
    if not ok: raise ValueError(message)
def sha(data): return hashlib.sha256(data).hexdigest()
def readpng(path):
    with Image.open(path) as img:
        check(img.size==(512,384),"PNG_DIMENSIONS")
        return img.convert("RGBA").tobytes()
def rows(path):
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh,delimiter="\t"))
def channel_stats(a,b):
    check(len(a)==len(b)==786432,"RGBA_BYTES")
    differences=[abs(x-y) for x,y in zip(a,b)]
    return {"different_bytes":sum(bool(v) for v in differences),
            "maximum":max(differences),"mean":sum(differences)/len(differences)}
def verify(raw, original, previous, fields, receipt, compute_log):
    stages=json.loads(receipt.read_text())["stages"]
    ledger=rows(raw/"resident-ledger.tsv")
    check(len(stages)==5 and len(ledger)==40,"WRONG_COVERAGE")
    log=compute_log.read_text()
    check("QCHAIN_CP_E_RESIDENT_COMPUTE_WITNESS_PASS" in log,"MISSING_GPU_EXECUTION_LOG")
    check(log.count("CP_E_STAGE stage=")==5,"MISSING_GPU_STAGE")
    result={"schema":"gnu6.qchain.cpe_oracle.v1","gpu_driver_trace":"NOT_RUN",
            "device_graph":"ONE_WGPU_DEVICE_ONE_ENCODER_SIX_DISPATCHES",
            "frames":[],"fields":[]}
    for i in range(5):
        stem=f"scene-{i:02}"; proof=stages[i]
        scene=(original/f"{stem}.scene.txt").read_bytes()
        check(sha(scene)==proof["scene_sha256"],"SCENE_TAMPER")
        mask=(original/f"{stem}.f2-mask.bin").read_bytes()
        check(sha(mask)==proof["mask_sha256"],"MASK_TAMPER")
        signed=(raw/f"{stem}.gpu-f2-mask.bin").read_bytes()
        check(mask==signed,"RESIDENT_GPU_F2_MASK_DIFFERENCE")
        check(signed==(fields/f"{stem}.gpu-mask.bin").read_bytes(),"F2_F3_GPU_MASK_DIFFERENCE")
        analytics=(raw/f"{stem}.gpu-f3-analytic.f32raw").read_bytes()
        check(len(analytics)==196608*16,"F3_ANALYTICS_LENGTH")
        field_results={}
        for channel,offset in (("height",0),("heat",1),("normal-z",3)):
            reference=(fields/f"{stem}.gpu-{channel}.f32").read_bytes()
            check(len(reference)==196608*4,"F3_ORACLE_LENGTH")
            worst=0.0; total=0.0
            for j in range(196608):
                v=struct.unpack_from("<f",analytics,j*16+offset*4)[0]
                ref=struct.unpack_from("<f",reference,j*4)[0]
                check(math.isfinite(v) and math.isfinite(ref),"F3_NONFINITE")
                delta=abs(v-ref)
                worst=max(worst,delta);total+=delta
            check(worst<=0.003,"F3_NUMERIC_BUDGET")
            field_results[channel]={"maximum":worst,"mean":total/196608}
        for j in range(196608):
            m=struct.unpack_from("<f",analytics,j*16+8)[0]
            check(math.isfinite(m),"NONFINITE_MASK")
            check((m>0.5)==bool(signed[j]),"F3_ANALYTIC_MASK_MISMATCH")
        result["fields"].append({"stage":i,"binary_mask_exact":True,**field_results})
    seen=set()
    for row in ledger:
        i=int(row["stage"]);material=row["material"];frame=int(row["frame"])
        check(i in range(5) and material in ("ceramic","gel","metal","paper")
              and frame in (0,1),"INVALID_CASE")
        key=(i,material,frame)
        check(key not in seen,"DUPLICATE_FRAME")
        seen.add(key)
        check(row["backend"]=="vulkan_wgsl_gpu","GPU_BACKEND_SPOOF")
        check(row["digest"]==format(int(stages[i]["f2_semantic_digest"]),"016x"),
              "SCENE_IDENTITY_SPOOF")
        check(int(row["epoch"])==i,"EPOCH_REPLAY")
        check(int(row["dispatches"])==6,"WRONG_GPU_DISPATCHES")
        check(int(row["submits"])==1,"MULTI_SUBMIT_DRIFT")
        check(int(row["intermediate_host_transfers"])==0,"INTERMEDIATE_CPU_BRIDGE")
        check(int(row["final_readbacks"])==3,"DIAGNOSTIC_READBACK_DRIFT")
        stem=f"state{i}-{material}-frame{frame}-dpr2"
        gpu=(raw/f"{stem}.gpu-rgba.bin").read_bytes()
        baseline=readpng(previous/f"{stem}-gpu.png")
        d=channel_stats(gpu,baseline)
        check(d["different_bytes"]==0,"RESIDENT_GPU_FRAME_REGRESSION")
        if material=="ceramic" and frame==0:
            oracle=(original/f"scene-{i:02}.f4-rgba.bin").read_bytes()
            check(sha(oracle)==stages[i]["f4_rgba_sha256"],"CPU_RGBA_TAMPER")
            bounded=channel_stats(gpu,oracle)
            check(bounded["maximum"]<=12 and bounded["mean"]<=0.5,
                  "CPU_GPU_PARITY_BUDGET")
        result["frames"].append({"stage":i,"material":material,"frame":frame,
                                  "sha256":sha(gpu),"exact_vs_cpd_gpu":True})
    check(len(seen)==40,"COVERAGE_MISSING")
    result["verdict"]="QCHAIN_CPE_ONE_DEVICE_RESIDENT_GRAPH_40_FRAMES_EXACT_GPU_PARITY_PASS"
    result["gpu_wayland_e2e"]="NOT_RUN"
    result["cp03_hybrid60"]="OPEN"
    return result
def main():
    parser=argparse.ArgumentParser()
    for key in ("raw","original","previous","fields","receipt","compute_log","out"):
        parser.add_argument("--"+key.replace("_","-"),type=Path,required=True)
    a=parser.parse_args()
    check(not a.out.exists(),"REFUSE_OVERWRITE")
    result=verify(a.raw,a.original,a.previous,a.fields,a.receipt,a.compute_log)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],"frames",len(result["frames"]),
          "f3_field_stages",len(result["fields"]))
if __name__=="__main__":
    main()
