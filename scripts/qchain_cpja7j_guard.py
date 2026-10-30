#!/usr/bin/env python3
"""Guarded 300-frame private Weston session. Sensors are whole-device, sampled."""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

TEMP_LIMIT=75.0
POWER_LIMIT=180.0
BASELINE_LIMIT=65.0
WALL_LIMIT_SECONDS=100.0
QUERY=("nvidia-smi","--query-gpu=temperature.gpu,power.draw,"
       "utilization.gpu,memory.used,fan.speed",
       "--format=csv,noheader,nounits")

def deny(ok,reason):
    if not ok:raise RuntimeError(reason)

def sensor():
    t=time.monotonic()
    r=subprocess.run(QUERY,capture_output=True,text=True,timeout=2.5)
    deny(r.returncode==0,"GPU_SENSOR_PROCESS_ERROR")
    lines=r.stdout.strip().splitlines()
    deny(len(lines)==1,"GPU_SENSOR_CARDINALITY_NOT_ONE")
    fields=[x.strip() for x in lines[0].split(",")]
    deny(len(fields)==5,"GPU_SENSOR_FIELDS_NOT_FIVE")
    temp,power,util,memory,fan=fields
    row={
        "monotonic_ns":time.monotonic_ns(),
        "temp_c":float(temp),"power_w":float(power),
        "gpu_util_pct":float(util),"mem_mib":float(memory),
        "fan_pct":float(fan),
        "query_duration_ms":round((time.monotonic()-t)*1000,2)
    }
    deny(0<=row["temp_c"]<=110 and 0<=row["power_w"]<=500
         and 0<=row["gpu_util_pct"]<=100
         and 0<=row["mem_mib"]<=65536
         and 0<=row["fan_pct"]<=100,"GPU_SENSOR_NUMERIC_INVALID")
    return row

