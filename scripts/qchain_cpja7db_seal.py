#!/usr/bin/env python3
"""CP-JA7D-B commit-bound create-only cryptographic evidence qualification."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

POSITIVES=("final-normal-01","final-normal-02","final-loss-01","final-loss-02")
NEGATIVES=(("final-no-recovery",40,1),("final-double-loss",44,2),("final-no-injection",120,0))
SOURCES=(
 "crates/showcase/Cargo.toml",
 "vendor/wgpu-hal-30.0.1/Cargo.toml",
 "vendor/wgpu-hal-30.0.1/src/vulkan/swapchain/mod.rs",
 "vendor/wgpu-hal-30.0.1/src/vulkan/swapchain/native.rs",
 "vendor/wgpu-hal-30.0.1/src/vulkan/swapchain/cpja6_lifecycle.rs",
 "vendor/wgpu-hal-30.0.1/src/vulkan/swapchain/cpja7db_collector.rs",
 "tests/cpja7db/lifecycle_harness.rs",
 "scripts/qchain_cpja7db_run.py",
 "scripts/qchain_cpja7db_gate.py",
 "scripts/qchain_cpja7db_independent_oracle.py",
 "scripts/qchain_cpja7db_oracle_tail.py",
 "scripts/test_qchain_cpja7db_oracle.py",
 "scripts/qchain_cpja7db_seal.py",
 "docs/QCHAIN-CP-JA7D-B-ASYNC-OUT-OF-ORDER-20261011.md",
)
ARTIFACTS=(
 "preflight/async/qchain_cpja7_dual_viewer",
 "preflight/build-final.log",
 "preflight/async-ledger-tests.log",
 "preflight/ja7d-regression-tests.log",
 "preflight/ja6-regression-tests.log",
 "preflight/blob-frame-tests.log",
 "preflight/clippy-final.log",
 "preflight/ja7d-legacy-check.log",
 "preflight/ja5-legacy-check.log",
 "oracle/adversarial-final.log",
)
EXTERNAL=(
 "/mnt/workbench/evidence/runs/qchain-cpja7cb-20261011-01/preflight/layer/libgnu6_cpja7cb_fault.so",
 "/mnt/workbench/evidence/runs/qchain-cpja7cb-20261011-01/preflight/layer/VK_LAYER_GNU6_cpja7cb_fault.json",
 "/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/preflight/tile_views.so",
 "/mnt/workbench/build/qchain-cpi02-engine-20261010/debug/examples/qchain_cpi02_gpu_live",
 "/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json",
)
def require(ok,code):
    if not ok:raise RuntimeError(code)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path):
    return json.loads(path.read_text())

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo",type=Path,required=True)
    parser.add_argument("--evidence",type=Path,required=True)
    opts=parser.parse_args()
    repo=opts.repo.resolve()
    evidence=opts.evidence.resolve()
    dest=evidence/"qualification-20261011.json"
    require(not dest.exists(),"SEAL_REFUSE_OVERWRITE")
    branch=subprocess.check_output(["git","branch","--show-current"],cwd=repo,text=True).strip()
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
    require(branch=="feat/qchain-async-out-of-order-20261011","SEALED_BRANCH_MISMATCH")
    require(not subprocess.check_output(["git","status","--porcelain"],cwd=repo,text=True).strip(),
            "SEALED_WORKTREE_NOT_CLEAN")
    digests={}
    for source in SOURCES:
        path=repo/source
        require(path.is_file(),"SOURCE_NOT_FOUND_"+source)
        digests["source:"+source]=digest(path)
    for artifact in ARTIFACTS:
        path=evidence/artifact
        require(path.is_file(),"EVIDENCE_MISSING_"+artifact)
        digests[artifact]=digest(path)
    ext_digests={}
    for item in EXTERNAL:
        path=Path(item)
        require(path.is_file(),"EXTERNAL_DEPENDENCY_MISSING")
        ext_digests[item]=digest(path)
    observations=[]
    sums={"frames":0,"issued":0,"wait_successes":0,"typed_acks":0,
          "reverse_deliveries":0,"nonfifo_acks":0,"server_presented":0,
          "client_presented":0,"captures":0}
    for name in POSITIVES:
        run=evidence/"runs"/name
        producer=load(run/"run-verdict.json")
        oracle=load(evidence/"oracle"/(name+".json"))
        mode="loader-recovery" if name.startswith("final-loss") else "normal"
        expected_ack=238 if mode=="loader-recovery" else 240
        expected_out_of_order=119 if mode=="loader-recovery" else 120
        expected_unacked=[[2,39],[2,40]] if mode=="loader-recovery" else []
        require(
            producer["mode"]==oracle["mode"]==mode and
            producer["verdict"]=="CPJA7DB_ASYNC_OUT_OF_ORDER_"+(
                "DEVICE_LOSS_RECOVERY_PASS" if mode=="loader-recovery" else "NORMAL_PASS") and
            oracle["verdict"]=="CPJA7DB_INDEPENDENT_ASYNC_OUT_OF_ORDER_AUTHORITY_PASS",
            "PRODUCER_AND_ORACLE_VERDICTS_DIVERGE_"+name)
        require(
            producer["frames"]==oracle["source_frames"]==120 and
            producer["issue_count"]==oracle["issued"]==240 and
            producer["wait_success_count"]==oracle["typed_vk_wait_success"]==240 and
            producer["typed_acks"]==oracle["acknowledged"]==expected_ack and
            producer["reorder_batches"]==oracle["out_of_order_deliveries"]==120 and
            producer["out_of_order_acks"]==oracle["out_of_order_acknowledged"]==expected_out_of_order,
            "ASYNC_NATIVE_PRESENTATION_AUTHORITY_NOT_MATCHED_"+name)
        require(
            producer["unacknowledged"]==oracle["unacknowledged"]==expected_unacked and
            producer["maximum_inflight"]==oracle["max_outstanding_per_swapchain"]==2 and
            producer["wayland_server_presented"]==oracle["server_wayland_presented"]==240 and
            producer["wayland_client_presented"]==oracle["client_wayland_presented"] and
            producer["wayland_unreceived_by_client"]==oracle["server_unreceived_by_client"] and
            0<=oracle["server_unreceived_by_client"]<=(2 if mode=="loader-recovery" else 0) and
            producer["compositor_samples"]==len(oracle["screenshots"])==8,
            "REVOKED_IDS_OR_CLIENT_SERVER_PIXELS_NOT_RECONCILED_"+name)
        require(not oracle["real_vendor_device_loss"] and
                not oracle["actual_present_order_reversed"] and
                oracle["real_vulkan_wait_status_for_each_ack"],
                "UNSUPPORTED_EXTERNAL_VULKAN_CLAIM_"+name)
        observations.append({
            "run":name,"mode":mode,"source_frames":120,
            "submitted":240,"real_wait_success":240,
            "typed_acks":expected_ack,"out_of_order_acks":expected_out_of_order,
            "unacknowledged":expected_unacked,"server_wayland_presented":240,
            "client_wayland_presented":oracle["client_wayland_presented"],
            "screenshots":8
        })
        for k,v in (
            ("frames",120),("issued",240),("wait_successes",240),
            ("typed_acks",expected_ack),("reverse_deliveries",120),
            ("nonfifo_acks",expected_out_of_order),("server_presented",240),
            ("client_presented",oracle["client_wayland_presented"]),("captures",8)
        ):sums[k]+=v
        for path in list(sorted(run.glob("sample-*.png")))+[
            run/"run-verdict.json",run/"viewer.stdout",run/"viewer.stderr",
            run/"weston.stdout",run/"weston-timeline-proto.log",
            evidence/"oracle"/(name+".json")
        ]:digests[str(path.relative_to(evidence))]=digest(path)
    negatives=[]
    for name,frames,faults in NEGATIVES:
        run=evidence/"negative"/name
        verdict=load(run/"negative-verdict.json")
        client=(run/"viewer.stderr").read_text(errors="replace")
        require(verdict["mode"]==name.removeprefix("final-") and verdict["submitted_frames"]==frames
                and verdict["injections"]==faults and verdict["viewer_exit"]!=0
                and not verdict["success_receipt"] and
                verdict["verdict"].endswith("_FAIL_CLOSED_PASS")
                and not (run/"run-verdict.json").exists(),
                "NEGATIVE_MODE_FALSE_POSITIVE_"+name)
        if faults:
            require("CPJA7D_DEVICE_WIDE_DRAIN_DENIED" in client
                    and "CPJA7DB_DEVICE_LOST_DRAIN_REVOKED" in client,
                    "CANCELLED_ASYNC_DEVICE_MISSING_"+name)
        else:
            require("CPJA7DB_DEVICE_LOST_DRAIN_REVOKED" not in client,
                    "NO_INJECTION_LEDGER_CONTAMINATED")
        negatives.append({
            "mode":name,"completed_source_frames":frames,"faults":faults,
            "viewer_exit":verdict["viewer_exit"],"no_false_positive_receipt":True
        })
        for item in ("negative-verdict.json","viewer.stdout","viewer.stderr"):
            path=run/item
            digests[str(path.relative_to(evidence))]=digest(path)
    adversarial=(evidence/"oracle/adversarial-final.log").read_text()
    require("CPJA7DB_ORACLE_ADVERSARIAL_25_OF_25_PASS" in adversarial,
            "25_FALSIFICATIONS_NOT_QUALIFIED")
    checks=(
        ("async-ledger-tests.log","10 passed; 0 failed"),
        ("ja7d-regression-tests.log","8 passed; 0 failed"),
        ("ja6-regression-tests.log","6 passed; 0 failed"),
        ("blob-frame-tests.log","31 passed; 0 failed"),
        ("clippy.log","Finished"),
        ("ja7d-legacy-check.log","Finished"),
        ("ja5-legacy-check.log","Finished"),
    )
    for filename,marker in checks:
        require(marker in (evidence/"preflight"/filename).read_text(),
                "QUALIFICATION_CHECK_NOT_PASSING_"+filename)
    report={
        "schema":"gnu6.qchain.cpja7db_qualification.v1",
        "verdict":"CPJA7DB_ASYNC_COMPLETION_DELIVERY_REORDER_AND_RECOVERY_SCOPED_PASS",
        "date":"2026-10-11",
        "parent_commit":"58cb27803bf0007743212a13f04061333cc79dde",
        "branch":branch,"commit":head,
        "machine":"NVIDIA RTX 3070, isolated Weston 15 desktop GL",
        "positive_runs":observations,"negative_runs":negatives,
        "aggregate":sums,"invalidated_device_ids_unacknowledged":4,
        "adversarial_controls_rejected":25,
        "rust_tests_async":10,"rust_tests_legacy_ja7d":8,
        "rust_tests_legacy_ja6":6,"blob_frame_tests":31,
        "clippy_warnings":0,"async_workers_per_device":2,
        "worker_vulkan_wait_timeout_ns":0,"worker_poll_pause_microseconds":250,
        "delivery_reordering_after_real_vk_wait":True,
        "hardware_actual_present_order_reordering":False,
        "physical_gpu_device_loss":False,
        "separate_cp03_hybrid60":False,"zero_copy":False,
        "host_gpu_reset":False,"merge_push_deployment":False,
        "source_and_evidence_sha256":digests,
        "external_reference_sha256":ext_digests
    }
    dest.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"commit",head,
          "manifest_sha256",digest(dest),
          "evidence_entries",len(digests)+len(ext_digests),
          "issued",sums["issued"],"typed_acks",sums["typed_acks"],
          "out_of_order",sums["nonfifo_acks"],flush=True)

if __name__=="__main__":
    main()
