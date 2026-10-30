#!/usr/bin/env python3
"""Reread all eight real native oracles and quantify factorial paired effects."""
import argparse,hashlib,json,statistics
from pathlib import Path
from qchain_cpja7j_independent_oracle import verify
PLAN=[("control-a",65536,0),("pipe-a",1048576,0),
      ("cache-a",65536,1),("both-a",1048576,1),
      ("both-b",1048576,1),("cache-b",65536,1),
      ("pipe-b",1048576,0),("control-b",65536,0)]
METRICS=("submit_fps","pipe_write_median_us",
         "canonical_compare_median_us","client_integrity_copy_median_us",
         "compute_readback_median_us","gpu_render_p99_ns")
def need(ok,msg):
    if not ok:raise AssertionError(msg)
def load(p):return json.loads(p.read_text())
def read(e):
    plan=load(e/"preflight/plan.json")
    need([q["name"] for q in plan["plan"]]==[n for n,_,_ in PLAN] and
         [q["pipe_bytes"] for q in plan["plan"]]==[p for _,p,_ in PLAN] and
         [q["canonical_cache"] for q in plan["plan"]]==[c for _,_,c in PLAN],
         "PREREGISTRATION_ORDER_OR_FACTORS_CHANGED")
    rows=[]
    for name,pipe,cache in PLAN:
        observed=verify(e/"runs"/name,pipe,cache)
        saved=load(e/"oracle"/(name+".json"))
        receipt=load(e/"runs"/name/"run-verdict.json")
        guard=load(e/"bench"/(name+".safety.json"))
        sensors=[json.loads(line) for line in
                 (e/"bench"/(name+".thermal.jsonl")).read_text().splitlines()]
        need(observed==saved and
             observed["gpu_compute_frames"]==receipt["frames"]==1200 and
             observed["vulkan_typed_ack"]==receipt["typed_ack"]==2400 and
             observed["weston_presented"]==2400 and
             observed["render_pass_gpu_query_count"]==4800 and
             observed["screenshots"]==8 and
             guard["verdict"]=="CPJA7H_GUARDED_ATTRIBUTION_PASS" and
             guard["runner_exit"]==0 and guard["error"] is None and
             len(sensors)==guard["samples"]>=15 and
             max(r["temp_c"] for r in sensors)==guard["temp_max_c"] and
             max(r["power_w"] for r in sensors)==guard["power_max_w"] and
             all(r["test_name"]==name and 0<=r["temp_c"]<75
                 and 0<=r["power_w"]<180
                 and 0<=r["query_duration_ms"]<=2500 for r in sensors) and
             all(0<b["monotonic_ns"]-a["monotonic_ns"]<=3_000_000_000
                 for a,b in zip(sensors,sensors[1:])),
             "INDEPENDENT_NATIVE_OR_SENSOR_GATE_FAILED_"+name)
        rows.append({**observed,"temp_max_c":guard["temp_max_c"],
            "power_max_w":guard["power_max_w"],
            "sensor_samples":len(sensors)})
    return rows
def paired(rows):
    idx={d["run"]:d for d in rows}
    def diff(a,b,metric):return round(idx[a][metric]-idx[b][metric],4)
    effects={}
    for metric in METRICS:
        pairs={
          "pipe_with_cache_off":[diff("pipe-a","control-a",metric),
                                 diff("pipe-b","control-b",metric)],
          "pipe_with_cache_on":[diff("both-a","cache-a",metric),
                                diff("both-b","cache-b",metric)],
          "cache_with_small_pipe":[diff("cache-a","control-a",metric),
                                   diff("cache-b","control-b",metric)],
          "cache_with_large_pipe":[diff("both-a","pipe-a",metric),
                                   diff("both-b","pipe-b",metric)]
        }
        effects[metric]={name:{"replicates":v,
          "replicate_sign_consistent":v[0]*v[1]>0,
          "median_difference":round(statistics.median(v),4)}
           for name,v in pairs.items()}
    return effects
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--evidence",type=Path,required=True)
    a.add_argument("--out",type=Path,required=True)
    args=a.parse_args()
    need(not args.out.exists(),"REFUSE_OVERWRITE_ANALYSIS")
    rows=read(args.evidence)
    result={"schema":"gnu6.qchain.cpja7j_factorial_mirrored_analysis.v1",
      "verdict":"CPJA7J_EIGHT_INTERVENTION_E2E_NATIVE_PASS",
      "sample_count":len(rows),"randomized":False,
      "paired_replicates_per_condition":2,
      "rows":rows,"factor_effects":paired(rows),
      "statistically_significant_performance_improvement":False,
      "sustained_60_fps":False,"gpu_power_attributable_to_app":False}
    args.out.write_text(json.dumps(result,indent=2)+"\n")
    for r in rows:
        print("CPJA7J_FACTORIAL_RESULT",r["run"],"fps",r["submit_fps"],
             "pipe_write_median_us",r["pipe_write_median_us"],
             "canonical_median_us",r["canonical_compare_median_us"],flush=True)
    print("CPJA7J_EIGHT_MIRRORED_E2E_NATIVE_PASS",flush=True)
if __name__=="__main__":main()

