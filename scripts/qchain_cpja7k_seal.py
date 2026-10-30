#!/usr/bin/env python3
"""Independent immutable CP-JA7K evidence seal, after local Git commit."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from qchain_cpja7k_oracle import verify,need
SOURCES=(
 "docs/QCHAIN-CP-JA7K-READBACK-CONTRACT-20261012.md",
 "docs/QCHAIN-CP-JA7K-READBACK-RESULTS-20261012.md",
 "tests/cpja7k/gpu-session-readback-query.patch",
 "tests/cpja7k/qchain_cpja7k_f4_source.rs",
 "scripts/qchain_cpja7k_guard.py",
 "scripts/qchain_cpja7k_materialize.py",
 "scripts/qchain_cpja7k_oracle.py",
 "scripts/test_qchain_cpja7k_oracle.py",
 "scripts/qchain_cpja7k_seal.py",
)
def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()
def load(file):return json.loads(file.read_text())
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--repo",required=True,type=Path)
    a.add_argument("--evidence",required=True,type=Path)
    t=a.parse_args()
    w=t.repo.resolve();e=t.evidence.resolve()
    target=e/"qualification-20261012.json"
    need(not target.exists(),"FINAL_SEAL_REFUSE_OVERWRITE")
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=w,text=True).strip()
    branch=subprocess.check_output(["git","branch","--show-current"],cwd=w,text=True).strip()
    dirty=subprocess.check_output(["git","status","--porcelain"],cwd=w,text=True).strip()
    need(branch=="feat/qchain-f4-readback-timestamps-20261012" and not dirty,
         "COMMIT_OR_WORKTREE_NOT_QUALIFIED")
    anchor=load(e/"preflight/preregistered-anchor.json")
    need(anchor["parent"]=="46d217ce9f1dce6d3cc95e2eb0d2dc4a2f841e62" and
         anchor["accepted_run"]=="f4-copy-1200" and anchor["frames"]==1200 and
         anchor["aborts"]=={"temp_c":75,"power_w":180,"wall_s":100},
         "PREREGISTERED_CONTRACT_INVALID")
    for name,expected in anchor["sha256"].items():
        need(sha(Path(name))==expected,"ANCHOR_BYTE_HASH_DRIFT_"+name)
    original=Path("/mnt/workbench/evidence/runs/qchain-cpja7jc-20261012-01/preflight/f4-snapshot/F4/src/gpu_session.rs")
    copied=e/"preflight/f4-snapshot/F4/src/gpu_session.rs"
    reconstructed=e/"preflight/reproduced-f4/F4/src/gpu_session.rs"
    need(sha(original)=="b710306da940f6dd83826bf0da7921ce9739452708ff20d1e000becd54e0ddb7" and
         sha(copied)==sha(reconstructed) and
         sha(e/"preflight/f4-snapshot/F4/src/bin/qchain_cpja7k_f4_source.rs")==
         sha(w/"tests/cpja7k/qchain_cpja7k_f4_source.rs"),
         "SOURCE_ARCHIVE_RECONSTRUCTION_NOT_IDENTICAL")
    qualified=verify(e/"runs/f4-copy-1200",1200)
    recorded=load(e/"oracle/f4-copy-1200.json")
    need(qualified==recorded and
         qualified["frame_count"]==1200 and
         qualified["gpu"]["gpu_query_count"]==21600 and
         qualified["gpu"]["raw_bytes"]==172800 and
         qualified["native"]["vulkan_typed_acks"]==2400 and
         qualified["native"]["weston_presented"]==2400 and
         qualified["native"]["screenshots"]==8,
         "INDEPENDENT_F4_GPU_COPY_WSI_QUALIFICATION_FAILED")
    pilot=load(e/"oracle/pilot-300-gpu.json")
    need(pilot["frame_count"]==300 and
         pilot["gpu"]["gpu_query_count"]==5400 and
         pilot["gpu"]["raw_bytes"]==43200,
         "SOURCE_PILOT_INVALID")
    guard=load(e/"bench/f4-copy-1200.safety.json")
    samples=[json.loads(row) for row in
             (e/"bench/f4-copy-1200.thermal.jsonl").read_text().splitlines()]
    need(guard["verdict"]=="CPJA7K_GUARDED_COPY_PASS" and guard["error"] is None and
         guard["runner_exit"]==0 and guard["temperature_abort_c"]==75 and
         guard["power_abort_w"]==180 and guard["wall_timeout_s"]==100 and
         guard["host_power_attributable_to_app"] is False and
         len(samples)==guard["samples"]>=15 and
         max(x["temp_c"] for x in samples)==guard["temp_max_c"] and
         max(x["power_w"] for x in samples)==guard["power_max_w"],
         "THERMAL_GUARD_INVALID_OR_FALSIFIED")
    need(all(x["test_name"]=="f4-copy-1200" and 0<=x["temp_c"]<75 and
             0<=x["power_w"]<180 and 0<=x["gpu_util_pct"]<=100 and
             x["query_duration_ms"]<=2500 for x in samples) and
         all(0 < (b["monotonic_ns"]-a["monotonic_ns"]) <=3_000_000_000
             for a,b in zip(samples,samples[1:])),
         "THERMAL_SAMPLE_GAP_OR_CEILING")
    need("CPJA7K_ADVERSARIAL_12_OF_12_PASS" in
         (e/"oracle/adversarial.log").read_text(),"TWELVE_MUTATIONS_NOT_REJECTED")
    for file,term in (
      ("preflight/f4-clippy.log","Finished"),
      ("preflight/ja7jc-compat.log","Finished"),
      ("preflight/blob-frame-tests.log","31 passed; 0 failed")):
        need(term in (e/file).read_text(),"RUST_TESTS_NOT_QUALIFIED_"+file)
    proof={}
    for source in SOURCES:
        need((w/source).is_file(),"TRACKED_SOURCE_NOT_PRESENT_"+source)
        proof["source:"+source]=sha(w/source)
    for folder in ("preflight","runs","bench","oracle","negative"):
        for file in sorted((e/folder).rglob("*")):
            if file.is_file():proof[str(file.relative_to(e))]=sha(file)
    report={
     "schema":"gnu6.qchain.cpja7k_three_gpu_copy_timestamps.v1",
     "verdict":"CPJA7K_REAL_F4_THREE_READBACK_GPU_COPY_SCOPED_PASS",
     "commit":head,"branch":branch,
     "parent":"46d217ce9f1dce6d3cc95e2eb0d2dc4a2f841e62",
     "pilot_frames":300,"qualified_frames":1200,
     "gpu_hardware_timestamps":21600,"gpu_copy_timestamp_pairs":3600,
     "six_compute_timestamp_pairs":7200,
     "gpu_raw_bytes":172800,
     "vulkan_typed_acks":2400,"weston_presented":2400,"screenshots":8,
     "independent_oracle":recorded,
     "whole_board_thermal_samples":guard["samples"],
     "maximum_temperature_c":guard["temp_max_c"],
     "maximum_whole_board_power_w":guard["power_max_w"],
     "adversarial_rejections":12,"rust_blob_frame_tests":31,
     "readback_gpu_copy_measured":True,
     "host_mapping_and_pcie_isolated":False,
     "randomized_matched_build_ab_effect":False,
     "gpu_device_loss_driver_origin":False,
     "cp03_hybrid60_qualified":False,
     "production_promotion":False,"merge_push_deploy":False,
     "source_and_raw_evidence_sha256":proof}
    target.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"commit",head,
          "sha256",sha(target),"sha_entries",len(proof),flush=True)
if __name__=="__main__":main()
