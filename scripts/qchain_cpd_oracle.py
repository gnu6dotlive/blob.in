#!/usr/bin/env python3
"""Independent CP-D verifier: F2 GPU signed-mask bytes and F4 GPU regression provenance."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from PIL import Image

def need(ok, reason):
    if not ok: raise ValueError(reason)
def digest(raw):
    return hashlib.sha256(raw).hexdigest()
def rgba(path):
    with Image.open(path) as img:
        need(img.size==(512,384), "FRAME_DIMENSIONS")
        return img.convert("RGBA").tobytes()
def rows(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f,delimiter="\t"))
def mask_claim(path, canonical, proof):
    data=path.read_bytes()
    need(len(data)==196608 and set(data).issubset({0,1}),"GPU_SIGNED_MASK_FORMAT")
    need(digest(canonical)==proof["mask_sha256"],"CANONICAL_MASK_TAMPERING")
    need(data==canonical,"GPU_SIGNED_MASK_MISMATCH")
    return digest(data)
def evaluate(root, cpu, f3_field_root, baseline_f4):
    receipt=json.loads((cpu.parent/"qchain-reconciliation.json").read_text())
    require_stages=receipt["stages"]
    led2=rows(root/"f2-mask/gpu-f2-mask-ledger.tsv")
    led4=rows(root/"f4/ledger-dpr2-reducedtrue.tsv")
    need(len(led2)==5 and len(led4)==40,"COVERAGE_MISSING")
    log=(root/"f4-run.log").read_text()
    need("mask_source=F2_GPU_SIGNED_MASK_VULKAN_READBACK_REUPLOAD" in log,"GPU_PROVENANCE_NOT_OBSERVED")
    need("F4_PASS frames=40 gpu_frames=40" in log,"F4_COMPLETION_MISSING")
    result={"schema":"gnu6.qchain.cpd_independent_oracle.v1",
            "source":"F2 GPU signed-mask WGSL + GPU F3 + F4 effects; host readback/reupload remains",
            "f2":[],"f4":[],"gpu_signed_masks_exact":True,"gpu_f4_regression_exact":True,
            "device_resident_zero_copy":False,"cpu_rasterization_used_for_f4_input":False}
    for i in range(5):
        proof=require_stages[i]
        scene=(cpu/f"scene-{i:02}.scene.txt").read_bytes()
        need(digest(scene)==proof["scene_sha256"],"SCENE_DRIFT")
        fields=dict(line.split("=",1) for line in scene.decode().splitlines() if "=" in line)
        row=led2[i]
        need(int(row["stage"])==i and int(row["epoch"])==i
             and row["digest"]==fields["digest"],"F2_GPU_MASK_IDENTITY")
        need(row["backend"]=="vulkan_wgsl_gpu" and row["mask_mismatches"]=="0",
             "F2_GPU_BACKEND")
        original=(cpu/f"scene-{i:02}.f2-mask.bin").read_bytes()
        sha=mask_claim(root/f"f2-mask/scene-{i:02}.gpu-f2-mask.bin",original,proof)
        need((f3_field_root/f"scene-{i:02}.gpu-mask.bin").read_bytes()==original,
             "GPU_F2_F3_MASK_DIVERGENCE")
        result["f2"].append({"stage":i,"semantic_digest":fields["digest"],
                              "scene_sha256":proof["scene_sha256"],
                              "gpu_signed_mask_sha256":sha,"exact":True})
    for row in led4:
        i=int(row["state"]); mat=row["material"]; frame=int(row["frame"])
        need(i in range(5) and mat in ("ceramic","gel","metal","paper") and frame in (0,1),
             "F4_INVALID_CASE")
        expected=format(int(require_stages[i]["f2_semantic_digest"]),"016x")
        need(row["digest"]==expected and int(row["epoch"])==i,"F4_IDENTITY_DRIFT")
        need(row["backend"]=="gpu" and int(row["dispatches"])==4,"F4_GPU_DISPATCH_MISSING")
        need(int(row["reset_gpu"])==frame+1,"F4_REDUCED_MOTION_DRIFT")
        name=f"state{i}-{mat}-frame{frame}-dpr2"
        new=rgba(root/f"f4/{name}-gpu.png")
        before=rgba(baseline_f4/f"{name}-gpu.png")
        need(new==before,f"F4_GPU_OUTPUT_CHANGED {name}")
        cpu_image=rgba(root/f"f4/{name}-cpu.png")
        ref=rgba(baseline_f4/f"{name}-cpu.png")
        need(cpu_image==ref,f"F4_CPU_REFERENCE_CHANGED {name}")
        errors=[abs(x-y) for x,y in zip(cpu_image,new)]
        need(max(errors)<=12 and sum(errors)/len(errors)<=0.5,
             f"F4_BOUNDED_PARITY_FAIL {name}")
        result["f4"].append({"stage":i,"material":mat,"frame":frame,
                              "gpu_sha256":digest(new),"regression_exact":True,
                              "max_channel_vs_cpu":max(errors)})
    need(len({(x["stage"],x["material"],x["frame"]) for x in result["f4"]})==40,
         "F4_DUPLICATE_CASE")
    result["verdict"]="QCHAIN_CPD_GPU_SIGNED_MASK_EXACT_F4_GPU_HYBRID_HOST_BRIDGE_PASS"
    return result

def main():
    ap=argparse.ArgumentParser()
    for key in ("root","cpu","f3_fields","baseline_f4","out"):
        ap.add_argument("--"+key.replace("_","-"),type=Path,required=True)
    a=ap.parse_args()
    need(not a.out.exists(),"REFUSE_OVERWRITE")
    result=evaluate(a.root,a.cpu,a.f3_fields,a.baseline_f4)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],"f2",len(result["f2"]),"f4",len(result["f4"]))
if __name__=="__main__":
    main()
