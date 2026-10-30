#!/usr/bin/env python3
"""Three fail-closed controls only after the 3600-frame GPU-active guarded E2Es is complete."""
import argparse,json,subprocess,sys
from pathlib import Path

def need(ok,why):
    if not ok:raise RuntimeError(why)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",type=Path,required=True)
    ap.add_argument("--evidence",type=Path,required=True)
    a=ap.parse_args()
    w=a.repo.resolve();e=a.evidence.resolve()
    positive=e/"runs/active-eco-3600/run-verdict.json"
    status=e/"bench/active-eco-3600.safety.json"
    need(positive.exists() and status.exists(),"CONTINUOUS_RUN_NOT_FINISHED")
    verdict=json.loads(status.read_text())
    need(verdict["schema"]=="gnu6.qchain.cpja7g_board_guard.v1" and
         verdict["verdict"]=="CPJA7G_GUARDED_ACTIVE_GPU_PASS",
         "THERMAL_GUARD_NOT_PASS")
    gpu=subprocess.run(
        ["nvidia-smi","--query-gpu=temperature.gpu,power.draw",
         "--format=csv,noheader,nounits"],capture_output=True,text=True,timeout=3)
    need(gpu.returncode==0 and len(gpu.stdout.strip().splitlines())==1,
         "NEGATIVE_PREFLIGHT_SENSOR_ERROR")
    temp,power=[float(s.strip()) for s in gpu.stdout.strip().split(",")]
    need(temp<65 and power<180,"NEGATIVE_PREFLIGHT_GPU_UNSAFE")
    for mode,frames,faults in (
        ("no-recovery",40,1),("double-loss",44,2),("no-injection",120,0)):
        path=e/"negative"/mode
        need(not path.exists(),"REFUSE_DUPLICATE_NEGATIVE_"+mode)
        path.mkdir()
        command=[
            sys.executable,str(w/"scripts/qchain_cpja7cb_negative_run.py"),
            "--mode",mode,
            "--engine","/mnt/workbench/build/qchain-cpi02-engine-20261010/debug/examples/qchain_cpi02_gpu_live",
            "--viewer",str(e/"preflight/bin/qchain_cpja7_dual_viewer"),
            "--broker",str(w/"scripts/qchain_cpi02_stream_source.py"),
            "--baseline","/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw",
            "--receipt","/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json",
            "--root",str(path),
            "--tile-plugin","/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/preflight/tile_views.so",
            "--layer-dir","/mnt/workbench/evidence/runs/qchain-cpja7cb-20261011-01/preflight/layer"
        ]
        with (e/"negative"/f"{mode}.runner.log").open("xb") as log:
            result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=60)
        need(result.returncode==0,"NEGATIVE_RUN_HARNESS_FAILED_"+mode)
        proof=json.loads((path/"negative-verdict.json").read_text())
        need(proof["mode"]==mode and proof["submitted_frames"]==frames and
             proof["injections"]==faults and
             proof["viewer_exit"]!=0 and not proof["success_receipt"] and
             proof["verdict"].endswith("_FAIL_CLOSED_PASS") and
             not (path/"run-verdict.json").exists(),
             "FALSE_POSITIVE_IN_NEGATIVE_"+mode)
        print("CPJA7G_FAIL_CLOSED_PASS",mode,"frames",frames,"injections",faults,flush=True)
    print("CPJA7G_THREE_LIVE_NEGATIVES_PASS",flush=True)
if __name__=="__main__":main()
