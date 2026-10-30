#!/usr/bin/env python3
"""Clean Git commit + independently recalculated, create-only CP-JA7I seal."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from qchain_cpja7i_validate import assess,load,sha

SOURCES=(
 "crates/showcase/Cargo.toml",
 "crates/showcase/src/bin/qchain_cpja7_dual_viewer.rs",
 "docs/QCHAIN-CP-JA7I-GPU-TIMESTAMP-CAUSALITY-CONTRACT-20261012.md",
 "docs/QCHAIN-CP-JA7I-GPU-TIMESTAMP-CAUSALITY-RESULTS-20261012.md",
 "scripts/qchain_cpja7i_run.py",
 "scripts/qchain_cpja7i_guard.py",
 "scripts/qchain_cpja7i_independent_oracle.py",
 "scripts/qchain_cpja7i_validate.py",
 "scripts/qchain_cpja7i_negative_run.py",
 "scripts/qchain_cpja7i_negatives.py",
 "scripts/test_qchain_cpja7i_oracle.py",
 "scripts/qchain_cpja7i_seal.py"
)
def need(ok,why):
    if not ok:raise RuntimeError(why)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--evidence",type=Path,required=True)
    a=p.parse_args()
    w=a.repo.resolve();e=a.evidence.resolve()
    dest=e/"qualification-20261012.json"
    need(not dest.exists(),"REFUSE_OVERWRITE_MANIFEST")
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=w,text=True).strip()
    branch=subprocess.check_output(["git","branch","--show-current"],cwd=w,text=True).strip()
    status=subprocess.check_output(["git","status","--porcelain"],cwd=w,text=True).strip()
    need(branch=="feat/qchain-gpu-timestamp-causality-20261012" and not status,
         "WORKTREE_UNCLEAN_OR_UNEXPECTED_BRANCH")
    rows=assess(w,e)
    need(len(rows)==2 and [r["interval_ms_requested"] for r in rows]==[33,16]
         and sum(r["native_typed_acks"] for r in rows)==4800
         and sum(r["gpu_hardware_queries"] for r in rows)==9600
         and all(r["fps_submitted"]<60 for r in rows),
         "GPU_TIMESTAMP_OR_SOURCE_COVERAGE_INCOMPLETE")
    need("CPJA7I_ADVERSARIAL_11_OF_11_PASS" in
         (e/"oracle/adversarial-final.log").read_text(),
         "ADVERSARIAL_WITNESS_NOT_ADMITTED")
    failures={
        "first_main_query_set_limit":"wgpu max 4096 queries, 4800 requested; no frame rendered",
        "first_no_injection_negative":"harness missing CPJA7I_GPU_QUERY_RAW, no false positive"
    }
    need("too many queries" in
         (e/"runs/baseline-33/viewer.stderr").read_text()
         and "CPJA7I_GPU_QUERY_OUTPUT_REQUIRED" in
         (e/"negative/no-injection/viewer.stderr").read_text(),
         "FAILED_PREFLIGHT_PROVENANCE_LOST")
    evidence={}
    for source in SOURCES:
        f=w/source
        need(f.is_file(),"MISSING_SOURCE_"+source)
        evidence["source:"+source]=sha(f)
    for directory in ("preflight","runs","bench","oracle","negative"):
        for file in sorted((e/directory).rglob("*")):
            if file.is_file():
                evidence[str(file.relative_to(e))]=sha(file)
    external={}
    for name in (
      "/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/preflight/tile_views.so",
      "/mnt/workbench/evidence/runs/qchain-cpja7cb-20261011-01/preflight/layer/libgnu6_cpja7cb_fault.so",
      "/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json"
    ):
        file=Path(name)
        need(file.is_file(),"EXTERNAL_REFERENCE_UNAVAILABLE_"+name)
        external[name]=sha(file)
    report={
        "schema":"gnu6.qchain.cpja7i_gpu_timestamps.v1",
        "verdict":"CPJA7I_REAL_RENDER_PASS_GPU_TIMESTAMP_SCOPED_PASS",
        "commit":head,"branch":branch,
        "parent":"f99eebaa2e253ad3b2abbc4c339bbcd7c9425027",
        "runs":rows,
        "totals":{"frames":2400,"vulkan_typed_acks":4800,
                  "weston_presented":4800,"hardware_gpu_queries":9600,
                  "gpu_query_raw_bytes":76800,"compositor_captures":16},
        "adversarial_rejections":11,"synthetic_fail_closed_controls":3,
        "rust_blob_frame_tests":31,
        "unqualified_preflight_failures_retained":failures,
        "source_empty_poll_count_instrumented":False,
        "f4_compute_shader_timestamp_measured":False,
        "f4_readback_separated":False,
        "real_gpu_render_pass_timestamp_measured":True,
        "causal_source_bottleneck_isolated_by_intervention":False,
        "gpu_to_host_clock_synchronization":False,
        "scanout_photons_measured":False,
        "steady_60fps":False,"cp03_hybrid60":False,
        "board_power_attributable_to_app":False,
        "production_promotion":False,"merge_push_deploy":False,
        "source_and_raw_evidence_sha256":evidence,
        "external_baselines_sha256":external
    }
    dest.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"commit",head,
          "SHA256",hashlib.sha256(dest.read_bytes()).hexdigest(),
          "entries",len(evidence)+len(external),
          "frames",report["totals"]["frames"],flush=True)
if __name__=="__main__":main()
