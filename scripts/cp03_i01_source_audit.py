#!/usr/bin/env python3
"""blob.in CP03 source/proof inventory; NEVER a HYBRID-HERO-60 qualification."""
import argparse,hashlib,json
from pathlib import Path

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def witness(path,probes):
    if not path.is_file():
        return {"status":"MISSING","path":str(path),"sha256":None,"observations":[]}
    data=path.read_text(errors="replace")
    checks=[{"marker":mark,"observed":mark in data} for mark in probes]
    return {"status":"SOURCE_INSPECTED" if all(t["observed"] for t in checks) else "SOURCE_UNCONFIRMED",
            "path":str(path),"sha256":digest(path),
            "size_bytes":path.stat().st_size,"observations":checks}

def inventory(history,experiment,cuda,receipts):
    core=history/"blobin-core/src"
    f4=experiment/"F4/src"
    checks={
      "historical_2d_path":witness(core/"path.rs",["cubic","Contour","Path"]),
      "historical_2d_tessellation":witness(core/"tessellate.rs",["pub struct Mesh","pub x: f32","pub y: f32","lyon"]),
      "historical_blob_animation":witness(core/"blob.rs",["pub trait Blob","wobble","Path"]),
      "historical_animation_solver":witness(core/"solve.rs",["pub struct Spring","pub fn tick"]),
      "gpu_f4_source":witness(f4/"gpu_session.rs",["pub struct PersistentSession","render_next"]),
      "synthetic_cuda_2d_csg":witness(cuda/"csg.cu",["struct Primitive","float x, y, radius","compose("]),
      "cuda_scope_disclosure":witness(cuda/"README.md",["not a general arbitrary","synthetic","Private research"]),
      "cp03_numeric_receipt":witness(receipts/"cp03-numeric-gate.json",["NOT_QUALIFIED","input_samples_count"]),
    }
    missing=[k for k,v in checks.items() if v["status"]!="SOURCE_INSPECTED"]
    existing=(receipts/"cp03-numeric-gate.json")
    if existing.is_file():
        cp03=json.loads(existing.read_text())
        if cp03.get("cp03_pass") is not False or cp03.get("metrics_pass") is not False:
            raise ValueError("CP03_NUMERIC_RECEIPT_UNEXPECTED_TRUE")
    result={
      "schema":"blob.in.cp03.i01_source_inventory.v1",
      "identity":"blob.in / HYBRID-HERO-60@1",
      "resolution":[1280,720],
      "status":"DONOR_INVENTORY_PASS" if not missing else "DONOR_INVENTORY_HOLD",
      "proofs":checks,"missing_or_unconfirmed":missing,
      "source_capability_assessment":{
       "historical_core":"2D cubic Bezier paths and 2D lyon tessellation only; 3D closed/open mixed boolean NOT PROVEN",
       "f4_pipeline":"512x384 GPU frame/material/effects proof; 1280x720 hybrid SDF+mesh scene NOT PROVEN",
       "cuda01":"synthetic 2D analytic-circle CSG benchmark; 3D mixed SDF+mesh scene NOT PROVEN",
       "prior_gpu05_pacing":"CP03 numeric receipt explicitly NOT_QUALIFIED; 0 input samples",
      },
      "integrated_scene":{
       "workload":"HYBRID-HERO-60@1",
       "actual_native_1280x720_scene_executed":False,
       "sdf_gpu":False,"gpu_csg":False,"closed_mesh_3d":False,
       "open_mesh_3d":False,"mixed_boolean_3d":False,
       "animated_transform":False,"actual_input":False
      },
      "cp03_gates":{f"G{i:02d}":"HOLD" for i in range(1,8)},
      "cp03_hybrid60_pass":False,
      "production_promotion":False,
      "next":"Acquire authoritative CP03 geometry contract and build actual integrated scene."
    }
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--history",type=Path,required=True)
    p.add_argument("--experiment",type=Path,required=True)
    p.add_argument("--cuda",type=Path,required=True)
    p.add_argument("--receipt-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():
        raise RuntimeError("REFUSE_OVERWRITE_EVIDENCE")
    data=inventory(a.history,a.experiment,a.cuda,a.receipt_dir)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(data,indent=2)+"\n")
    print(data["status"],"CP03="+str(data["cp03_hybrid60_pass"]),
          "inspected="+str(sum(v["status"]=="SOURCE_INSPECTED" for v in data["proofs"].values())),
          "HOLD="+",".join(k for k,v in data["cp03_gates"].items() if v=="HOLD"))

if __name__=="__main__":main()
