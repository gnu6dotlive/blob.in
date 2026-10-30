#!/usr/bin/env python3
"""Independent CP-F source-locked persistent Vulkan session artifact oracle."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

def sha(data): return hashlib.sha256(data).hexdigest()
def require(condition, reason):
    if not condition: raise ValueError(reason)
def tsv(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))
def verify(raw, baseline, cpu, receipt, log, previous_receipt):
    receipt_data=json.loads(receipt.read_text())
    stages=receipt_data["stages"]
    older=json.loads(previous_receipt.read_text())
    require(len(stages)==5 and len(older["frames"])==40,"BASELINE_SCOPE")
    reference_files=sorted(x.name for x in baseline.iterdir() if x.is_file())
    current_files=sorted(x.name for x in raw.iterdir() if x.is_file())
    require(current_files==sorted(reference_files+["session-stats.tsv"]),
            "UNEXPECTED_OR_MISSING_OUTPUT")
    for i in range(5):
        stem=f"scene-{i:02}"
        proof=stages[i]
        require(sha((cpu/f"{stem}.scene.txt").read_bytes())==proof["scene_sha256"],
                "SCENE_ORACLE_TAMPER")
        canonical=(cpu/f"{stem}.f2-mask.bin").read_bytes()
        require(sha(canonical)==proof["mask_sha256"],"MASK_ORACLE_TAMPER")
        require((raw/f"{stem}.gpu-f2-mask.bin").read_bytes()==canonical,
                "PERSISTENT_GPU_MASK_DRIFT")
    stats=tsv(raw/"session-stats.tsv")
    require(len(stats)==1,"SESSION_STATS_UNTRUSTED")
    expected={"device_creations":"1","pipeline_creations":"3",
              "reusable_storage_allocations":"5","frames_rendered":"40"}
    require(all(stats[0].get(k)==v for k,v in expected.items()),"SESSION_REUSE_CONTRACT")
    ledger=tsv(raw/"resident-ledger.tsv")
    require(len(ledger)==40,"FRAME_LEDGER_COUNT")
    seen=set()
    for line in ledger:
        state=int(line["stage"]); frame=int(line["frame"])
        material=line["material"]
        key=(state,material,frame)
        require(state in range(5) and material in ("ceramic","gel","metal","paper")
                and frame in (0,1),"INVALID_FRAME_ID")
        require(key not in seen,"DUPLICATE_FRAME_ID")
        seen.add(key)
        require(line["digest"]==format(int(stages[state]["f2_semantic_digest"]),"016x"),
                "SCENE_SEMANTIC_BINDING")
        require(int(line["epoch"])==state,"EPOCH_MISMATCH")
        require(line["backend"]=="vulkan_wgsl_gpu","BACKEND_MISMATCH")
        require((line["dispatches"],line["submits"],
                 line["intermediate_host_transfers"],line["final_readbacks"])
                ==("6","1","0","3"),"RENDER_PATH_COUNTER_MISMATCH")
    logs=log.read_text()
    require("QCHAIN_CP_F_PERSISTENT_SESSION_PASS states=5 materials=4 frames=40" in logs,
            "SESSION_EXECUTION_LOG_MISSING")
    for state, rendered in enumerate((1,9,17,25,33)):
        require(f"CP_F_STAGE stage={state} " in logs
                and f"session_frames={rendered}" in logs,
                "SESSION_CONTINUITY_MISSING")
    # Validate identity, chronology and GPU provenance before exact artifact parity.
    exact=0
    for name in reference_files:
        data=(baseline/name).read_bytes()
        require((raw/name).read_bytes()==data,"BASELINE_BYTES_MISMATCH "+name)
        exact+=1
    return {"schema":"gnu6.qchain.cpf_oracle.v1",
        "verdict":"QCHAIN_CPF_PERSISTENT_DEVICE_40_FRAMES_GPU_EXACT_PARITY_PASS",
        "baseline_files_exact":exact,"frames_exact":40,"f2_signed_masks_exact":5,
        "f3_analytical_buffers_exact":5,"cpu_source_sha_attested":True,
        "session_stats":stats[0],"independent_driver_allocation_trace":"NOT_RUN",
        "host_readback_per_frame":3,"gpu_frame_source_wayland":"NOT_RUN",
        "persistent_gpu_buffers_across_frames":5,"cp03_hybrid60":"OPEN"}
def main():
    parser=argparse.ArgumentParser()
    for key in ("raw","baseline","cpu","receipt","log","previous_receipt","out"):
        parser.add_argument("--"+key.replace("_","-"),required=True,type=Path)
    args=parser.parse_args()
    require(not args.out.exists(),"OUTPUT_ALREADY_EXISTS")
    result=verify(args.raw,args.baseline,args.cpu,args.receipt,
                  args.log,args.previous_receipt)
    args.out.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],"files",result["baseline_files_exact"])
if __name__=="__main__": main()
