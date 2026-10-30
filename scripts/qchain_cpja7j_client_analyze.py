#!/usr/bin/env python3
"""Check 4 mirrored native client-ownership runs, thermal guard and ownership."""
import argparse,hashlib,json,statistics
from pathlib import Path
from qchain_cpja7j_client_oracle import verify
PLAN=(("client-copy-a","copy"),("client-mmap-a","mmap"),
      ("client-mmap-b","mmap"),("client-copy-b","copy"))
def need(v,msg):
    if not v:raise AssertionError(msg)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def assess(e,w):
    anchor=load(e/"preflight/client-plan.json")
    need(anchor["parent"]=="267f03c63c0e6c1b7b26cf965387e35dd7e9fcd2" and
         anchor["addendum_sha256"]==sha(w/"docs/QCHAIN-CP-JA7J-CLIENT-COPY-ADDENDUM-20261012.md") and
         anchor["same_viewer_sha256"]==sha(e/"preflight/client/bin/qchain_cpja7_dual_viewer") and
         anchor["broker_sha256"]==sha(w/"scripts/qchain_cpja7j_stream_source.py") and
         anchor["engine_sha256"]==sha(e/"preflight/bin/qchain_cpja7h_timing_gpu_live") and
         anchor["runs"]==[{"name":n,"mode":m} for n,m in PLAN],
         "CLIENT_ANCHOR_OR_EXPECTED_ORDER_CHANGED")
    rows=[]
    for name,mode in PLAN:
        result=verify(e/"runs"/name,mode)
        need(result==load(e/"oracle"/(name+".json")),
             "CLIENT_OWNERSHIP_INDEPENDENT_ORACLE_MISMATCH_"+name)
        safety=load(e/"bench"/(name+".safety.json"))
        samples=[json.loads(row) for row in
            (e/"bench"/(name+".thermal.jsonl")).read_text().splitlines()]
        need(safety["verdict"]=="CPJA7H_GUARDED_ATTRIBUTION_PASS" and
             safety["runner_exit"]==0 and safety["error"] is None and
             len(samples)==safety["samples"]>=15 and
             max(r["temp_c"] for r in samples)==safety["temp_max_c"] and
             max(r["power_w"] for r in samples)==safety["power_max_w"] and
             all(r["test_name"]==name and 0<=r["temp_c"]<75 and 0<=r["power_w"]<180
                 for r in samples) and
             all(0<b["monotonic_ns"]-a["monotonic_ns"]<=3_000_000_000
                 for a,b in zip(samples,samples[1:])),
             "CLIENT_SAFETY_STREAM_INVALID_"+name)
        rows.append({**result,"temp_max_c":safety["temp_max_c"],
           "power_max_w":safety["power_max_w"],"safety_samples":len(samples)})
    return rows
def summarize(rows):
    indexed={x["run"]:x for x in rows}
    fields=("observed_submit_fps","client_hash_plus_copy_median_us",
            "client_hash_plus_copy_p99_us","source_pipe_write_median_us")
    comparison={}
    for f in fields:
        a=round(indexed["client-mmap-a"][f]-indexed["client-copy-a"][f],4)
        b=round(indexed["client-mmap-b"][f]-indexed["client-copy-b"][f],4)
        comparison[f]={"paired_differences_mmap_minus_copy":[a,b],
          "direction_consistent":a*b>0,
          "median_effect":round(statistics.median((a,b)),4)}
    return comparison
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",type=Path,required=True)
    p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    need(not a.out.exists(),"REFUSE_OVERWRITE_CLIENT_ANALYSIS")
    rows=assess(a.evidence,a.repo)
    answer={"schema":"gnu6.qchain.cpja7j_client_ownership_mirrored_analysis.v1",
      "verdict":"CPJA7J_CLIENT_FOUR_RUNS_NATIVE_PASS",
      "rows":rows,"mirrored_effects":summarize(rows),
      "actual_gpu_zero_copy":False,
      "confirmed_sustained60":False,"sample_size_per_condition":2}
    a.out.write_text(json.dumps(answer,indent=2)+"\n")
    for r in rows:
        print("CPJA7J_CLIENT_RESULT",r["run"],"fps",r["observed_submit_fps"],
           "integrity_host_us",r["client_hash_plus_copy_median_us"],flush=True)
    print("CPJA7J_CLIENT_FOUR_NATIVE_PASS",flush=True)
if __name__=="__main__":main()

