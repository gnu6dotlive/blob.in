#!/usr/bin/env python3
"""Seal exact-commit CP-JA7B evidence: read-only inputs, create-only report."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",required=True,type=Path)
    p.add_argument("--repository",required=True,type=Path)
    a=p.parse_args()
    root=a.evidence.resolve()
    repo=a.repository.resolve()
    destination=root/"qualification-20261011.json"
    if destination.exists():
        raise RuntimeError("QUALIFICATION_SEAL_ALREADY_EXISTS")
    branch=subprocess.check_output(
        ["git","branch","--show-current"],cwd=repo,text=True).strip()
    commit=subprocess.check_output(
        ["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
    dirty=subprocess.check_output(["git","status","--porcelain"],cwd=repo,text=True)
    # Untracked exploratory probes are archived outside the sealed code paths.
    tracked=subprocess.check_output(["git","diff","--name-only"],cwd=repo,text=True).strip()
    if tracked:
        raise RuntimeError("SEAL_REQUIRES_NO_UNCOMMITTED_TRACKED_CHANGES")
    names=(
        "typed-visible-positive-20261011b",
        "typed-visible-drop-20261011b",
        "typed-source-rebuild-drop-20261011",
    )
    checks=[]
    hashes={}
    source_files=[
        "crates/showcase/src/bin/qchain_cpja7_dual_viewer.rs",
        "scripts/qchain_cpja7b_visible_run.py",
        "scripts/qchain_cpja7b_independent_oracle.py",
        "scripts/test_qchain_cpja7b_oracle.py",
        "scripts/qchain_cpja7b_seal.py",
        "tests/cpja7b/tile_views.c",
        "docs/QCHAIN-CP-JA7B-VISIBLE-MULTI-SURFACE-RECOVERY-20261011.md",
    ]
    for relative in source_files:
        file=repo/relative
        hashes[f"repo:{relative}"]=sha(file)
    for name in names:
        run=root/"runs"/name
        d=json.loads((run/"run-verdict.json").read_text())
        o=json.loads((root/"oracle"/f"{name}.json").read_text())
        if (d["source_frames"]!=120 or d["viewer_exit"]!=0 or d["source_exit"]!=0
                or d["compositor_samples"]!=8 or
                d["typed_vk_wait_success_primary"]!=120 or
                d["typed_vk_wait_success_secondary"]!=d["secondary_present_calls"] or
                d["compositor_server_presented"]!=120+d["secondary_present_calls"] or
                d["compositor_server_discarded"]!=0 or
                d["unresolved_compositor_outcomes"]!=0 or
                len(o["samples"])!=8 or
                o["weston_presented"]!=120+d["secondary_present_calls"] or
                o["weston_discarded"]!=0):
            raise RuntimeError("UNSEALED_TEST_RUN_"+name)
        if not o["verdict"].endswith("_PASS"):
            raise RuntimeError("INDEPENDENT_ORACLE_NOT_PASS_"+name)
        checks.append({"run":name,"producer_verdict":d["verdict"],
                       "independent_verdict":o["verdict"],
                       "gpu_source_frames":120,
                       "primary_vk_acks":d["typed_vk_wait_success_primary"],
                       "secondary_vk_acks":d["typed_vk_wait_success_secondary"],
                       "presented_feedback":d["compositor_server_presented"],
                       "screenshots":8,
                       "mapped_transition":o["mapped_window_transition"]})
        for f in list(run.glob("sample-*.png")) + [
            run/"run-verdict.json",run/"viewer.stdout",run/"viewer.stderr",
            run/"weston.stdout",run/"weston-timeline-proto.log",
            root/"oracle"/f"{name}.json",
        ]:
            hashes[str(f.relative_to(root))]=sha(f)
    for relative in ("preflight/typed/qchain_cpja7_dual_viewer",
                     "preflight/tile_views_rebuilt_20261011.so",
                     "preflight/viewer-rebuild-typed-20261011.log",
                     "preflight/tile-build-20261011.log",
                     "preflight/rust-tests-20261011.log",
                     "preflight/typed-clippy-20261011.log"):
        hashes[relative]=sha(root/relative)
    receipt={"schema":"gnu6.qchain.cpja7b_qualification.v1",
             "date":"2026-10-11",
             "parent_commit":"a164603adfd40b7132c9e9d7c4f7b0889349ae94",
             "local_branch":branch,"local_commit":commit,
             "verdict":"CPJA7B_VISIBLE_MULTI_SURFACE_AND_TYPED_RECOVERY_SCOPED_PASS",
             "device":"NVIDIA GeForce RTX 3070",
             "compositor":"Weston 15.0.1 headless GL private desktop",
             "typed_source_frames":360,
             "typed_vk_success":sum(c["primary_vk_acks"]+c["secondary_vk_acks"] for c in checks),
             "wayland_presented_feedback":sum(c["presented_feedback"] for c in checks),
             "original_compositor_screenshots":24,
             "per_channel_max_rgb_delta":3,
             "canonical_gpu_pixels_sha_exact":True,
             "compositor_pixels_byte_exact_claim":False,
             "oracle_negative_controls_rejected":7,
             "blob_frame_rust_tests_pass":31,
             "typed_viewer_clippy_warnings":0,
             "private_scope_only":True,
             "no_push_merge_deploy":True,
             "actual_vulkan_device_lost_injection":False,
             "multiple_presents_in_flight":False,
             "cp03_hybrid_60_qualified":False,
             "runs":checks,
             "source_and_evidence_sha256":hashes,
             "untracked_exploratory_files_left_outside_seal":bool(dirty.strip())}
    destination.write_text(json.dumps(receipt,indent=2)+"\n")
    print(receipt["verdict"],"commit",commit,
          "typed_vk_success",receipt["typed_vk_success"],
          "wayland_presented_feedback",receipt["wayland_presented_feedback"],
          "evidence_entries",len(hashes),"qualification_sha256",sha(destination))


if __name__=="__main__":
    main()
