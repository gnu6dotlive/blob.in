#!/usr/bin/env python3
"""Independent CP-JA7G producer, whole-board guard and active Vulkan oracle."""
import argparse,hashlib,json,statistics
from pathlib import Path
from qchain_cpja7g_independent_oracle import verify
BASE=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
RECEIPT=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json")
NAMES=(("active-balanced-3600-02","balanced"),("active-eco-3600","eco"))
def need(ok,msg):
    if not ok:raise AssertionError(msg)
def load(p):return json.loads(p.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def check_sensors(name,profile,summary,sensors):
    need(summary["verdict"]=="CPJA7G_GUARDED_ACTIVE_GPU_PASS"
         and summary["runner_exit"]==0 and summary["error"] is None
         and summary["profile"]==profile
         and summary["wall_timeout_s"]==240
         and summary["temperature_abort_c"]==75
         and summary["power_abort_w"]==180
         and len(sensors)==summary["samples"]>=95,
         "GPU_SENSOR_RECEIPT_INVALID_"+name)
    gaps=[(b["monotonic_ns"]-a["monotonic_ns"])/1e9
          for a,b in zip(sensors,sensors[1:])]
    need(all(0<gap<=3 for gap in gaps) and
         all(row["test_name"]==name and 0<=row["temp_c"]<75
         and 0<=row["power_w"]<180 and
         0<=row["gpu_util_pct"]<=100
         and 0<=row["mem_mib"]<=65536
         and row["query_duration_ms"]<=2500 for row in sensors),
         "GPU_SENSOR_TIME_OR_CEILING_INVALID_"+name)
    need(sensors[0]["temp_c"]<65 and
         max(x["temp_c"] for x in sensors)==summary["temp_max_c"]
         and max(x["power_w"] for x in sensors)==summary["power_max_w"]
         and max(x["gpu_util_pct"] for x in sensors)==summary["gpu_util_max_pct"]
         and summary["host_power_attributable_to_app"] is False,
         "GPU_SENSOR_SUMMARY_FALSIFIED_"+name)
    return True
def validate(root,repo):
    anchor=load(root/"preflight/anchor.json")
    need(anchor["parent"]=="1bde593ab0ffcfa4cd696d79a2d644c08835a973"
         and anchor["contract_sha256"]==sha(repo/"docs/QCHAIN-CP-JA7G-ACTIVE-GPU-CONTRACT-20261012.md")
         and anchor["viewer_sha256"]==sha(root/"preflight/bin/qchain_cpja7_dual_viewer")
         and anchor["active_engine_sha256"]==sha(root/"preflight/bin/qchain_cpja7g_active_gpu_live"),
         "PRE_RUN_SOURCE_BINARY_CONTRACT_DRIFT")
    records=[]
    for name,profile in NAMES:
        p=root/"runs"/name
        produced=load(p/"run-verdict.json")
        witness=verify(p,BASE,RECEIPT)
        saved=load(root/"oracle"/(name+".json"))
        need(saved==witness and
             witness["verdict"]=="CPJA7G_INDEPENDENT_ACTIVE_COMPUTE_WSI_PASS"
             and witness["profile"]==produced["profile"]==profile,
             "INDEPENDENT_VULKAN_ORACLE_DIVERGED_"+name)
        need(witness["source_frames"]==produced["frames"]==3600 and
             produced["issued"]==witness["vulkan_issues"]==7200 and
             produced["typed_ack"]==witness["vulkan_typed_ack"]==7200 and
             produced["out_of_order_ack"]==witness["reordered_typed_ack"]==3600 and
             produced["captures"]==len(witness["screenshots"])==8,
             "SOURCE_NATIVE_ACK_OR_VISUALS_NOT_QUALIFIED_"+name)
        need(witness["gpu_compute_dispatches_verified"]==21600
             and witness["gpu_queue_submissions_verified"]==3600,
             "GPU_COMPUTE_NOT_REPRODUCED_"+name)
        sensors=[json.loads(row) for row in
                 (root/"bench"/(name+".thermal.jsonl")).read_text().splitlines()]
        summary=load(root/"bench"/(name+".safety.json"))
        check_sensors(name,profile,summary,sensors)
        ordered=sorted(x["gpu_util_pct"] for x in sensors)
        util_median=statistics.median(ordered)
        records.append({
          "run":name,"profile":profile,"source_frames":3600,
          "compute_dispatches":21600,"compute_queue_submissions":3600,
          "vulkan_typed_acks":7200,"reordered_acks":3600,
          "screen_captures":8,"frame_span_seconds":witness["active_span_seconds"],
          "effective_source_present_rate_fps":round(3599/witness["active_span_seconds"],3),
          "interval_p99_us":witness["active_interval_p99_us"],
          "intervals_20_to_100ms":witness["active_intervals_20_100_ms"],
          "sensor_samples":len(sensors),
          "temp_max_c":summary["temp_max_c"],
          "whole_board_power_max_w":summary["power_max_w"],
          "gpu_util_median_pct":util_median,
          "gpu_util_max_pct":summary["gpu_util_max_pct"],
          "power_specific_to_experiment":False
        })
    return records
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",required=True,type=Path)
    ap.add_argument("--evidence",required=True,type=Path)
    a=ap.parse_args()
    data=validate(a.evidence.resolve(),a.repo.resolve())
    print("CPJA7G_INDEPENDENT_TWO_ACTIVE_GPU_RUNS_PASS",json.dumps(data))
if __name__=="__main__":main()
