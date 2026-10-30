#!/usr/bin/env python3
"""Diagnostic bounded CPU contention: unscored in preregistered gate."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--evidence",type=Path,required=True)
    args=p.parse_args()
    repo=args.repo.resolve()
    root=args.evidence.resolve()
    require=lambda v,msg: v or (_ for _ in ()).throw(RuntimeError(msg))
    baseline=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
    receipt=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json")
    engine=Path("/mnt/workbench/build/qchain-cpi02-engine-20261010/debug/examples/qchain_cpi02_gpu_live")
    plugin=Path("/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/preflight/tile_views.so")
    summary=[]
    for profile in ("balanced","eco","latency"):
        name="pressure-"+profile
        folder=root/"runs"/name
        require(not folder.exists(),"REPEAT_PRESSURE_RUN_FORBIDDEN")
        folder.mkdir()
        command=[
          "taskset","-c","18,19",sys.executable,str(repo/"scripts/qchain_cpja7e_run.py"),
          "--mode","normal","--profile",profile,"--idle-ms","400",
          "--engine",str(engine),
          "--viewer",str(root/"preflight/bin/qchain_cpja7_dual_viewer"),
          "--broker",str(repo/"scripts/qchain_cpi02_stream_source.py"),
          "--baseline",str(baseline),"--receipt",str(receipt),
          "--root",str(folder),"--tile-plugin",str(plugin)
        ]
        load=["taskset","-c","18","stress-ng","--cpu","1",
              "--cpu-load","45","--timeout","9s","--quiet"]
        started=time.monotonic()
        with (root/"bench"/f"{name}.stress.log").open("wb") as stress_log, (
             root/"bench"/f"{name}.runner.log").open("wb") as app_log:
            stress=subprocess.Popen(load,stdout=stress_log,stderr=subprocess.STDOUT)
            try:
                time.sleep(.2)
                result=subprocess.run(command,stdout=app_log,
                                      stderr=subprocess.STDOUT,timeout=65)
            finally:
                if stress.poll() is None:
                    stress.terminate()
                try:stress.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    stress.kill()
                    stress.wait(timeout=3)
        require(result.returncode==0,f"DIAGNOSTIC_RUN_FAILED_{name}")
        with (root/"bench"/f"{name}.oracle.log").open("wb") as log:
            check=subprocess.run([
              sys.executable,str(repo/"scripts/qchain_cpja7db_independent_oracle.py"),
              "--run",str(folder),"--baseline",str(baseline),
              "--receipt",str(receipt),
              "--out",str(root/"oracle"/f"{name}.json")
            ],stdout=log,stderr=subprocess.STDOUT,timeout=20)
        require(check.returncode==0,f"DIAGNOSTIC_ORACLE_FAIL_{name}")
        from qchain_cpja7eb_benchmark import parse
        metrics=parse(folder,profile)
        summary.append({"name":name,"affinity_cpus":[18,19],
                        "stress_cpu":[18],"load_target_pct_one_core":45,
                        "wall_seconds":round(time.monotonic()-started,3),
                        **metrics})
        print("CPJA7EB_PRESSURE_DIAGNOSTIC_PASS",name,
              "p95",metrics["received_to_submit_p95_us"],
              "cpu_us",metrics["worker_cpu_us"],flush=True)
    (root/"bench/pressure-diagnostic.json").write_text(json.dumps(summary,indent=2)+"\n")
if __name__=="__main__":main()