def run(repo,e,name,profile,stressed,interval_ms):
    path=e/"runs"/name
    telemetry=e/"bench"/f"{name}.thermal.jsonl"
    verdict=e/"bench"/f"{name}.safety.json"
    deny(not path.exists() and not telemetry.exists() and not verdict.exists(),
         "REFUSE_OVERWRITE_RUN")
    before=sensor()
    deny(before["temp_c"]<BASELINE_LIMIT and before["temp_c"]<TEMP_LIMIT
         and before["power_w"]<POWER_LIMIT,"GPU_BASELINE_GUARD_REJECTED")
    path.mkdir()
    argv=[
        "taskset","-c","18,19",sys.executable,
        str(repo/"scripts/qchain_cpja7i_run.py"),
        "--mode","normal","--profile",profile,"--idle-ms","400","--interval-ms",str(interval_ms),"--frames","1200",
        "--engine","/mnt/workbench/evidence/runs/qchain-cpja7j-20261012-01/preflight/bin/qchain_cpja7h_timing_gpu_live",
        "--viewer",str(e/"preflight/bin/qchain_cpja7_dual_viewer"),
        "--broker",str(repo/"scripts/qchain_cpja7j_stream_source.py"),
        "--baseline","/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw",
        "--receipt","/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json",
        "--root",str(path),
        "--tile-plugin","/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/preflight/tile_views.so"
    ]
    stimulus=[
        "taskset","-c","18","stress-ng","--cpu","1",
        "--cpu-load","45","--timeout","60s","--quiet"
    ]
    started=time.monotonic()
    rows=[]
    outcome=None
    stress_started=False
    stress_cpu_observed=False
    stress=child=None
    exit_code=None
    error=None
    try:
        with telemetry.open("x") as output, (e/"bench"/f"{name}.runner.log").open("xb") as run_log:
            def append(sample):
                sample["test_name"]=name
                output.write(json.dumps(sample)+"\n")
                output.flush()
                rows.append(sample)
                deny(sample["temp_c"]<TEMP_LIMIT,
                     "GPU_TEMPERATURE_CEILING_REACHED")
                deny(sample["power_w"]<POWER_LIMIT,
                     "GPU_BOARD_POWER_CEILING_REACHED")
            append(before)
            child=subprocess.Popen(argv,stdout=run_log,stderr=subprocess.STDOUT,
                                   start_new_session=True)
            next_at=started+1
            while True:
                state=child.poll()
                elapsed=time.monotonic()-started
                if stressed and not stress_started and elapsed>=300:
                    stress=subprocess.Popen([
                        "taskset","-c","18","stress-ng","--cpu","1",
                        "--cpu-load","45","--timeout","120s","--quiet"
                    ],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                      start_new_session=True)
                    stress_started=True
                if stress_started and stress is not None and stress.poll() is None:
                    stress_cpu_observed=True
                if stress_started and elapsed>=420 and stress is not None and stress.poll() is None:
                    os.killpg(stress.pid,signal.SIGTERM)

                deny(elapsed<WALL_LIMIT_SECONDS,"SUSTAINED_RUN_WALL_TIMEOUT")
                if state is not None:
                    exit_code=state
                    append(sensor())
                    deny(state==0,"SUSTAINED_300_FRAME_RUN_FAILED")
                    break
                if time.monotonic()>=next_at:
                    sample=sensor()
                    deny(sample["monotonic_ns"]-rows[-1]["monotonic_ns"]<=3_000_000_000,
                         "GPU_SENSOR_STALE")
                    append(sample)
                    next_at+=1
                else:time.sleep(.08)
            deny(len(rows)>=15,"GPU_SENSOR_SAMPLE_COUNT_UNDER_15")
            deny(time.monotonic()-started >= (17 if interval_ms==16 else 35),"ATTRIBUTION_RUNTIME_TOO_SHORT")
            outcome="CPJA7H_GUARDED_ATTRIBUTION_PASS"
    except Exception as problem:
        error=type(problem).__name__+": "+str(problem)
        outcome="CPJA7H_GUARDED_ATTRIBUTION_HOLD"
    finally:
        if child is not None and child.poll() is None:
            # Deliver SIGINT so the runner's finally can release private Weston.
            os.killpg(child.pid,signal.SIGINT)
            try:child.wait(timeout=7)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL)
                child.wait(timeout=5)
        if stress is not None and stress.poll() is None:
            os.killpg(stress.pid,signal.SIGTERM)
            try:stress.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(stress.pid,signal.SIGKILL)
                stress.wait(timeout=5)
    summary={
        "schema":"gnu6.qchain.cpja7h_board_guard.v1",
        "run":name,"profile":profile,"stress_cpu_18":stressed,
        "runner_affinity":[18,19],
        "temperature_abort_c":TEMP_LIMIT,
        "power_abort_w":POWER_LIMIT,
        "baseline_limit_c":BASELINE_LIMIT,
        "wall_timeout_s":WALL_LIMIT_SECONDS,
        "verdict":outcome,"error":error,
        "runner_exit":exit_code,
        "samples":len(rows),"duration_s":round(time.monotonic()-started,2),
        "temp_min_c":min(x["temp_c"] for x in rows),
        "temp_max_c":max(x["temp_c"] for x in rows),
        "power_min_w":min(x["power_w"] for x in rows),
        "power_max_w":max(x["power_w"] for x in rows),
        "gpu_util_max_pct":max(x["gpu_util_pct"] for x in rows),
        "fan_max_pct":max(x["fan_pct"] for x in rows),
        "host_power_attributable_to_app":False
    }
    verdict.write_text(json.dumps(summary,indent=2)+"\n")
    deny(outcome=="CPJA7H_GUARDED_ATTRIBUTION_PASS",error or "SUSTAINED_GUARD_ABORT")
    print(outcome,name,"profile",profile,
          "samples",len(rows),"temp_max",summary["temp_max_c"],
          "power_max",summary["power_max_w"],
          "wall",summary["duration_s"],flush=True)
    return summary

def main():
    p=argparse.ArgumentParser()
    for name in ("repo","evidence"):
        p.add_argument("--"+name,required=True,type=Path)
    p.add_argument("--name",required=True)
    p.add_argument("--profile",required=True,choices=["latency","balanced","eco"])
    p.add_argument("--stress",action="store_true")
    p.add_argument("--interval-ms",type=int,required=True,choices=[16,33])
    x=p.parse_args()
    run(x.repo.resolve(),x.evidence.resolve(),x.name,x.profile,x.stress,x.interval_ms)
if __name__=="__main__":main()
