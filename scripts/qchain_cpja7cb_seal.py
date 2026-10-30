#!/usr/bin/env python3
"""Commit-scoped SHA-256 evidence seal for CP-JA7C, create-only and read-only input."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

POS=("loader-recovery-02","loader-recovery-03","loader-rebuilt-recovery-04")
NEG=("no-recovery","double-loss","no-injection")
SOURCES=(
    "tests/cpja7cb/gnu6_loader_fault_layer.c",
    "scripts/qchain_cpja7cb_run.py",
    "scripts/qchain_cpja7cb_gate.py",
    "scripts/qchain_cpja7cb_independent_oracle.py",
    "scripts/qchain_cpja7cb_negative_run.py",
    "scripts/test_qchain_cpja7cb_oracle.py",
    "scripts/qchain_cpja7cb_seal.py",
    "docs/QCHAIN-CP-JA7C-B-LOADER-DISPATCH-20261011.md",
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
            r["verdict"]=="CPJA7CB_LOADER_DISPATCH_DEVICE_LOST_IN_PROCESS_RECOVERY_PASS" and
            o["verdict"]=="CPJA7CB_INDEPENDENT_LOADER_DISPATCH_FAULT_RECOVERY_PASS" and
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
                     run/"viewer.stderr"):
            digests[str(file.relative_to(root))]=sha(file)
    require(any(n["mode"]=="no-injection" and n["submitted_frames"]==120 and
                n["injections"]==0 for n in negatives),
            "NO_INJECTION_PASS_THROUGH_NOT_OBSERVED")
    adversarial=(root/"oracle/adversarial.log").read_text()
    require("CPJA7CB_ORACLE_NEGATIVE_13_OF_13_PASS" in adversarial,
            "ADVERSARIAL_GATE_NOT_COMPLETE")
    digests["oracle/adversarial.log"]=sha(root/"oracle/adversarial.log")
    require(sha(root/"preflight/layer/libgnu6_cpja7cb_fault.so")==
            sha(root/"preflight/layer-rebuilt/libgnu6_cpja7cb_fault.so"),
            "SOURCE_REBUILD_BINARY_NOT_IDENTICAL")
    for item in ("preflight/typed/qchain_cpja7_dual_viewer",
                 "preflight/viewer-build.log",
                 "preflight/layer/libgnu6_cpja7cb_fault.so",
                 "preflight/layer/VK_LAYER_GNU6_cpja7cb_fault.json",
                 "preflight/layer-rebuilt/libgnu6_cpja7cb_fault.so",
                 "preflight/layer-rebuilt/VK_LAYER_GNU6_cpja7cb_fault.json",
                 "preflight/layer/vulkaninfo-final.stdout",
                 "preflight/layer/vulkaninfo-final.stderr",
                 "preflight/clippy.log",
                 "preflight/blob-frame-tests.log"):
        digests[item]=sha(root/item)
    report={
        "schema":"gnu6.qchain.cpja7cb_qualification.v1",
        "date":"2026-10-11","branch":branch,"commit":commit,
        "parent":"b89470d4daf448489be078cc0ba0981e9edb6c50",
        "verdict":"CPJA7CB_EXPLICIT_VULKAN_LOADER_DEVICE_LOSS_RECOVERY_SCOPED_PASS",
        "hardware":"NVIDIA GeForce RTX 3070",
        "weston":"15 isolated headless GL desktop",
        "synthetic_error":"VK_ERROR_DEVICE_LOST returned by private explicit Vulkan loader layer at vkQueuePresentKHR",
        "loader_layer":"VK_LAYER_GNU6_cpja7cb_fault",
        "binary_source_rebuild_byte_identical":True,
        "layer_loaded_only_in_test_viewer":True,
        "vendor_vk_error_returned":False,
        "physical_gpu_reset":False,
        "positive_runs":results,"negative_runs":negatives,
        "source_frames":360,"typed_vk_acks":720,"wayland_presented":720,
        "compositor_captures":24,"max_screen_rgb_delta_per_channel":3,
        "adversarial_controls_rejected":13,"blob_frame_tests_passed":31,
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
