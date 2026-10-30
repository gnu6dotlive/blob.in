#!/usr/bin/env python3
"""Commit-pinned immutable raw evidence seal, rechecking 12 native E2E oracles."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from qchain_cpja7j_analyze import read as factor_read,paired
from qchain_cpja7j_client_analyze import assess as client_read,summarize
SOURCE_REL=(
 "crates/showcase/Cargo.toml",
 "crates/showcase/src/bin/qchain_cpja7_dual_viewer.rs",
 "docs/QCHAIN-CP-JA7J-BACKPRESSURE-CONTRACT-20261012.md",
 "docs/QCHAIN-CP-JA7J-CLIENT-COPY-ADDENDUM-20261012.md",
 "docs/QCHAIN-CP-JA7J-BACKPRESSURE-RESULTS-20261012.md",
 "scripts/qchain_cpja7j_stream_source.py",
 "scripts/qchain_cpja7j_guard.py",
 "scripts/qchain_cpja7j_client_guard.py",
 "scripts/qchain_cpja7j_independent_oracle.py",
 "scripts/qchain_cpja7j_analyze.py",
 "scripts/qchain_cpja7j_client_oracle.py",
 "scripts/qchain_cpja7j_client_analyze.py",
 "scripts/test_qchain_cpja7j_oracle.py",
 "scripts/test_qchain_cpja7j_client_oracle.py",
 "scripts/qchain_cpja7j_seal.py")
def need(ok,msg):
    if not ok:raise RuntimeError(msg)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text())
def run(command,cwd):
    return subprocess.check_output(command,cwd=cwd,text=True).strip()
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo",type=Path,required=True)
    parser.add_argument("--evidence",type=Path,required=True)
    a=parser.parse_args();w=a.repo.resolve();e=a.evidence.resolve()
    dest=e/"qualification-20261012.json"
    need(not dest.exists(),"REFUSE_OVERWRITE_SEAL")
    head=run(["git","rev-parse","HEAD"],w)
    need(run(["git","branch","--show-current"],w)=="feat/qchain-transport-backpressure-20261012"
         and not run(["git","status","--porcelain"],w),
         "GIT_NOT_CLEAN_OR_WRONG_BRANCH")
    factor_anchor=load(e/"preflight/plan.json")
    client_anchor=load(e/"preflight/client-plan.json")
    need(factor_anchor["parent"]=="267f03c63c0e6c1b7b26cf965387e35dd7e9fcd2"
         and factor_anchor["contract_sha256"]==sha(w/SOURCE_REL[2])
         and factor_anchor["viewer_sha256"]==sha(e/"preflight/bin/qchain_cpja7_dual_viewer")
         and factor_anchor["engine_sha256"]==sha(e/"preflight/bin/qchain_cpja7h_timing_gpu_live")
         and factor_anchor["broker_sha256"]==sha(w/SOURCE_REL[5])
         and client_anchor["addendum_sha256"]==sha(w/SOURCE_REL[3])
         and client_anchor["same_viewer_sha256"]==sha(e/"preflight/client/bin/qchain_cpja7_dual_viewer")
         and client_anchor["broker_sha256"]==sha(w/SOURCE_REL[5])
         and client_anchor["engine_sha256"]==factor_anchor["engine_sha256"],
         "PREREGISTERED_CONTRACT_OR_BINARIES_CHANGED")
    factor=factor_read(e)
    client=client_read(e,w)
    need(len(factor)==8 and len(client)==4
         and all(x["gpu_compute_frames"]==1200 and
                 x["canonical_full_byte_equality_checks"]==1200 and
                 x["vulkan_typed_ack"]==2400 and
                 x["weston_presented"]==2400 and
                 x["render_pass_gpu_query_count"]==4800 and
                 x["screenshots"]==8 for x in factor),
         "NATIVE_FACTORIAL_EVIDENCE_NOT_ADMITTED")
    need(all(x["frames"]==1200 and
             x["vulkan_typed_acks"]==2400 and
             x["gpu_timestamps"]==4800 and
             x["screen_captures"]==8 and
             x["cpu_sha256_remains_required"] for x in client),
         "CLIENT_OWNERSHIP_VALIDITY_FAILED")
    need("CPJA7J_ADVERSARIAL_12_OF_12_PASS" in
         (e/"oracle/adversarial.log").read_text() and
         "CPJA7J_CLIENT_ADVERSARIAL_8_OF_8_PASS" in
         (e/"oracle/client-adversarial.log").read_text() and
         "CPJA7J_CLIENT_THREE_NEGATIVES_FAIL_CLOSED_PASS" in
         (e/"negative/client-live-negatives.log").read_text(),
         "FAIL_CLOSED_OR_MUTATION_GATES_MISSING")
    for name,frames,faults in (("no-recovery",40,1),
                              ("double-loss",44,2),("no-injection",120,0)):
        proof=load(e/"negative"/("client-"+name)/"negative-verdict.json")
        need(proof["mode"]==name and proof["submitted_frames"]==frames and
             proof["injections"]==faults and proof["viewer_exit"]!=0 and
             proof["success_receipt"] is False and
             proof["verdict"].endswith("_FAIL_CLOSED_PASS") and
             not (e/"negative"/("client-"+name)/"run-verdict.json").exists(),
             "CLIENT_SYNTHETIC_DEVICE_LOSS_FALSE_PASS_"+name)
    for file,marker in (("preflight/client-clippy.log","Finished"),
                        ("preflight/ja7i-compat.log","Finished"),
                        ("preflight/blob-frame-tests.log","31 passed; 0 failed")):
        need(marker in (e/file).read_text(),"RUST_GATE_NOT_QUALIFIED_"+file)
    original=Path("/mnt/workbench/workspaces/gnu.in.labs/.worktrees/in-gnu6-qchain-cpf-persistent-20261010")
    need(original.is_dir() and
         run(["git","rev-parse","HEAD"],original)=="5132cf59b3842e27dcacf89bfe7060e807706e90",
         "F4_SOURCE_COMMIT_NOT_FOUND")
    gpu_session=original/"experiments/blobin-next-01/F4/src/gpu_session.rs"
    need(gpu_session.is_file() and
         "timestamp_writes: None" in gpu_session.read_text() and
         "gpu_session::PersistentSession" not in gpu_session.read_text(),
         "F4_SOURCE_NOT_IDENTICAL_TO_PREINSTRUMENTED_COPY")
    f4_sha=sha(gpu_session)
    source={}
    for name in SOURCE_REL:
        file=w/name
        need(file.is_file(),"SOURCE_FILE_MISSING_"+name)
        source["source:"+name]=sha(file)
    for d in ("preflight","bench","runs","oracle","negative"):
        for file in sorted((e/d).rglob("*")):
            if file.is_file():source[str(file.relative_to(e))]=sha(file)
    for file in (
      gpu_session,
      Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json"),
      Path("/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/preflight/tile_views.so"),
      Path("/mnt/workbench/evidence/runs/qchain-cpja7cb-20261011-01/preflight/layer/libgnu6_cpja7cb_fault.so")
    ):
        need(file.is_file(),"EXTERNAL_PROVENANCE_FILE_MISSING")
        source["external:"+str(file)]=sha(file)
    result={
        "schema":"gnu6.qchain.cpja7j_factorial_client_ownership_scoped.v1",
        "verdict":"CPJA7J_TRANSPORT_AND_CLIENT_CONTROLLED_E2E_SCOPED_PASS",
        "commit":head,"parent":"267f03c63c0e6c1b7b26cf965387e35dd7e9fcd2",
        "factorial_mirrored_runs":factor,
        "factorial_paired_effects":paired(factor),
        "client_mirrored_runs":client,
        "client_mirrored_effects":summarize(client),
        "totals":{"runs":12,"gpu_compute_frames":14400,
                  "typed_vulkan_ack":28800,"weston_presented":28800,
                  "gpu_timestamps":57600,"compositor_captures":96},
        "independent_adversarial_rejections":20,
        "client_live_fail_closed_controls":3,
        "rust_blob_frame_tests":31,
        "f4_real_source_commit":"5132cf59b3842e27dcacf89bfe7060e807706e90",
        "f4_gpu_session_source_sha256":f4_sha,
        "f4_source_mutated":False,
        "f4_compute_kernel_gpu_timestamps_measured":False,
        "fully_attributable_gpu_energy":False,
        "steady_60fps":False,"cp03_hybrid60":False,
        "randomized_trials":False,
        "mmap_copy_elision_promoted":False,
        "pipe_size_promoted_production":False,
        "merge_push_deploy":False,
        "source_and_evidence_sha256":source
    }
    dest.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],"commit",head,
          "SHA256",sha(dest),"hash_entries",len(source),
          "frames",result["totals"]["gpu_compute_frames"],flush=True)
if __name__=="__main__":main()

