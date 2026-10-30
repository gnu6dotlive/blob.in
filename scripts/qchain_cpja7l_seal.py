#!/usr/bin/env python3
"""Fail-closed commit-bound SHA256 for CP-JA7L matched-binary crossover."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from qchain_cpja7l_analyze import positive,sha,load

SOURCE_FILES=(
 "docs/QCHAIN-CP-JA7L-CONTRACT-20261012.md",
 "docs/QCHAIN-CP-JA7L-MATCHED-PIPE-RESULTS-20261012.md",
 "scripts/qchain_cpja7l_guard.py",
 "scripts/qchain_cpja7l_analyze.py",
 "scripts/qchain_cpja7l_seal.py",
 "scripts/test_qchain_cpja7l_oracle.py",
 "scripts/qchain_cpja7j_stream_source.py",
 "scripts/qchain_cpja7i_run.py",
)
def need(ok,msg):
    if not ok:raise RuntimeError(msg)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--evidence",type=Path,required=True)
    args=p.parse_args()
    w=args.repo.resolve();e=args.evidence.resolve()
    target=e/"qualification-20261012.json"
    need(not target.exists(),"NO_OVERWRITE_COMMIT_BOUND_SEAL")
    sha_git=subprocess.check_output(["git","rev-parse","HEAD"],
                                    cwd=w,text=True).strip()
    branch=subprocess.check_output(["git","branch","--show-current"],
                                   cwd=w,text=True).strip()
    dirty=subprocess.check_output(["git","status","--porcelain"],
                                  cwd=w,text=True).strip()
    need(branch=="feat/qchain-matched-throughput-20261012" and not dirty,
         "GIT_WORKTREE_NOT_CLEAN")
    independent=positive(e)
    need(independent==load(e/"oracle/four-run-independent.json"),
         "ORACLE_RECALCULATED_FOUR_RUNS_DIVERGED")
    need(independent["qualified_frame_count"]==4800
         and independent["gpu_timestamps"]==86400
         and independent["vulkan_typed_ack"]==9600
         and independent["wayland_presented"]==9600
         and independent["screenshots"]==32,
         "INDEPENDENT_FOUR_E2E_WITNESS_NOT_COMPLETE")
    need("CPJA7L_ADVERSARIAL_12_OF_12_PASS" in
         (e/"oracle/adversarial.log").read_text(),
         "ADVERSARIAL_FALSE_RECEIPT_REJECTIONS_MISSING")
    for name,term in (
      ("preflight/f4-clippy.log","Finished"),
      ("preflight/blob-frame-tests.log","31 passed; 0 failed")):
        need(term in (e/name).read_text(),
             "RUST_REGRESSION_GATE_MISSING_"+name)
    pilot=e/"runs/pilot-pipe-b"
    need("pipe_bytes=1048576 canonical_cache=0" in
         (pilot/"source.stdout").read_text()
         and (pilot/"f4-copy-query.bin").stat().st_size==43200,
         "PRELIMINARY_B_PILOT_NOT_ADMITTED")
    source={}
    for relative in SOURCE_FILES:
        file=w/relative
        need(file.is_file(),"TRACKED_SOURCE_MISSING_"+relative)
        source["source:"+relative]=sha(file)
    for folder in ("preflight","bench","runs","oracle","negative"):
        for file in sorted((e/folder).rglob("*")):
            if file.is_file():
                source[str(file.relative_to(e))]=sha(file)
    external={}
    for path in (
      "/mnt/workbench/evidence/runs/qchain-cpja7k-20261012-01/qualification-20261012.json",
      "/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/preflight/tile_views.so",
      "/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json"
    ):
        file=Path(path)
        need(file.is_file(),"REFERENCE_MISSING_"+path)
        external[path]=sha(file)
    keys=set()
    for item in independent["runs"]:
        keys.add(item["gpu_query_sha256"])
    need(len(keys)==4,"IDENTICAL_GPU_QUERIES_UNEXPECTED")
    result={
      "schema":"gnu6.qchain.cpja7l_paired_pipe_host_readback.v1",
      "verdict":"CPJA7L_FOUR_MATCHED_BINARY_CROSSOVER_SCOPED_PASS",
      "commit":sha_git,"branch":branch,
      "parent":"54c2daca0fb11e40a60554458c1a6b6808529a5d",
      "native_independent_proof":independent,
      "intervention":"Linux F_SETPIPE_SZ actual 65536 vs 1048576, cache=0",
      "matched_binary_sha256":load(e/"preflight/anchor.json")["sha256"],
      "adversarial_rejections":12,"rust_blob_frame_tests":31,
      "causal_direction_consistent_in_sample":independent["effect"]["direction_consistent"],
      "statistical_significance_proven":False,
      "stable_sixty_fps":False,"cp03_hybrid60_qualified":False,
      "scanout_photons_measured":False,
      "power_per_frame_attributable":False,
      "unique_bottleneck_proven":False,
      "production_promotion":False,"merge_push_deploy":False,
      "source_and_raw_evidence_sha256":source,
      "external_baselines_sha256":external,
    }
    target.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],"commit",sha_git,"sha256",sha(target),
          "sha_entries",len(source)+len(external),flush=True)
if __name__=="__main__":main()
