#!/usr/bin/env python3
"""Create-only commit-bound SHA-256 proof for QCHAIN CP-JA7D."""
import hashlib
import json
import re
import subprocess
import argparse
from pathlib import Path

POSITIVES=("two-inflight-01","two-inflight-02",
           "loader-loss-inflight-02","loader-loss-inflight-03")
NEGATIVES=(
 ("loader-no-recovery-02","no-recovery",40,1),
 ("loader-double-loss-01","double-loss",44,2),
 ("loader-no-injection-01","no-injection",120,0),
)
SOURCES=(
 "crates/showcase/Cargo.toml",
 "vendor/wgpu-hal-30.0.1/Cargo.toml",
 "vendor/wgpu-hal-30.0.1/src/vulkan/mod.rs",
 "vendor/wgpu-hal-30.0.1/src/vulkan/adapter.rs",
 "vendor/wgpu-hal-30.0.1/src/vulkan/swapchain/native.rs",
 "vendor/wgpu-hal-30.0.1/src/vulkan/swapchain/cpja6_lifecycle.rs",
 "tests/cpja7d/lifecycle_harness.rs",
 "scripts/qchain_cpja7d_run.py",
 "scripts/qchain_cpja7d_gate.py",
 "scripts/qchain_cpja7d_independent_oracle.py",
 "scripts/qchain_cpja7d_audit_tail.py",
 "scripts/test_qchain_cpja7d_oracle.py",
 "scripts/qchain_cpja7d_seal.py",
 "docs/QCHAIN-CP-JA7D-MULTI-INFLIGHT-WITH-RECOVERY-20261011.md",
)
ARTIFACTS=(
 "preflight/inflight/qchain_cpja7_dual_viewer",
 "preflight/cpja7d-ledger-tests.log",
 "preflight/cpja6-regression-tests.log",
 "preflight/clippy-final.log",
 "preflight/legacy-feature-check.log",
 "preflight/blob-frame-tests-final.log",
 "preflight/build-device-wide.log",
 "oracle/adversarial.log",
)
EXTERNAL=(
 "/mnt/workbench/evidence/runs/qchain-cpja7cb-20261011-01/preflight/layer/libgnu6_cpja7cb_fault.so",
 "/mnt/workbench/evidence/runs/qchain-cpja7cb-20261011-01/preflight/layer/VK_LAYER_GNU6_cpja7cb_fault.json",
 "/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/preflight/tile_views.so",
 "/mnt/workbench/build/qchain-cpi02-engine-20261010/debug/examples/qchain_cpi02_gpu_live",
 "/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json",
)
def require(value,reason):
    if not value:
        raise RuntimeError(reason)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo",required=True,type=Path)
    parser.add_argument("--evidence",required=True,type=Path)
    a=parser.parse_args()
    repo=a.repo.resolve()
    e=a.evidence.resolve()
    target=e/"qualification-20261011.json"
    require(not target.exists(),"REFUSE_OVERWRITE_EVIDENCE")
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
    branch=subprocess.check_output(["git","branch","--show-current"],cwd=repo,text=True).strip()
    require(not subprocess.check_output(["git","status","--porcelain"],
                                       cwd=repo,text=True).strip(),"WORKTREE_NOT_CLEAN")
    require(branch=="feat/qchain-multi-inflight-present-20261011","BRANCH_MISMATCH")
    files={}
    for name in SOURCES:
        p=repo/name
        require(p.is_file(),"MISSING_SOURCE_"+name)
        files["source:"+name]=digest(p)
    for name in ARTIFACTS:
        p=e/name
        require(p.is_file(),"MISSING_EVIDENCE_"+name)
        files[name]=digest(p)
    externals={}
    for name in EXTERNAL:
        p=Path(name)
        require(p.is_file(),"MISSING_REFERENCED_BASELINE_"+name)
        externals[name]=digest(p)
    normal_good=0
    loss_good=0
    observations=[]
    total_issued=total_ack=total_server=total_client=total_captures=0
    for name in POSITIVES:
        run=e/"runs"/name
        prod=json.loads((run/"run-verdict.json").read_text())
        independent=json.loads((e/"oracle"/(name+".json")).read_text())
        mode="loader-recovery" if name.startswith("loader-") else "normal"
        expected_ack=237 if mode=="loader-recovery" else 240
        expected_unknown=[[2,39],[1,40],[2,40]] if mode=="loader-recovery" else []
        require(prod["mode"]==independent["mode"]==mode,
                "RUN_MODE_DIVERGED_"+name)
        require(prod["verdict"] in (
                "CPJA7D_NORMAL_TWO_IN_FLIGHT_VISIBLE_PASS",
                "CPJA7D_LOADER_LOSS_WITH_PENDING_IDS_VISIBLE_RECOVERY_PASS"
                ) and independent["verdict"]==
                "CPJA7D_INDEPENDENT_TWO_INFLIGHT_WITH_RECOVERY_PASS",
                "RUN_ORACLE_NOT_QUALIFIED_"+name)
        require(prod["frames"]==independent["source_frames"]==120 and
                prod["issued"]==independent["issued"]==240 and
                prod["typed_ack"]==independent["typed_acks"]==expected_ack and
                prod["inflight_cap"]==independent["depth_per_surface"]==2,
                "RUN_PRESENT_AUTHORITY_DIVERGED_"+name)
        require(prod["not_acknowledged"]==expected_unknown and
                independent["unacknowledged"]==sorted(expected_unknown),
                "UNACKNOWLEDGED_IDS_MISREPORTED_"+name)
        require(prod["wayland_presented"]==
                independent["server_wayland_presented"]==240 and
                independent["server_wayland_discarded"]==0 and
                prod["compositor_samples"]==len(independent["screenshots"])==8,
                "SERVER_OR_VISUAL_ORACLE_DIVERGED_"+name)
        require(0<=independent["server_delivered_but_not_client_observed"]<=
                (2 if mode=="loader-recovery" else 0),
                "CLIENT_FEEDBACK_DISCREPANCY_UNBOUNDED_"+name)
        if mode=="loader-recovery":
            loss_good+=1
        else:
            normal_good+=1
        observations.append({
            "run":name,"mode":mode,"frames":120,"issued":240,
            "acknowledged":expected_ack,
            "unacknowledged":independent["unacknowledged"],
            "server_presented":240,"client_observed":
             independent["client_received_wayland_feedback"],"captures":8,
            "producer":prod["verdict"],"independent":independent["verdict"]
        })
        total_issued+=240
        total_ack+=expected_ack
        total_server+=240
        total_client+=independent["client_received_wayland_feedback"]
        total_captures+=8
        for p in sorted(run.glob("sample-*.png"))+[
            run/"run-verdict.json",run/"viewer.stdout",run/"viewer.stderr",
            run/"weston.stdout",run/"weston-timeline-proto.log",
            e/"oracle"/(name+".json")
        ]:
            files[str(p.relative_to(e))]=digest(p)
    require(normal_good==loss_good==2,"REPLICATION_GATES_INCOMPLETE")
    negatives=[]
    for name,mode,frames,injections in NEGATIVES:
        run=e/"negative"/name
        v=json.loads((run/"negative-verdict.json").read_text())
        log=(run/"viewer.stderr").read_text(errors="replace")
        require(v["mode"]==mode and v["submitted_frames"]==frames and
                v["injections"]==injections and v["viewer_exit"]!=0 and
                not v["success_receipt"] and
                v["verdict"].endswith("_FAIL_CLOSED_PASS") and
                not (run/"run-verdict.json").exists(),
                "NEGATIVE_NOT_FAIL_CLOSED_"+name)
        if injections:
            require("CPJA7D_LOSS_INVALIDATES_UNACKED" in log and
                    "CPJA7D_DEVICE_WIDE_DRAIN_DENIED generation=2" in log,
                    "DEVICE_GLOBAL_FENCE_MISSING_IN_NEGATIVE_"+name)
        else:
            require("CPJA7D_LOSS_INVALIDATES_UNACKED" not in log,
                    "UNEXPECTED_LOSS_IN_NO_FAULT_NEGATIVE")
        negatives.append({
            "run":name,"mode":mode,"viewer_exit":v["viewer_exit"],
            "completed_frames":frames,"synthetic_faults":injections,
            "no_positive_receipt":True
        })
        for name2 in ("negative-verdict.json","viewer.stdout","viewer.stderr"):
            files[str((run/name2).relative_to(e))]=digest(run/name2)
    adversarial=(e/"oracle/adversarial.log").read_text()
    require("CPJA7D_ORACLE_ADVERSARIAL_19_OF_19_PASS" in adversarial,
            "19_INDEPENDENT_FALSIFICATIONS_NOT_REJECTED")
    require("8 passed; 0 failed" in (e/"preflight/cpja7d-ledger-tests.log").read_text() and
            "6 passed; 0 failed" in (e/"preflight/cpja6-regression-tests.log").read_text() and
            "31 passed; 0 failed" in (e/"preflight/blob-frame-tests-final.log").read_text() and
            "Finished" in (e/"preflight/clippy-final.log").read_text() and
            "Finished" in (e/"preflight/legacy-feature-check.log").read_text(),
            "RUST_OR_CLIPPY_GATE_NOT_QUALIFIED")
    report={
       "schema":"gnu6.qchain.cpja7d_qualification.v1",
       "verdict":"CPJA7D_BOUNDED_TWO_INFLIGHT_WITH_DEVICE_WIDE_RECOVERY_SCOPED_PASS",
       "date":"2026-10-11","parent":"1a586ef77f3ab69755c79adeacf4187910854892",
       "branch":branch,"commit":head,
       "hardware":"NVIDIA RTX 3070","compositor":"isolated Weston 15 headless GL",
       "max_outstanding_per_swapchain":2,"separate_swapchains":2,
       "positive_runs":observations,"negative_runs":negatives,
       "source_frames":480,
       "vulkan_presentations_issued":total_issued,
       "vulkan_typed_acks":total_ack,
       "poisoned_ids_left_unacknowledged":total_issued-total_ack,
       "wayland_server_presented":total_server,
       "wayland_client_observed":total_client,
       "wayland_client_missing_due_to_device_teardown":total_server-total_client,
       "screenshots":total_captures,
       "adversarial_corruptions_rejected":19,
       "cpja7d_ledger_tests":8,"cpja6_regression_tests":6,
       "blob_frame_tests":31,"clippy_warnings":0,
       "bounded_fifo_retirement":True,
       "out_of_order_completion_accepted":False,
       "actual_driver_device_lost":False,"physical_gpu_reset":False,
       "cp03_hybrid_60_qualified":False,"zero_copy":False,
       "merge_push_deploy":False,
       "source_and_evidence_sha256":files,
       "external_reference_sha256":externals
    }
    target.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"commit",head,
          "manifest_sha256",digest(target),
          "qualified_hash_entries",len(files)+len(externals),
          "issued",total_issued,"typed_ack",total_ack,
          "screenshots",total_captures,flush=True)

if __name__=="__main__":
    main()
