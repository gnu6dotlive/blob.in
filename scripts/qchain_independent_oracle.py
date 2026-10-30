#!/usr/bin/env python3
"""Independent fixture-to-GPU-artifact oracle; no import from producer's Rust implementation."""
import argparse
import csv
from collections import deque
import hashlib
import json
from pathlib import Path
from PIL import Image

W, H = 512, 384
MAT = ("ceramic", "gel", "metal", "paper")
EXPECTED = ((2, 0), (1, 0), (1, 1), (1, 0), (2, 0))
def sha(b):
    return hashlib.sha256(b).hexdigest()
def need(cond, msg):
    if not cond:
        raise ValueError(msg)
def png_bytes(p):
    with Image.open(p) as image:
        need(image.size == (W, H), f"BAD_CAPTURE_DIMENSIONS {p}")
        return image.convert("RGBA").tobytes()
def statistics(a, b):
    need(len(a) == len(b) == W * H * 4, "RGBA_LENGTH_MISMATCH")
    diffs = [abs(x-y) for x, y in zip(a,b)]
    return {"different_bytes":sum(d>0 for d in diffs),
            "max_channel":max(diffs), "mean_abs":sum(diffs)/len(diffs),
            "exact":not any(diffs)}
def topology(mask):
    need(len(mask) == W*H and set(mask) <= {0,1}, "INVALID_BINARY_MASK")
    visited=bytearray(len(mask)); comp=holes=0
    for p in range(len(mask)):
        if visited[p]: continue
        color=mask[p]; visited[p]=1; q=deque([p]); edge=False
        while q:
            i=q.popleft(); x=i%W; y=i//W
            edge |= x==0 or x==W-1 or y==0 or y==H-1
            for j in ((i-1 if x else -1),(i+1 if x<W-1 else -1),
                      (i-W if y else -1),(i+W if y<H-1 else -1)):
                if j>=0 and not visited[j] and mask[j]==color:
                    visited[j]=1; q.append(j)
        if color: comp+=1
        elif not edge: holes+=1
    return (comp,holes)
def projected_mask(rgba):
    return bytes(1 if rgba[i+1]>39 and rgba[i+3]==255 else 0
                 for i in range(0,len(rgba),4))
def ledger(p, required_rows):
    with p.open(newline="") as f: rows=list(csv.DictReader(f, delimiter="\t"))
    need(len(rows)==required_rows, "WRONG_LEDGER_ROW_COUNT")
    return rows
