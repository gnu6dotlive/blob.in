#!/usr/bin/env python3
"""Commit-bound CP-JA7E-B create-only evidence seal; no statistical overclaim."""
import argparse
import hashlib
import json
import random
import subprocess
from pathlib import Path
from qchain_cpja7eb_benchmark import parse
from qchain_cpja7eb_analyze import analyze

PROFILES=("latency","balanced","eco")
SOURCES=(
"crates/showcase/Cargo.toml",
"vendor/wgpu-hal-30.0.1/Cargo.toml",
"vendor/wgpu-hal-30.0.1/src/vulkan/swapchain/cpja7db_collector.rs",
"vendor/wgpu-hal-30.0.1/src/vulkan/swapchain/cpja7e_policy.rs",
"docs/QCHAIN-CP-JA7E-B-STATISTICAL-CONTRACT-20261012.md",
"docs/QCHAIN-CP-JA7E-B-STATISTICAL-RESULTS-20261012.md",
"scripts/qchain_cpja7eb_benchmark.py",
"scripts/qchain_cpja7eb_analyze.py",
"scripts/qchain_cpja7eb_pressure.py",
"scripts/test_qchain_cpja7eb_analysis.py",
"scripts/qchain_cpja7eb_seal.py",
)
PREFLIGHT=(
"preflight/bin/qchain_cpja7_dual_viewer",
"preflight/build.log",
"preflight/clippy.log",
"preflight/legacy-scheduler-check.log",
"preflight/blob-frame-tests.log",
)
EXTERNAL=(
"/mnt/workbench/evidence/runs/qchain-cpja7cb-20261011-01/preflight/layer/libgnu6_cpja7cb_fault.so",
"/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/preflight/tile_views.so",
"/mnt/workbench/build/qchain-cpi02-engine-20261010/debug/examples/qchain_cpi02_gpu_live",
"/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json",
)
def require(cond,why):
    if not cond:raise RuntimeError(why)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):
    return json.loads(path.read_text())
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",required=True,type=Path)
    ap.add_argument("--evidence",required=True,type=Path)
    args=ap.parse_args()
    repo=args.repo.resolve()
    root=args.evidence.resolve()
    target=root/"qualification-20261012.json"
    require(not target.exists(),"REFUSE_OVERWRITE_QUALIFICATION")
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
    branch=subprocess.check_output(["git","branch","--show-current"],cwd=repo,text=True).strip()
    status=subprocess.check_output(["git","status","--porcelain"],cwd=repo,text=True).strip()
    require(not status and branch=="feat/qchain-scheduler-statistical-20261012",
            "BRANCH_OR_WORKTREE_NOT_CLEAN")
    plan=load(root/"bench/plan.json")
    expected=[]
    rng=random.Random(20261012)
    for rn in range(1,6):
        shuffled=list(PROFILES)
        rng.shuffle(shuffled)
        for profile in shuffled:
            expected.append((rn,profile,f"r{rn:02}-{profile}"))
    require([(r["round"],r["profile"],r["name"]) for r in plan["schedule"]]==expected
            and plan["seed"]==20261012
            and plan["run_count"]==15,"UNTRUSTWORTHY_PREREGISTERED_SCHEDULE")
    require(plan["contract_sha256"]==sha(repo/SOURCES[4]) and
            plan["viewer_sha256"]==sha(root/PREFLIGHT[0]),
            "CONTRACT_OR_BINARY_CHANGED_AFTER_TRIALS")
    normal=load(root/"bench/normal-metrics.json")
    stats=load(root/"bench/analysis.json")
    require(len(normal)==15 and stats==analyze(root) and
            stats["preregistered_latency_gate_pass"]
            and stats["scoped_cost_improvement_gate_pass"],
            "PREREGISTERED_QUALITY_OR_COST_GATES_FAILED")
    for row in normal:
        run=root/"runs"/row["run"]
        actual=parse(run,row["profile"])
        for key,value in actual.items():
            require(row[key]==value,
                    f"MEASUREMENTS_DO_NOT_MATCH_RAW_LOG_{row['run']}_{key}")
        require(row["latency_gate_pass"] and row["worker_context_records"]==2
                and row["idle_markers_complete"],
                f"INVALID_WORKER_IDLE_OR_LATENCY_{row['run']}")
    runs=[x[2] for x in expected]
    loss=[]
    for profile in PROFILES:
        name="loss-"+profile
        producer=load(root/"runs"/name/"run-verdict.json")
        oracle=load(root/"oracle"/(name+".json"))
        require(producer["mode"]==oracle["mode"]=="loader-recovery" and
                producer["typed_acks"]==oracle["acknowledged"]==238 and
                producer["frames"]==oracle["source_frames"]==120 and
                producer["issue_count"]==oracle["issued"]==240 and
                oracle["unacknowledged"]==[[2,39],[2,40]] and
                len(oracle["screenshots"])==8,
                "LOADER_LOSS_RECOVERY_NOT_QUALIFIED_"+name)
        stderr=(root/"runs"/name/"viewer.stderr").read_text(errors="replace")
        require(stderr.count("CPJA7E_WORKER_METRICS")==4
                and stderr.count("CPJA7EB_WORKER_CTX")==4,
                "FOUR_WORKER_METRICS_MISSING_"+name)
        runs.append(name)
        loss.append(name)
    pressures=load(root/"bench/pressure-diagnostic.json")
    require(len(pressures)==3 and set(x["profile"] for x in pressures)==set(PROFILES),
            "PRESSURE_DIAGNOSTICS_UNBALANCED")
    for entry in pressures:
        name=entry["name"]
        require(name=="pressure-"+entry["profile"]
                and entry["affinity_cpus"]==[18,19]
                and entry["stress_cpu"]==[18]
                and entry["load_target_pct_one_core"]==45,
                "PRESSURE_PROVENANCE_MISSING_"+name)
        verified=parse(root/"runs"/name,entry["profile"])
        for key,value in verified.items():
            require(entry[key]==value,f"PRESSURE_RAW_LOG_MISMATCH_{name}_{key}")
        oracle=load(root/"oracle"/(name+".json"))
        require(oracle["source_frames"]==120 and
                oracle["acknowledged"]==240 and
                oracle["out_of_order_acknowledged"]==120 and
                len(oracle["screenshots"])==8,
                "PRESSURE_FUNCTIONAL_ORACLE_FAILED_"+name)
        runs.append(name)
    negatives=[]
    for mode,frames,faults in (("no-recovery",40,1),
                               ("double-loss",44,2),
                               ("no-injection",120,0)):
        v=load(root/"negative"/mode/"negative-verdict.json")
        require(v["mode"]==mode and v["submitted_frames"]==frames and
                v["injections"]==faults and v["viewer_exit"]!=0 and
                not v["success_receipt"]
                and v["verdict"].endswith("_FAIL_CLOSED_PASS"),
                "FALSE_POSITIVE_NEGATIVE_"+mode)
        negatives.append(mode)
    require("CPJA7EB_ADVERSARIAL_12_OF_12_PASS" in
            (root/"bench/adversarial.log").read_text(),
            "ADVERSARIAL_FALSIFICATIONS_NOT_ALL_REJECTED")
    require("Finished" in (root/"preflight/clippy.log").read_text() and
            "Finished" in (root/"preflight/legacy-scheduler-check.log").read_text() and
            "31 passed; 0 failed" in (root/"preflight/blob-frame-tests.log").read_text(),
            "COMPILATION_OR_REGRESSION_CHECK_FAILED")
    digests={}
    for source in SOURCES:
        path=repo/source
        require(path.exists(),"SOURCE_MISSING_"+source)
        digests["source:"+source]=sha(path)
    for name in PREFLIGHT:
        path=root/name
        require(path.exists(),"PREFLIGHT_MISSING_"+name)
        digests[name]=sha(path)
    for folder in ("bench","oracle"):
        for path in sorted((root/folder).glob("*")):
            if path.is_file():
                digests[str(path.relative_to(root))]=sha(path)
    for name in runs:
        path=root/"runs"/name
        files=list(path.glob("sample-*.png"))
        require(len(files)==8,"EIGHT_CAPTURES_NOT_FOUND_"+name)
        for file in sorted(files)+[
                path/"run-verdict.json",path/"viewer.stdout",
                path/"viewer.stderr",path/"weston.stdout",
                path/"weston-timeline-proto.log"]:
            require(file.is_file(),"RUN_EVIDENCE_MISSING_"+name)
            digests[str(file.relative_to(root))]=sha(file)
    for name in negatives:
        path=root/"negative"/name
        for basename in ("negative-verdict.json","viewer.stdout","viewer.stderr"):
            file=path/basename
            require(file.is_file(),"NEGATIVE_EVIDENCE_MISSING")
            digests[str(file.relative_to(root))]=sha(file)
    external={}
    for name in EXTERNAL:
        path=Path(name)
        require(path.is_file(),"EXTERNAL_REF_MISSING")
        external[name]=sha(path)
    report={
      "schema":"gnu6.qchain.cpja7eb_statistical_qualification.v1",
      "verdict":"CPJA7EB_RANDOMIZED_CONTROLLED_SCHEDULER_SCOPED_PASS",
      "parent":"05d72e501910d82e4c5b1eb4a0e4bb7e9d356808",
      "branch":branch,"commit":head,
      "preregistered_normal_runs":len(normal),
      "loader_recovery_runs":len(loss),
      "unscored_pressure_diagnostics":len(pressures),
      "live_negative_controls":len(negatives),
      "normal_source_frames":1800,"recovery_source_frames":360,
      "supplemental_pressure_source_frames":360,
      "all_positive_source_frames":2520,
      "all_positive_vulkan_issues":5040,
      "all_positive_trusted_acks":5034,
      "normal_independent_witnesses":15,
      "recovery_independent_witnesses":3,
      "diagnostic_independent_witnesses":3,
      "adversarial_statistical_falsifications":12,
      "single_workstation":"RTX 3070 / Weston headless GL",
      "performance_gate":"preregistered bounded experimental workload only",
      "statistical_improvement_gate":stats["scoped_cost_improvement_gate_pass"],
      "worker_profile_medians":stats["profile_summary"],
      "profile_ratios":stats["ratios"],
      "bootstrapped_paired_exploration":stats["paired_bootstrap_exploratory_not_population_ci"],
      "real_nvidia_driver_device_loss":False,
      "power_or_thermal_qualification":False,
      "steady_state_60fps":False,"hybrid_60":False,
      "default_profile_production_promotion":False,
      "merge_push_deploy":False,
      "source_and_raw_evidence_sha256":digests,
      "external_baseline_sha256":external
    }
    target.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"commit",head,
          "sha256",sha(target),"entries",len(digests)+len(external),
          "positive",len(runs),"negative",len(negatives))
if __name__=="__main__":main()
