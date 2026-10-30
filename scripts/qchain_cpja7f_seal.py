#!/usr/bin/env python3
"""CP-JA7F 20-minute residence: clean-commit, create-only SHA256 qualification."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from qchain_cpja7f_validate import validate,NAME,load

SOURCES=(
  "crates/showcase/Cargo.toml",
  "crates/showcase/src/bin/qchain_cpja7_dual_viewer.rs",
  "docs/QCHAIN-CP-JA7F-RESIDENT-CONTRACT-20261012.md",
  "docs/QCHAIN-CP-JA7F-RESULTS-20261012.md",
  "scripts/qchain_cpja7f_run.py",
  "scripts/qchain_cpja7f_gate.py",
  "scripts/qchain_cpja7f_safety.py",
  "scripts/qchain_cpja7f_pid_watch.py",
  "scripts/qchain_cpja7f_live_audit.py",
  "scripts/qchain_cpja7f_negatives.py",
  "scripts/qchain_cpja7f_results.py",
  "scripts/qchain_cpja7f_independent_oracle.py",
  "scripts/qchain_cpja7f_validate.py",
  "scripts/test_qchain_cpja7f_oracle.py",
  "scripts/qchain_cpja7f_seal.py",
)
EXTERNAL=(
 "/mnt/workbench/evidence/runs/qchain-cpja7cb-20261011-01/preflight/layer/libgnu6_cpja7cb_fault.so",
 "/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/preflight/tile_views.so",
 "/mnt/workbench/build/qchain-cpi02-engine-20261010/debug/examples/qchain_cpi02_gpu_live",
 "/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json"
)
def need(ok,why):
    if not ok:raise RuntimeError(why)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",required=True,type=Path)
    ap.add_argument("--evidence",required=True,type=Path)
    args=ap.parse_args()
    repo=args.repo.resolve()
    e=args.evidence.resolve()
    target=e/"qualification-20261012.json"
    need(not target.exists(),"REFUSE_OVERWRITE_SEAL")
    commit=subprocess.check_output(["git","rev-parse","HEAD"],
           cwd=repo,text=True).strip()
    branch=subprocess.check_output(["git","branch","--show-current"],
           cwd=repo,text=True).strip()
    status=subprocess.check_output(["git","status","--porcelain"],
           cwd=repo,text=True).strip()
    need(not status and branch=="feat/qchain-continuous-residency-20261012",
         "WORKTREE_UNCLEAN_OR_WRONG_BRANCH")
    original=load(e/"preflight/residency-hash-anchor.json")
    need(original["contract_sha256"]==sha(repo/SOURCES[2])
         and original["viewer_sha256"]==sha(e/"preflight/bin/qchain_cpja7_dual_viewer")
         and original["viewer_pid_witness"]==2850804
         and original["weston_pid_witness"]==2850797
         and original["interval_ms"]==4100
         and original["target_frames"]==300,
         "HISTORIC_CONTRACT_BINARY_OR_PROCESS_WITNESS_DRIFT")
    native=validate(repo,e)
    need(native["process"]["viewer_pid"]==original["viewer_pid_witness"]
         and native["process"]["weston_pid"]==original["weston_pid_witness"],
         "PROCESS_LIFETIME_IDENTITY_MISMATCH")
    need(native["sensor"]["temp_max_c"]<75 and
         native["sensor"]["power_max_w"]<180 and
         native["sensor"]["samples"]>=1150
         and native["native"]["vulkan_typed_ack"]==600
         and native["native"]["interframe_gaps_3_to_6_seconds"]>=270,
         "RESIDENT_RUNTIME_OR_SENSORS_NOT_QUALIFIED")
    preview=load(e/"runs/pilot-residency-100ms-02/run-verdict.json")
    need(preview["frames"]==300 and preview["typed_ack"]==600 and
         preview["present_interval_ms"]==100 and
         preview["minimum_20_minute_residency"] is False,
         "SHORT_PILOT_MISCLASSIFIED")
    losses=[]
    for mode,frames,injections in (
        ("no-recovery",40,1),("double-loss",44,2),("no-injection",120,0)):
        p=e/"negative"/mode/"negative-verdict.json"
        result=load(p)
        need(result["mode"]==mode and
             result["submitted_frames"]==frames and
             result["injections"]==injections and
             result["viewer_exit"]!=0 and
             not result["success_receipt"] and
             result["verdict"].endswith("_FAIL_CLOSED_PASS") and
             not (e/"negative"/mode/"run-verdict.json").exists(),
             "NEGATIVE_FALSE_POSITIVE_"+mode)
        losses.append({"mode":mode,"source_frames":frames,
                       "synthetic_faults":injections,
                       "fail_closed":True})
    adversarial=(e/"oracle/adversarial.log").read_text()
    need("CPJA7F_ADVERSARIAL_26_OF_26_PASS" in adversarial,
         "TWENTY_SIX_FALSIFICATIONS_NOT_REJECTED")
    for name,mark in (
        ("preflight/clippy.log","Finished"),
        ("preflight/legacy-async-check.log","Finished"),
        ("preflight/blob-frame-tests.log","31 passed; 0 failed")):
        need(mark in (e/name).read_text(),
             "COMPILATION_OR_TEST_NOT_PASS_"+name)
    # Failed attempts are kept as evidence, never relabeled as qualified run.
    failed={"pilot-residency-100ms":"inherited latency gate refused 300 frames",
            "resident-20min-01":"unprepared bench/ folder refused before viewer"}
    for name in failed:
        need(not (e/"runs"/name/"run-verdict.json").exists(),
             "FAILED_ATTEMPT_RELABELED")
    evidence={}
    for name in SOURCES:
        path=repo/name
        need(path.is_file(),"SOURCE_NOT_PRESENT_"+name)
        evidence["source:"+name]=sha(path)
    for dirname in ("preflight","runs","bench","telemetry","oracle","negative"):
        for path in sorted((e/dirname).rglob("*")):
            if path.is_file():
                evidence[str(path.relative_to(e))]=sha(path)
    external={}
    canonical_root=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
    reference_paths=list(EXTERNAL)+[
        str(canonical_root/f"state4-{material}-frame{frame}-dpr2.gpu-rgba.bin")
        for material in ("ceramic","gel","metal","paper") for frame in (0,1)
    ]
    for name in reference_paths:
        path=Path(name)
        need(path.is_file(),"EXTERNAL_DEPENDENCY_MISSING")
        external[name]=sha(path)
    report={
      "schema":"gnu6.qchain.cpja7f_20min_residency.v1",
      "verdict":"CPJA7F_CONTINUOUS_LOW_DUTY_WSI_RESIDENCY_SCOPED_PASS",
      "commit":commit,"branch":branch,
      "parent":"d2085e7be6a98e646b653c2493e8ce23b313f68c",
      "run":NAME,"pilot":{"name":"pilot-residency-100ms-02",
        "frames":300,"duration_gate_pass":False},
      "failed_preflights_excluded":failed,
      "viewer_pid":native["process"]["viewer_pid"],
      "weston_pid":native["process"]["weston_pid"],
      "observer_started_after_process_creation":True,
      "watcher_not_full_process_lifetime":True,
      "raw_source_frames":native["native"]["source_frames"],
      "vulkan_issued":native["native"]["vulkan_issues"],
      "vulkan_wait_success":native["native"]["vulkan_real_wait_success"],
      "vulkan_typed_acks":native["native"]["vulkan_typed_ack"],
      "deliberately_out_of_order_acks":native["native"]["reordered_typed_ack"],
      "wayland_server_presented":native["native"]["wayland_server_presented"],
      "compositor_screenshots":len(native["native"]["screenshots"]),
      "present_elapsed_us":native["native"]["residency_observed_span_us"],
      "paced_intervals":native["native"]["interframe_gaps_3_to_6_seconds"],
      "sensor_metrics":native["sensor"],
      "process_metrics":native["process"],
      "synthetic_loss_negative_controls":losses,
      "adversarial_rejections":26,"blob_frame_unit_tests":31,
      "gpu_energy_exclusively_attributable":False,
      "hardware_driver_device_loss":False,
      "continuous_high_load_test":False,
      "thermal_equilibrium_qualified":False,
      "sustained_60fps_qualified":False,
      "cp03_hybrid60":False,"production_promotion":False,
      "merge_push_deployment":False,
      "source_and_raw_evidence_sha256":evidence,
      "external_baseline_sha256":external
    }
    target.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"commit",commit,
          "SHA256",sha(target),"entries",len(evidence)+len(external),
          "residence_seconds",round(report["present_elapsed_us"]/1e6,2),
          "max_c",native["sensor"]["temp_max_c"],flush=True)
if __name__=="__main__":main()