def verify(cpu, f2, f3, f4, receipt):
    origin=json.loads(receipt.read_text())
    need(origin["verdict"]=="F2_F3_F4_CPU_CHAIN_PASS_BRIDGE_NOT_RUN","BAD_CPU_ORACLE")
    l2=ledger(f2/"ledger-dpr2.tsv",5)
    l3=ledger(f3/"material-ledger-dpr2.tsv",20)
    l4=ledger(f4/"ledger-dpr2-reducedtrue.tsv",40)
    results={"schema":"gnu6.qchain.independent_gpu_oracle.v1",
      "scope":"artifact-level independent reconciliation, GPU provenance relies additionally on execution logs",
      "canonical_frames":[],"f3_material_cases":[],"f4_cases":[],
      "f2_projection_mask_pixel_exact":True,"f2_mask_matches_binary_canonical":True,
      "f3_canonical_pixel_exact":True,"f4_canonical_pixel_exact":True}
    need(len(origin["stages"])==5,"WRONG_CANONICAL_STAGES")
    for i in range(5):
        name=f"scene-{i:02}"
        scene=(cpu/f"{name}.scene.txt").read_bytes()
        fields=dict(line.split("=",1) for line in scene.decode().splitlines() if "=" in line)
        proof=origin["stages"][i]
        need(proof["stage"]==i and proof["epoch"]==i,"BAD_EPOCH")
        need(sha(scene)==proof["scene_sha256"],"SOURCE_SHA_DRIFT")
        need(fields["epoch"]==str(i) and fields["digest"]==proof["f2_semantic_digest"],
             "SEMANTIC_SCENE_IDENTITY_MISMATCH")
        mask=(cpu/f"{name}.f2-mask.bin").read_bytes()
        reference_f3=(cpu/f"{name}.f3-rgba.bin").read_bytes()
        reference_f4=(cpu/f"{name}.f4-rgba.bin").read_bytes()
        for content,key in ((mask,"mask_sha256"),(reference_f3,"f3_rgba_sha256"),
                            (reference_f4,"f4_rgba_sha256")):
            need(sha(content)==proof[key],f"ORIGINAL_SHA_DRIFT {key} stage {i}")
        need(topology(mask)==EXPECTED[i],f"CANONICAL_TOPOLOGY_WRONG {i}")
        row=l2[i]
        need(int(row["step"])==i and int(row["epoch"])==i and row["selected_backend"]=="gpu",
             f"F2_PROVENANCE_WRONG {i}")
        need(row["semantic_digest"]==format(int(fields["digest"]),"016x"),
             f"F2_SEMANTIC_DIGEST_WRONG {i}")
        need((int(row["components"]),int(row["holes"]))==EXPECTED[i],
             f"F2_LEDGER_TOPOLOGY_WRONG {i}")
        cpu_projection=png_bytes(f2/f"step{i}-cpu-dpr2.png")
        gpu_projection=png_bytes(f2/f"step{i}-gpu-dpr2.png")
        projected_cpu=projected_mask(cpu_projection)
        projected_gpu=projected_mask(gpu_projection)
        need(projected_cpu==projected_gpu,f"F2_GPU_PROJECTION_MASK_DRIFT {i}")
        need(topology(projected_gpu)==EXPECTED[i],f"F2_GPU_TOPOLOGY_DRIFT {i}")
        signed_vs_aa=sum(a!=b for a,b in zip(mask,projected_gpu))
        raster_stats=statistics(cpu_projection,gpu_projection)
        need(raster_stats["max_channel"]<=6 and raster_stats["mean_abs"]<=0.15,
             f"F2_RGBA_BOUNDED_PARITY_RED {i}")
        results["f2_mask_matches_binary_canonical"] &= signed_vs_aa==0
        results["f2_projection_mask_pixel_exact"] &= projected_cpu==projected_gpu
        f3_gpu=png_bytes(f3/f"s{i}-ceramic-dpr2-gpu.png")
        f3_cpu=png_bytes(f3/f"s{i}-ceramic-dpr2-cpu.png")
        need(f3_cpu==reference_f3,f"F3_CPU_ARCHIVE_DRIFT {i}")
        f3diff=statistics(reference_f3,f3_gpu)
        need(f3diff["max_channel"]<=8 and f3diff["mean_abs"]<=0.35,
             f"F3_CANONICAL_BOUNDED_RED {i}")
        f4_cpu=png_bytes(f4/f"state{i}-ceramic-frame0-dpr2-cpu.png")
        f4_gpu=png_bytes(f4/f"state{i}-ceramic-frame0-dpr2-gpu.png")
        need(f4_cpu==reference_f4,f"F4_CPU_ARCHIVE_DRIFT {i}")
        f4diff=statistics(reference_f4,f4_gpu)
        need(f4diff["max_channel"]<=12 and f4diff["mean_abs"]<=0.5,
             f"F4_CANONICAL_BOUNDED_RED {i}")
        results["f3_canonical_pixel_exact"] &= f3diff["exact"]
        results["f4_canonical_pixel_exact"] &= f4diff["exact"]
        results["canonical_frames"].append({"stage":i,
          "scene_sha256":proof["scene_sha256"],"semantic_digest":fields["digest"],
          "f2_projection_mask_cpu_gpu_exact":True,
          "f2_aa_projection_vs_signed_field_different_pixels":signed_vs_aa,
          "f2_rgba_gpu_vs_cpu":raster_stats,"f3_rgba_gpu_vs_archive":f3diff,
          "f4_rgba_gpu_vs_archive":f4diff})

    for row in l3:
        i=int(row["step"]); mat=row["material"]
        need(i in range(5) and mat in MAT and int(row["dpr"])==2 and row["backend"]=="gpu",
             "F3_LEDGER_UNEXPECTED_CASE")
        need(row["digest"]==format(int(origin["stages"][i]["f2_semantic_digest"]),"016x"),
             "F3_LEDGER_SEMANTIC_DRIFT")
        need((int(row["components"]),int(row["holes"]))==EXPECTED[i],"F3_LEDGER_TOPOLOGY_DRIFT")
        stats=statistics(png_bytes(f3/f"s{i}-{mat}-dpr2-cpu.png"),
                         png_bytes(f3/f"s{i}-{mat}-dpr2-gpu.png"))
        need(stats["max_channel"]<=8 and stats["mean_abs"]<=0.35,"F3_MATERIAL_PARITY_RED")
        results["f3_material_cases"].append({"stage":i,"material":mat,**stats})
    need(len({(v["stage"],v["material"]) for v in results["f3_material_cases"]})==20,
         "F3_CASE_DUPLICATE")
    for row in l4:
        i=int(row["state"]); mat=row["material"]; frame=int(row["frame"])
        need(i in range(5) and mat in MAT and frame in (0,1) and int(row["dpr"])==2,
             "F4_WRONG_CASE")
        need(row["backend"]=="gpu" and int(row["dispatches"])==4, "F4_NOT_GPU_COMPUTE")
        need(row["digest"]==format(int(origin["stages"][i]["f2_semantic_digest"]),"016x"),
             "F4_LEDGER_SEMANTIC_DRIFT")
        need((int(row["components"]),int(row["holes"]))==EXPECTED[i],"F4_LEDGER_TOPOLOGY_DRIFT")
        need(int(row["reset_cpu"])==int(row["reset_gpu"])==frame+1,
             "F4_REDUCED_MOTION_STATE_DRIFT")
        prefix=f"state{i}-{mat}-frame{frame}-dpr2"
        stats=statistics(png_bytes(f4/f"{prefix}-cpu.png"),png_bytes(f4/f"{prefix}-gpu.png"))
        need(stats["max_channel"]<=12 and stats["mean_abs"]<=0.5,
             f"F4_BOUNDED_PARITY_RED {prefix}")
        results["f4_cases"].append({"stage":i,"material":mat,"frame":frame,**stats})
    need(len({(v["stage"],v["material"],v["frame"]) for v in results["f4_cases"]})==40,
         "F4_CASE_DUPLICATE")
    results.update({"cpu_archive_sha_verified":True,
      "f2_five_topologies":True,"f3_20_bounded":True,"f4_40_bounded":True,
      "f4_backend_class":"HYBRID_GPU_F3_AND_GPU_EFFECTS_WITH_CPU_F2_MASK",
      "gpu_compute_full_autonomous":False,"gpu_wayland_observed":False,
      "exact_f2_f3_f4_rgba_parity":False,
      "verdict":"QCHAIN_F2_F3_F4_VULKAN_BOUNDED_ARTIFACT_PARITY_PASS_HYBRID_F4"})
    return results

def main():
    ap=argparse.ArgumentParser()
    for arg in ("cpu","f2","f3","f4","receipt","out"):
        ap.add_argument("--"+arg,required=True,type=Path)
    a=ap.parse_args()
    need(not a.out.exists(),"REFUSE_OVERWRITE")
    result=verify(a.cpu,a.f2,a.f3,a.f4,a.receipt)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],"f2",len(result["canonical_frames"]),
          "f3",len(result["f3_material_cases"]),"f4",len(result["f4_cases"]))
    for v in result["canonical_frames"]:
        print("stage",v["stage"],"f2 AA-vs-signed",
              v["f2_aa_projection_vs_signed_field_different_pixels"],
              "F3 diff",v["f3_rgba_gpu_vs_archive"]["different_bytes"],
              "F4 diff",v["f4_rgba_gpu_vs_archive"]["different_bytes"])
if __name__=="__main__":
    main()
