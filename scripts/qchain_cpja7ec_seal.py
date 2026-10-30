#!/usr/bin/env python3
"""CP-JA7E-C create-only, commit-bound qualified mixed CPU/GPU and thermal report."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from qchain_cpja7ec_validate import evaluate,load,require,digest
from qchain_cpja7db_independent_oracle import audit as audit_loss

NORMAL_NAMES=(
    "pilot-balanced-03","c01-balanced","c02-eco",
    "c03-eco-cpu","c04-balanced-cpu","c05-balanced","c06-eco",
    "pressure-proof-eco","pressure-proof-balanced"
)
LOSS_NAMES=("loader-loss-balanced","loader-loss-eco")
NEGATIVES=(("no-recovery",40,1),("double-loss",44,2),
           ("no-injection",120,0))
EXTERNAL=(
 "/mnt/workbench/evidence/runs/qchain-cpja7cb-20261011-01/preflight/layer/libgnu6_cpja7cb_fault.so",
 "/mnt/workbench/evidence/runs/qchain-cpja7cb-20261011-01/preflight/layer/VK_LAYER_GNU6_cpja7cb_fault.json",
 "/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/preflight/tile_views.so",
 "/mnt/workbench/build/qchain-cpi02-engine-20261010/debug/examples/qchain_cpi02_gpu_live",
 "/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json"
)
SOURCES=(
 "docs/QCHAIN-CP-JA7E-C-SUSTAINED-THERMAL-CONTRACT-20261012.md",
 "docs/QCHAIN-CP-JA7E-C-SUSTAINED-THERMAL-RESULTS-20261012.md",
 "scripts/qchain_cpja7ec_run.py",
 "scripts/qchain_cpja7ec_gate.py",
 "scripts/qchain_cpja7ec_independent_oracle.py",
 "scripts/qchain_cpja7ec_safety.py",
 "scripts/qchain_cpja7ec_campaign.py",
 "scripts/qchain_cpja7ec_stress_probe.py",
 "scripts/qchain_cpja7ec_validate.py",
 "scripts/test_qchain_cpja7ec_oracle.py",
 "scripts/qchain_cpja7ec_seal.py",
)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",required=True,type=Path)
    p.add_argument("--evidence",required=True,type=Path)
    x=p.parse_args()
    repo=x.repo.resolve()
    e=x.evidence.resolve()
    target=e/"qualification-20261012.json"
    require(not target.exists(),"REFUSE_OVERWRITE_SEAL")
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
    branch=subprocess.check_output(["git","branch","--show-current"],cwd=repo,text=True).strip()
    require(branch=="feat/qchain-sustained-thermal-20261012",
            "BRANCH_DRIFT")
    require(not subprocess.check_output(
        ["git","status","--porcelain"],cwd=repo,text=True).strip(),
        "WORKTREE_NOT_CLEAN")
    positive=evaluate(repo,e)
    require(len(positive["profile_results"])==9 and
            len(positive["cpu_activity_extra_proofs"])==2,
            "QUALIFIED_NINE_THERMAL_AND_TWO_CPU_PROOFS_MISSING")
    reference=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
    cpu_receipt=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json")
    recovery=[]
    for name in LOSS_NAMES:
        run=e/"runs"/name
        fresh=audit_loss(run,reference,cpu_receipt)
        stored=load(e/"oracle"/(name+".json"))
        producer=load(run/"run-verdict.json")
        require(fresh==stored and
                fresh["verdict"]=="CPJA7DB_INDEPENDENT_ASYNC_OUT_OF_ORDER_AUTHORITY_PASS" and
                fresh["source_frames"]==120 and
                fresh["issued"]==240 and
                fresh["acknowledged"]==238 and
                fresh["unacknowledged"]==[[2,39],[2,40]] and
                len(fresh["screenshots"])==8 and
                producer["typed_acks"]==238,
                "RECOVERY_INDEPENDENT_ORACLE_DIVERGED_"+name)
        recovery.append({"run":name,"frames":120,
                         "vulkan_issued":240,"vulkan_acked":238,
                         "screenshots":8,"unacknowledged":fresh["unacknowledged"]})
    negative=[]
    for name,frames,injections in NEGATIVES:
        run=e/"negative"/name
        result=load(run/"negative-verdict.json")
        require(result["mode"]==name and
                result["viewer_exit"]!=0 and
                result["submitted_frames"]==frames and
                result["injections"]==injections and
                not result["success_receipt"] and
                result["verdict"].endswith("_FAIL_CLOSED_PASS") and
                not (run/"run-verdict.json").exists(),
                "NEGATIVE_FALSE_PASS_"+name)
        negative.append({"run":name,"frames":frames,"synthetic_faults":injections})
    require("CPJA7EC_ADVERSARIAL_20_OF_20_PASS" in
            (e/"bench/adversarial-final.log").read_text(),
            "TWENTY_ADVERSARIAL_TESTS_NOT_REJECTED")
    require("Finished" in (e/"preflight/clippy.log").read_text()
            and "Finished" in (e/"preflight/legacy-async-check.log").read_text()
            and "31 passed; 0 failed" in (e/"preflight/blob-frame-tests.log").read_text(),
            "SOURCE_BUILD_OR_RUST_TESTS_NOT_PASS")
    # Failed preflights stay attributed: they cannot be counted among positives.
    failures=[]
    for name in ("pilot-balanced","pilot-balanced-02"):
        result=load(e/"bench"/(name+".safety.json"))
        require(result["verdict"]=="CPJA7EC_SAFETY_ABORT_FAIL_CLOSED"
                and result["runner_exit"]!=0
                and not (e/"runs"/name/"run-verdict.json").exists(),
                "FAILED_PREFLIGHT_RELABELED_AS_PASS")
        failures.append({"run":name,"failure":result["error"],
                         "gpu_qualification":False})
    evidence={}
    for item in SOURCES:
        path=repo/item
        require(path.is_file(),"MISSING_SOURCE_"+item)
        evidence["source:"+item]=digest(path)
    for base in ("preflight","bench","oracle","negative","runs"):
        for path in sorted((e/base).rglob("*")):
            if path.is_file():
                evidence[str(path.relative_to(e))]=digest(path)
    external={}
    for name in EXTERNAL:
        path=Path(name)
        require(path.is_file(),"MISSING_EXTERNAL_REFERENCE")
        external[name]=digest(path)
    normal=positive["profile_results"]
    max_temp=max(x["temperature_max_c"] for x in normal)
    max_power=max(x["board_power_max_w"] for x in normal)
    min_samples=min(x["valid_samples"] for x in normal)
    report={
        "schema":"gnu6.qchain.cpja7ec_sustained_thermal.v1",
        "verdict":"CPJA7EC_BOUNDED_MULTICYCLE_THERMAL_SAFETY_SCOPED_PASS",
        "date":"2026-10-12",
        "commit":head,"branch":branch,
        "parent_commit":"f6a7ec14363e09ee80b77b1a1fde63123af727dc",
        "hardware":"NVIDIA GeForce RTX 3070 on resident Hyprland; isolated Weston 15",
        "normal_300_frame_runs":normal,
        "normal_300_frame_count":len(normal),
        "original_six_campaign_count":6,
        "supplemental_cpu18_process_witness":positive["cpu_activity_extra_proofs"],
        "cpu_activity_original_c03_c04_independently_instrumented":False,
        "loader_loss_recovery_runs":recovery,
        "fail_closed_negative_runs":negative,
        "failed_prefights_excluded":failures,
        "aggregate":{
            "source_frames":2940,
            "vulkan_issued":5880,
            "vulkan_typed_acks":5876,
            "old_device_unacknowledged_ids":4,
            "compositor_screenshots":88,
            "normal_wayland_presented":5400,
            "max_observed_gpu_temp_c":max_temp,
            "max_observed_whole_board_power_w":max_power,
            "min_thermal_sample_count":min_samples,
            "adversarial_evidence_rejections":20,
            "blob_frame_unit_tests":31
        },
        "sensor_sampling_is_discrete":True,
        "whole_device_power_not_application_attributable":True,
        "long_term_thermal_equilibrium_qualified":False,
        "continuous_multi_hour_uptime_qualified":False,
        "physical_driver_device_loss":False,
        "steady_state_60fps":False,"cp03_hybrid60":False,
        "production_default_changed":False,
        "merge_push_deploy":False,
        "source_and_raw_evidence_sha256":evidence,
        "external_refs_sha256":external
    }
    target.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"commit",head,
          "manifest_sha256",digest(target),
          "sha256_entries",len(evidence)+len(external),
          "source_frames",report["aggregate"]["source_frames"],
          "max_temp",max_temp,"max_board_power",max_power,flush=True)
if __name__=="__main__":
    main()
