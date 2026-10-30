#!/usr/bin/env python3
"""Fixed-order CP-JA7E-C six separate guarded 300-frame WSI cycles."""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

SCHEDULE=(
 ("c01-balanced","balanced",False),
 ("c02-eco","eco",False),
 ("c03-eco-cpu","eco",True),
 ("c04-balanced-cpu","balanced",True),
 ("c05-balanced","balanced",False),
 ("c06-eco","eco",False),
)
def need(ok,why):
    if not ok:raise RuntimeError(why)
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--evidence",type=Path,required=True)
    a=p.parse_args()
    repo=a.repo.resolve()
    e=a.evidence.resolve()
    contract=repo/"docs/QCHAIN-CP-JA7E-C-SUSTAINED-THERMAL-CONTRACT-20261012.md"
    binary=e/"preflight/bin/qchain_cpja7_dual_viewer"
    pilot=e/"runs/pilot-balanced-03/run-verdict.json"
    need(pilot.is_file() and binary.is_file() and contract.is_file(),
         "PILOT_CONTRACT_OR_BINARY_NOT_PRESENT")
    need(not (e/"bench/plan.json").exists(),"REFUSE_OVERWRITE_STRESS_PLAN")
    plan={
        "schema":"gnu6.qchain.cpja7ec_campaign.v1",
        "parent_commit":"f6a7ec14363e09ee80b77b1a1fde63123af727dc",
        "preregistered_contract_sha256":digest(contract),
        "viewer_binary_sha256":digest(binary),
        "safety_temp_abort_c":75,"safety_power_abort_w":180,
        "cpu_affinity":[18,19],"cpu_stress_core":18,
        "stress_target_percent":45,"source_frames_per_run":300,
        "plan":[{"index":i+1,"name":name,"profile":profile,"stress":stress}
                for i,(name,profile,stress) in enumerate(SCHEDULE)]
    }
    (e/"bench/plan.json").write_text(json.dumps(plan,indent=2)+"\n")
    for i,(name,profile,stressed) in enumerate(SCHEDULE,1):
        cmd=[
            sys.executable,str(repo/"scripts/qchain_cpja7ec_safety.py"),
            "--repo",str(repo),"--evidence",str(e),"--name",name,
            "--profile",profile]
        if stressed:cmd+=["--stress"]
        started=time.monotonic()
        with (e/"bench"/f"{name}.campaign.log").open("xb") as log:
            result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=73)
        need(result.returncode==0,f"SAFETY_RUN_ABORT_{name}")
        with (e/"bench"/f"{name}.oracle.log").open("xb") as log:
            result=subprocess.run([
                sys.executable,str(repo/"scripts/qchain_cpja7ec_independent_oracle.py"),
                "--run",str(e/"runs"/name),
                "--baseline","/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw",
                "--receipt","/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json",
                "--out",str(e/"oracle"/(name+".json"))
            ],stdout=log,stderr=subprocess.STDOUT,timeout=20)
        need(result.returncode==0,f"ORACLE_NOT_QUALIFIED_{name}")
        verdict=json.loads((e/"runs"/name/"run-verdict.json").read_text())
        independent=json.loads((e/"oracle"/(name+".json")).read_text())
        safety=json.loads((e/"bench"/(name+".safety.json")).read_text())
        need(verdict["frames"]==independent["source_frames"]==300
             and verdict["typed_ack"]==independent["vulkan_typed_ack"]==600
             and len(independent["screenshots"])==8
             and safety["verdict"]=="CPJA7EC_SAFETY_BOUNDED_RUN_PASS",
             f"RESULTS_CONTRADICTED_{name}")
        print("CPJA7EC_CYCLE_PASS",i,"/",len(SCHEDULE),name,
              "temperature_max",safety["temp_max_c"],
              "board_power_max",safety["power_max_w"],
              "elapsed",round(time.monotonic()-started,2),flush=True)
    print("CPJA7EC_SIX_SEPARATE_SUSTAINED_CYCLES_PASS",flush=True)
if __name__=="__main__":main()
