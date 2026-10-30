#!/usr/bin/env python3
"""CP-JA7E-B preregistered randomized 5x3 E2E benchmark. No automatic retries."""
import argparse
import hashlib
import json
import random
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

PROFILES=("latency","balanced","eco")
CADENCE={"latency":250,"balanced":1000,"eco":4000}
BASE=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
RECEIPT=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json")
ENGINE=Path("/mnt/workbench/build/qchain-cpi02-engine-20261010/debug/examples/qchain_cpi02_gpu_live")
PLUGIN=Path("/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/preflight/tile_views.so")

def require(ok,why):
    if not ok: raise RuntimeError(why)

def quantile(values,q):
    values=sorted(values)
    at=(len(values)-1)*q
    before=int(at)
    frac=at-before
    return round(values[before]*(1-frac)+values[min(before+1,len(values)-1)]*frac,2)

def parse(root,profile):
    err=(root/"viewer.stderr").read_text(errors="replace")
    out=(root/"viewer.stdout").read_text(errors="replace")
    metrics=[dict(re.findall(r"(\w+)=(\S+)",line))
             for line in re.findall(r"CPJA7E_WORKER_METRICS ([^\n]+)",err)]
    contexts=[dict(re.findall(r"(\w+)=(\S+)",line))
              for line in re.findall(r"CPJA7EB_WORKER_CTX ([^\n]+)",err)]
    require(len(metrics)==len(contexts)==2,"WORKER_METRICS_MISSING")
    require(all(x.get("profile")==profile and int(x["cadence_us"])==CADENCE[profile]
                for x in metrics),"PROFILE_DRIFT")
    require({int(c["generation"]) for c in contexts}==
            {int(m["generation"]) for m in metrics},"CTX_GENERATIONS_MISMATCH")
    samples=[(int(a),int(b)) for a,b in re.findall(
        r"CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+) .*?received_to_submit_us=(\d+)",out)]
    require([s for s,_ in samples]==list(range(120)),"SOURCE_TIMESTAMPS_INVALID")
    warm=[time_us for seq,time_us in samples if seq>=5]
    require(len(warm)==115,"WARM_WINDOW_COUNT_WRONG")
    sample_us=[x for _,x in samples]
    worker_cpu=sum(int(m["cpu_us"]) for m in metrics)
    count=sum(int(m["wait_calls"]) for m in metrics)
    voluntary=sum(int(c["voluntary"]) for c in contexts)
    involuntary=sum(int(c["nonvoluntary"]) for c in contexts)
    require(all(int(m["successes"])==int(m["delivered"])==120
                and int(m["pending_abandoned"])==0 and int(m["ready_abandoned"])==0
                and int(m["idle_block_us"])>=350000 for m in metrics),
            "WORKER_FINISH_OR_IDLE_BLOCK_MISSING")
    p95=quantile(warm,.95)
    p99=quantile(warm,.99)
    return {
        "profile":profile, "cadence_us":CADENCE[profile],
        "worker_cpu_us":worker_cpu, "worker_wait_calls":count,
        "worker_timeouts":sum(int(m["timeouts"]) for m in metrics),
        "worker_idle_block_us":sum(int(m["idle_block_us"]) for m in metrics),
        "worker_voluntary_ctxt":voluntary,
        "worker_nonvoluntary_ctxt":involuntary,
        "received_to_submit_p50_us":quantile(warm,.5),
        "received_to_submit_p95_us":p95,
        "received_to_submit_p99_us":p99,
        "received_to_submit_max_us":max(sample_us),
        "warm_count":len(warm),"frames":len(samples),
        "latency_gate_pass":p95<=100000 and p99<=200000,
        "idle_markers_complete":"CPJA7E_IDLE_BEGIN duration_ms=400" in out
            and "CPJA7E_IDLE_END duration_ms=400" in out,
        "worker_context_records":len(contexts),
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--evidence",type=Path,required=True)
    a=p.parse_args()
    repo=a.repo.resolve()
    root=a.evidence.resolve()
    binary=root/"preflight/bin/qchain_cpja7_dual_viewer"
    require(binary.exists(),"BENCH_BINARY_MISSING")
    contract=repo/"docs/QCHAIN-CP-JA7E-B-STATISTICAL-CONTRACT-20261012.md"
    require(contract.exists(),"PREREGISTRATION_MISSING")
    require(not (root/"bench/plan.json").exists(),"REFUSE_OVERWRITE_PLAN")
    rng=random.Random(20261012)
    schedule=[]
    for round_num in range(1,6):
        order=list(PROFILES)
        rng.shuffle(order)
        for profile in order:
            schedule.append({"round":round_num,"profile":profile,
                             "name":f"r{round_num:02}-{profile}"})
    plan={"schema":"gnu6.cpja7eb.preregistered.v1","seed":20261012,
          "run_count":len(schedule),
          "contract_sha256":hashlib.sha256(contract.read_bytes()).hexdigest(),
          "viewer_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),
          "schedule":schedule}
    (root/"bench/plan.json").write_text(json.dumps(plan,indent=2)+"\n")
    rows=[]
    for i,trial in enumerate(schedule,1):
        name=trial["name"]
        profile=trial["profile"]
        run_dir=root/"runs"/name
        require(not run_dir.exists(),f"REPEAT_RUN_FORBIDDEN_{name}")
        run_dir.mkdir()
        cmd=[
            sys.executable,str(repo/"scripts/qchain_cpja7e_run.py"),
            "--mode","normal","--profile",profile,"--idle-ms","400",
            "--engine",str(ENGINE),"--viewer",str(binary),
            "--broker",str(repo/"scripts/qchain_cpi02_stream_source.py"),
            "--baseline",str(BASE),"--receipt",str(RECEIPT),
            "--root",str(run_dir),"--tile-plugin",str(PLUGIN),
        ]
        started=time.monotonic()
        with (root/"bench"/f"{name}.run.log").open("wb") as log:
            result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=65)
        require(result.returncode==0,f"E2E_EXIT_{name}_{result.returncode}")
        oracle=[
            sys.executable,str(repo/"scripts/qchain_cpja7db_independent_oracle.py"),
            "--run",str(run_dir),"--baseline",str(BASE),
            "--receipt",str(RECEIPT),
            "--out",str(root/"oracle"/f"{name}.json")
        ]
        with (root/"bench"/f"{name}.oracle.log").open("wb") as log:
            result=subprocess.run(oracle,stdout=log,stderr=subprocess.STDOUT,timeout=20)
        require(result.returncode==0,f"ORACLE_EXIT_{name}_{result.returncode}")
        witness=json.loads((root/"oracle"/f"{name}.json").read_text())
        require(witness["source_frames"]==120 and witness["acknowledged"]==240
                and witness["out_of_order_acknowledged"]==120
                and witness["server_wayland_presented"]==240
                and len(witness["screenshots"])==8,
                f"ORACLE_NOT_QUALIFIED_{name}")
        observed=parse(run_dir,profile)
        observed.update({"round":trial["round"],"run":name,
                         "elapsed_wall_s":round(time.monotonic()-started,3),
                         "oracle_verdict":witness["verdict"]})
        require(observed["idle_markers_complete"],"IDLE_PROBE_INCOMPLETE")
        (root/"bench"/f"{name}.metrics.json").write_text(
            json.dumps(observed,indent=2)+"\n")
        rows.append(observed)
        print(f"CPJA7EB_TRIAL_PASS {i}/15 {name} "
              f"cpu_us={observed['worker_cpu_us']} "
              f"calls={observed['worker_wait_calls']} "
              f"p95_us={observed['received_to_submit_p95_us']} "
              f"ctx={observed['worker_voluntary_ctxt']} "
              f"latency_gate={observed['latency_gate_pass']}",flush=True)
    (root/"bench/normal-metrics.json").write_text(json.dumps(rows,indent=2)+"\n")
    print("CPJA7EB_FIFTEEN_REPEATED_E2E_COMPLETE",flush=True)
if __name__=="__main__":
    main()
