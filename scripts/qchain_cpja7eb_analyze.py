#!/usr/bin/env python3
"""Independent-of-producer benchmark summary with preregistered thresholds."""
import argparse
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

PROFILES=("latency","balanced","eco")
def require(cond,text):
    if not cond:raise RuntimeError(text)
def median(vals):return round(statistics.median(vals),3)
def analyze(root):
    plan=json.loads((root/"bench/plan.json").read_text())
    rows=json.loads((root/"bench/normal-metrics.json").read_text())
    require(len(rows)==len(plan["schedule"])==15 and plan["seed"]==20261012,
            "TRIAL_COUNT_OR_PLAN_MISMATCH")
    require([(x["round"],x["profile"],x["run"]) for x in rows] ==
            [(x["round"],x["profile"],x["name"]) for x in plan["schedule"]],
            "ORIGINAL_RANDOMIZED_ORDER_MUTATED")
    profile_group=defaultdict(list)
    for row in rows:
        profile_group[row["profile"]].append(row)
        assert row["frames"]==120 and row["worker_context_records"]==2
        assert row["idle_markers_complete"] and row["worker_idle_block_us"]>=700000
        oracle=json.loads((root/"oracle"/(row["run"]+".json")).read_text())
        assert oracle["source_frames"]==120 and oracle["acknowledged"]==240
        assert oracle["out_of_order_acknowledged"]==120
        assert oracle["server_wayland_presented"]==240 and len(oracle["screenshots"])==8
        assert oracle["verdict"]=="CPJA7DB_INDEPENDENT_ASYNC_OUT_OF_ORDER_AUTHORITY_PASS"
    require(all(len(profile_group[x])==5 for x in PROFILES),"NOT_FIVE_OF_EACH_PROFILE")
    by_round={r:{x["profile"]:x for x in rows if x["round"]==r}
              for r in range(1,6)}
    require(all(set(v)==set(PROFILES) for v in by_round.values()),"UNBALANCED_ROUNDS")
    metrics=("worker_cpu_us","worker_wait_calls","worker_voluntary_ctxt",
             "worker_nonvoluntary_ctxt","received_to_submit_p50_us",
             "received_to_submit_p95_us","received_to_submit_p99_us")
    profiles={}
    for profile,vals in profile_group.items():
        profiles[profile]={name:{
            "median":median([x[name] for x in vals]),
            "min":min(x[name] for x in vals),
            "max":max(x[name] for x in vals),
            "samples":[x[name] for x in vals],
        } for name in metrics}
    latency=profiles["latency"]
    eco=profiles["eco"]
    ratios={
        "eco_over_latency_cpu":round(eco["worker_cpu_us"]["median"]/latency["worker_cpu_us"]["median"],4),
        "eco_over_latency_wait_calls":round(eco["worker_wait_calls"]["median"]/latency["worker_wait_calls"]["median"],4),
        "eco_over_latency_p95":round(eco["received_to_submit_p95_us"]["median"]/latency["received_to_submit_p95_us"]["median"],4)
    }
    quality=all(row["latency_gate_pass"] for row in rows)
    improvement=(ratios["eco_over_latency_cpu"]<=.90 and
                 ratios["eco_over_latency_wait_calls"]<=.75 and
                 ratios["eco_over_latency_p95"]<=1.25)
    rng=random.Random(20261012)
    diffs={
        "cpu_us":[by_round[r]["eco"]["worker_cpu_us"]-
                  by_round[r]["latency"]["worker_cpu_us"] for r in range(1,6)],
        "wait_calls":[by_round[r]["eco"]["worker_wait_calls"]-
                  by_round[r]["latency"]["worker_wait_calls"] for r in range(1,6)],
        "p95_us":[by_round[r]["eco"]["received_to_submit_p95_us"]-
                  by_round[r]["latency"]["received_to_submit_p95_us"] for r in range(1,6)],
    }
    bootstrap={}
    for metric,vals in diffs.items():
        sampled=sorted(statistics.mean(rng.choices(vals,k=5)) for _ in range(3000))
        bootstrap[metric]={
           "five_paired_differences":vals,
           "observed_mean_difference":round(statistics.mean(vals),3),
           "resampled_mean_p05":round(sampled[150],3),
           "resampled_mean_p95":round(sampled[2849],3)
        }
    return {
        "schema":"gnu6.qchain.cpja7eb_statistical_analysis.v1",
        "total_runs":len(rows),"replicates_per_profile":5,
        "run_order":[x["run"] for x in rows],
        "preregistered_latency_gate_pass":quality,
        "scoped_cost_improvement_gate_pass":improvement,
        "profile_summary":profiles,
        "ratios":ratios,
        "paired_bootstrap_exploratory_not_population_ci":bootstrap,
        "limitations":"5 paired rounds on one GPU/host, uncalibrated host load; not sufficient for production performance or energy claims"
    }
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",required=True,type=Path)
    a=p.parse_args()
    root=a.evidence.resolve()
    out=root/"bench/analysis.json"
    require(not out.exists(),"REFUSE_OVERWRITE_ANALYSIS")
    report=analyze(root)
    out.write_text(json.dumps(report,indent=2)+"\n")
    print("CPJA7EB_ANALYSIS",json.dumps({k:report[k] for k in
          ("total_runs","preregistered_latency_gate_pass",
           "scoped_cost_improvement_gate_pass","ratios")}),flush=True)
if __name__=="__main__":
    main()
