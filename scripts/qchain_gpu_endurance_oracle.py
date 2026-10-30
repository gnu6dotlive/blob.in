#!/usr/bin/env python3
"""Independent CP-H2 attribution audit for private multi-cycle Vulkan evidence."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
def check(ok,msg):
    if not ok:raise ValueError(msg)
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(262144),b""):
            h.update(chunk)
    return h.hexdigest()
def percentile(values,p):
    sorted_values=sorted(values)
    return sorted_values[min(len(values)-1,math.ceil(len(values)*p)-1)]
def verify(root,baseline,cpu_receipt,run):
    claim=json.loads(run.read_text())
    check(claim["verdict"]=="QCHAIN_CPH2_FRESH_GPU_ENGINE_AND_SEALED_IPC_RESTART_PASS","BAD_CLAIM")
    stages=json.loads(cpu_receipt.read_text())["stages"]
    originals={x.name:sha(x) for x in baseline.iterdir() if x.is_file()}
    check(len(originals)==52,"WRONG_REFERENCE_COUNT")
    cycles=claim["engine_cycle_count"]
    check(cycles>=3 and len(claim["cycles"])==cycles,"CYCLE_COUNT")
    data=[]

    for i in range(1,cycles+1):
        c=root/f"cycle-{i:02}"
        raw=c/"raw"
        present={x.name:x for x in raw.iterdir() if x.is_file()}
        check(present.keys()==originals.keys(),f"FILE_SET_DRIFT_{i}")
        for name,fn in present.items():
            check(sha(fn)==originals[name],f"RAW_GPU_DRIFT_{i}_{name}")
        log=c/"compute.log"
        text=log.read_text()
        check("QCHAIN_CP_F_PERSISTENT_SESSION_PASS states=5 materials=4 frames=40" in text,
              f"GPU_COMPUTE_NOT_COMPLETED_{i}")
        check(text.count("CP_F_STAGE stage=")==5,f"GPU_STAGES_MISSING_{i}")
        manifest=json.loads((c/"gpu-source-manifest.json").read_text())
        check(manifest["transport_version"]=="QCHAIN-GPU-FRAME-v1",
              f"GPU_PROTOCOL_CHANGED_{i}")
        check(manifest["compute_run_log_sha256"]==sha(log),f"COMPUTE_LOG_PROVENANCE_{i}")
        check(manifest["cpu_receipt_sha256"]==sha(cpu_receipt),f"CPU_SOURCE_PROVENANCE_{i}")
        check(len(manifest["stages"])==5,f"MANIFEST_SCOPE_{i}")
        for j,m in enumerate(manifest["stages"]):
            expected=f"state{j}-ceramic-frame0-dpr2.gpu-rgba.bin"
            check(m["stage"]==j and m["epoch"]==j and
                  m["scene_sha256"]==stages[j]["scene_sha256"] and
                  m["semantic_digest"]==stages[j]["f2_semantic_digest"] and
                  m["gpu_file"]==expected and
                  m["gpu_rgba_sha256"]==originals[expected],
                  f"MANIFEST_SCENE_IDENTITY_{i}_{j}")
        recovery=json.loads((c/"restart-verdict.json").read_text())
        check(recovery["verdict"]=="QCHAIN_GPU_SOURCE_IPC_RESTART_AFTER_DISCONNECT_PASS",
              f"RESTART_NOT_QUALIFIED_{i}")
        check(recovery["total_verified_frames"]==15 and len(recovery["cases"])==4,
              f"IPC_FRAMES_MISSING_{i}")
        for case in recovery["cases"]:
            idx=case["case"]
            folder=c/"restarts"/f"case-{idx:02}"
            check(sha(folder/"source.log")==case["server_log_sha256"],
                  f"SERVER_LOG_TAMPER_{i}_{idx}")
            if case["scenario"]=="fresh_socket_five_frames":
                check(case["frames"]==5 and case["server_exit"]==case["client_exit"]==0,
                      f"IPC_PRODUCER_FAILED_{i}_{idx}")
                check(sha(folder/"client.log")==case["client_log_sha256"],
                      f"CLIENT_LOG_TAMPER_{i}_{idx}")
                check((folder/"client.log").read_text().count("CPH_GPU_IPC_VERIFIED stage=")==5,
                      f"CLIENT_MISSING_RECEIPT_{i}_{idx}")
            else:
                check(case["scenario"]=="early_disconnect" and
                      case["server_exit"]!=0 and case["fail_closed"],
                      f"FAULT_WAS_NOT_DENIED_{i}_{idx}")
        record=claim["cycles"][i-1]
        check(record["index"]==i and record["engine"]["process_exit"]==0
              and record["artifacts"]["files_exact"]==52
              and record["ipc_verified_frames"]==15
              and record["recovery_receipt_sha256"]==sha(c/"restart-verdict.json"),
              f"CYCLE_RECEIPT_WRONG_{i}")
        data.append(record)
    fault=claim["mid_computation_interruption"]
    check(fault["first_frame_observed"] and fault["interrupted"] and
          0<fault["gpu_frames_before_termination"]<40 and fault["process_exit"]!=0,
          "MID_COMPUTE_FAILURE_NOT_PROVEN")
    check(len(list((root/"fault-mid-frame").glob("*.gpu-rgba.bin")))
          ==fault["gpu_frames_before_termination"],"FAULT_EVIDENCE_DRIFT")
    no_gpu=claim["gpu_startup_failure"]
    check(no_gpu["exit_code"]!=0 and not no_gpu["gpu_fallback"] and
          not any((root/"fault-gpu-unavailable").iterdir()),
          "VULKAN_FAILURE_FELL_BACK")
    engine=[x["engine"]["seconds"] for x in data]
    total=[x["full_chain_seconds"] for x in data]
    rss=[x["engine"]["peak_process_rss_bytes_sampled"] for x in data
         if x["engine"]["peak_process_rss_bytes_sampled"] is not None]
    check(len(rss)==cycles,"RSS_SAMPLING_INCOMPLETE")
    return {"schema":"gnu6.qchain.cph2_independent_endurance.v1",
       "verdict":"QCHAIN_CPH2_FRESH_GPU_ENGINE_AND_SEALED_IPC_RESTART_PASS",
       "cycles_verified":cycles,"gpu_frames_newly_computed":40*cycles,
       "gpu_artifacts_sha256_exact":52*cycles,
       "ipc_frames_received":15*cycles,"full_source_processes":4*cycles,
       "mid_compute_termination_verified":True,"no_vulkan_fallback_verified":True,
       "gpu_compute_wall_seconds":{
         "median":statistics.median(engine),"p95":percentile(engine,0.95),
         "maximum":max(engine),"minimum":min(engine)},
       "full_chain_wall_seconds":{
         "median":statistics.median(total),"p95":percentile(total,0.95),
         "maximum":max(total),"minimum":min(total)},
       "sampled_peak_cpu_rss_bytes":{"median":statistics.median(rss),
          "p95":percentile(rss,0.95),"maximum":max(rss)},
       "limits":{"no_gpu_driver_timestamp":True,
           "no_gpu_vram_profiling":True,
           "no_actual_wayland_new_capture":True,
           "not_a_realtime_60fps_benchmark":True,
           "not_long_running_in_one_process":True}}
def main():
    a=argparse.ArgumentParser()
    for name in ("root","baseline","cpu_receipt","run","out"):
        a.add_argument("--"+name.replace("_","-"),type=Path,required=True)
    args=a.parse_args()
    check(not args.out.exists(),"REFUSE_TO_OVERWRITE")
    report=verify(args.root,args.baseline,args.cpu_receipt,args.run)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"cycles",report["cycles_verified"],
          "gpu_frames",report["gpu_frames_newly_computed"],
          "ipc",report["ipc_frames_received"])
if __name__=="__main__":
    main()
