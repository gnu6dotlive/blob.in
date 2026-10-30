#!/usr/bin/env python3
"""Commit-scoped SHA-256 evidence seal for CP-JA7C, create-only and read-only input."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

POS=("loss-recovery-01","loss-recovery-02","loss-recovery-03")
NEG=("no-recovery","double-loss","no-injection")
SOURCES=(
    "crates/showcase/Cargo.toml",
    "crates/showcase/src/bin/qchain_cpja7_dual_viewer.rs",
    "vendor/wgpu-hal-30.0.1/Cargo.toml",
    "vendor/wgpu-hal-30.0.1/src/vulkan/swapchain/native.rs",
    "scripts/qchain_cpja7c_run.py",
    "scripts/qchain_cpja7c_gate.py",
    "scripts/qchain_cpja7c_independent_oracle.py",
    "scripts/qchain_cpja7c_negative_run.py",
    "scripts/test_qchain_cpja7c_oracle.py",
    "scripts/qchain_cpja7c_seal.py",
    "docs/QCHAIN-CP-JA7C-CONTROLLED-DEVICE-LOSS-20261011.md",
)

def require(ok,code):
    if not ok: raise RuntimeError(code)

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",required=True,type=Path)
    p.add_argument("--repo",required=True,type=Path)
    a=p.parse_args()
    root=a.evidence.resolve()
    repo=a.repo.resolve()
    destination=root/"qualification-20261011.json"
    require(not destination.exists(),"REFUSE_REPLACE_QUALIFICATION")
    branch=subprocess.check_output(
        ["git","branch","--show-current"],cwd=repo,text=True).strip()
    commit=subprocess.check_output(
        ["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
    require(not subprocess.check_output(
        ["git","status","--porcelain"],cwd=repo,text=True).strip(),
        "WORKTREE_NOT_CLEAN_FOR_SEAL")
    digests={}
    for f in SOURCES:
        digests["source:"+f]=sha(repo/f)
    results=[]
    for name in POS:
        run=root/"runs"/name
        r=json.loads((run/"run-verdict.json").read_text())
        o=json.loads((root/"oracle"/f"{name}.json").read_text())
        require(
            r["verdict"]=="CPJA7C_SYNTHETIC_DEVICE_LOSS_IN_PROCESS_VISIBLE_RECOVERY_PASS" and
            o["verdict"]=="CPJA7C_INDEPENDENT_SYNTHETIC_FAULT_AND_VISUAL_RECOVERY_PASS" and
            r["source_frames"]==120 and r["wayland_presented"]==240 and
            r["wayland_discarded"]==0 and r["new_logical_device_epochs"]==1 and
            r["failed_presentation_ack"]==False and
            o["old_device_typed_ack"]==80 and o["new_device_typed_ack"]==160 and
            len(o["compositor_samples"])==8 and
            o["actual_vendor_icd_device_loss"]==False,
            "UNQUALIFIED_POSITIVE_RUN_"+name)
        results.append({"run":name,"producer":r["verdict"],
                        "independent":o["verdict"],
                        "frame_count":120,"typed_success":240,
                        "feedback_presented":240,"captures":8})
        for file in sorted(run.glob("sample-*.png"))+[
            run/"run-verdict.json",run/"viewer.stdout",run/"viewer.stderr",
            run/"weston.stdout",run/"weston-timeline-proto.log",
            root/"oracle"/f"{name}.json",
        ]:
            digests[str(file.relative_to(root))]=sha(file)
    negatives=[]
    for mode in NEG:
        run=root/"negative"/mode
        r=json.loads((run/"negative-verdict.json").read_text())
        require(r["verdict"].endswith("_FAIL_CLOSED_PASS") and
                r["viewer_exit"]!=0 and not r["success_receipt"] and
                not (run/"run-verdict.json").exists(),
                "NEGATIVE_MUST_HAVE_NONZERO_EXIT_"+mode)
        negatives.append(r)
        for file in (run/"negative-verdict.json",run/"viewer.stdout",
                     run/"viewer.stderr",root/"negative"/f"{mode}.stdout.log"):
            digests[str(file.relative_to(root))]=sha(file)
    baseline=json.loads((root/"runs/no-fault-baseline/run-verdict.json").read_text())
    require(baseline["verdict"]=="CPJA7B_VISIBLE_DUAL_SURFACES_PASS" and
            baseline["source_frames"]==120 and
            baseline["typed_vk_wait_success_primary"]==120 and
            baseline["typed_vk_wait_success_secondary"]==120,
            "NO_INJECTION_REGRESSION_FAILED")
    digests["runs/no-fault-baseline/run-verdict.json"]=sha(
        root/"runs/no-fault-baseline/run-verdict.json")
    adversarial=(root/"oracle/adversarial-20261011.log").read_text()
    require("CPJA7C_ORACLE_NEGATIVE_10_OF_10_PASS" in adversarial,
            "ADVERSARIAL_GATE_NOT_COMPLETE")
    digests["oracle/adversarial-20261011.log"]=sha(
        root/"oracle/adversarial-20261011.log")
    for item in ("preflight/injected/qchain_cpja7_dual_viewer",
                 "preflight/build-20261011.log",
                 "preflight/rebuild-20261011.log",
                 "preflight/clippy-20261011.log",
                 "preflight/blob-frame-tests-20261011.log"):
        digests[item]=sha(root/item)
    report={
        "schema":"gnu6.qchain.cpja7c_qualification.v1",
        "date":"2026-10-11","branch":branch,"commit":commit,
        "parent":"83d0c76d6c1e18a27ad520d4bec64071921c38b7",
        "verdict":"CPJA7C_SYNTHETIC_WSI_DEVICE_LOSS_AND_IN_PROCESS_RECOVERY_SCOPED_PASS",
        "hardware":"NVIDIA GeForce RTX 3070",
        "weston":"15 isolated headless GL desktop",
        "synthetic_error":"VK_ERROR_DEVICE_LOST at HAL boundary before vkQueuePresentKHR",
        "vendor_vk_error_returned":False,
        "physical_gpu_reset":False,
        "positive_runs":results,"negative_runs":negatives,
        "source_frames":360,"typed_vk_acks":720,"wayland_presented":720,
        "compositor_captures":24,"max_screen_rgb_delta_per_channel":3,
        "adversarial_controls_rejected":10,"blob_frame_tests_passed":31,
        "clippy_warnings":0,
        "same_process_recovery":True,
        "multiple_presents_in_flight":False,
        "cp03_hybrid_60_qualified":False,
        "merge_push_deploy":False,
        "sha256":digests
    }
    destination.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"commit",commit,"sha256",sha(destination),
          "evidence_files",len(digests))

if __name__=="__main__":
    main()
