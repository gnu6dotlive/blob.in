#!/usr/bin/env python3
"""Seal native blob.in 2D UI lab without claiming 3D or sustained 60 FPS."""
import hashlib,json,subprocess
from pathlib import Path
from blobin_ui01_oracle import verify

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def need(ok,msg):
    if not ok:raise RuntimeError(msg)

def main():
    repo=Path(__file__).resolve().parents[1]
    evidence=Path("/mnt/workbench/evidence/runs/blobin-ui01-20261012-01")
    final=evidence/"qualification-20261012.json"
    need(not final.exists(),"DO_NOT_OVERWRITE_SEALED_QUALIFICATION")
    commit=subprocess.check_output(["git","rev-parse","HEAD"],
        cwd=repo,text=True).strip()
    branch=subprocess.check_output(["git","branch","--show-current"],
        cwd=repo,text=True).strip()
    status=subprocess.check_output(["git","status","--porcelain"],
        cwd=repo,text=True).strip()
    need(not status and branch=="feat/blobin-native-ui-motion-20261012",
         "UNQUALIFIED_WORKTREE_OR_BRANCH")
    proof=verify(evidence/"runs/native-qualified")
    recorded=json.loads((evidence/"oracle/native-qualified.json").read_text())
    need(proof==recorded and
         proof["verdict"]=="UI01_NATIVE_2D_MOTION_AND_LAYOUT_SCOPED_PASS"
         and proof["native_submitted_frames"]==180
         and proof["scripted_typed_actions"]==6
         and len(proof["sample_shas"])==4,
         "INDEPENDENT_NATIVE_UI_PROOF_FAILED")
    need("UI01_INDEPENDENT_ADVERSARIAL_7_OF_7_PASS" in
         (evidence/"tests/adversarial-qualified.log").read_text(),
         "ADVERSARIAL_FALSIFICATION_NOT_REJECTED")
    need("20 passed; 0 failed" in (evidence/"tests/ui-lib-qualified.log").read_text()
         and "Finished" in (evidence/"tests/ui-clippy-qualified.log").read_text(),
         "RUST_REGRESSION_GATE_MISSING")
    binfile=Path("/mnt/workbench/build/qchain-cpja7cb-20261011/debug/blobin_ui_lab")
    runtime=json.loads((evidence/"runs/native-qualified/smoke-verdict.json").read_text())
    need(binfile.is_file() and sha(binfile)==runtime["gpu_binary_sha256"],
         "EXECUTED_GPU_BINARY_CHANGED")
    files=(
        "crates/showcase/src/lib.rs",
        "crates/showcase/src/ui_motion.rs",
        "crates/showcase/src/ui_widgets.rs",
        "crates/showcase/src/bin/blobin_ui_lab.rs",
        "docs/BLOBIN-UI01-NATIVE-RENDER-AND-MOTION-20261012.md",
        "scripts/blobin_ui01_run.py",
        "scripts/blobin_ui01_oracle.py",
        "scripts/test_blobin_ui01_oracle.py",
        "scripts/blobin_ui01_seal.py",
    )
    digests={}
    for name in files:
        path=repo/name
        need(path.is_file(),"SOURCE_MISSING_"+name)
        digests["source:"+name]=sha(path)
    for folder in ("preflight","tests","runs","oracle"):
        for file in sorted((evidence/folder).rglob("*")):
            if file.is_file():
                digests[str(file.relative_to(evidence))]=sha(file)
    report={
        "schema":"blob.in.ui01_native_motion.v1",
        "verdict":"BLOBIN_UI01_NATIVE_MOTION_SCOPED_PASS",
        "parent":"dcdee4fc50c74f80482d437cd774ba976608c9f5",
        "commit":commit,"branch":branch,
        "interactive_native_gpu_ui_executable":True,
        "four_compositor_pixel_witnesses":True,
        "real_user_clicks_automatically_replayed":False,
        "compositor_wp_presentation_feedback_qualified":False,
        "sustained_60fps_qualified":False,
        "native_3d_implemented":False,
        "cp03_hybrid60_pass":False,
        "cp03_hybrid60_deferred":True,
        "rust_showcase_library_tests":20,
        "adversarial_rejections":7,
        "sample_and_typed_action_proof":proof,
        "binary_sha256":sha(binfile),
        "production_promotion":False,"merge_push_deploy":False,
        "source_and_raw_evidence_sha256":digests
    }
    final.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"commit",commit,"sha256",sha(final),
          "hash_entries",len(digests))

if __name__=="__main__":
    main()
