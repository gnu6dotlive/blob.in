#!/usr/bin/env python3
"""CP-JA7G create-only, commit-bound qualification seal."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from qchain_cpja7g_validate import validate,sha,load,BASE,RECEIPT

SOURCES=(
"crates/showcase/Cargo.toml",
"crates/showcase/src/bin/qchain_cpja7_dual_viewer.rs",
"tools/qchain_cpja7g_active_gpu_live.rs",
"docs/QCHAIN-CP-JA7G-ACTIVE-GPU-CONTRACT-20261012.md",
"docs/QCHAIN-CP-JA7G-ACTIVE-GPU-RESULTS-20261012.md",
"scripts/qchain_cpja7g_stream_source.py",
"scripts/qchain_cpja7g_run.py",
"scripts/qchain_cpja7g_gate.py",
"scripts/qchain_cpja7g_guard.py",
"scripts/qchain_cpja7g_independent_oracle.py",
"scripts/qchain_cpja7g_validate.py",
"scripts/qchain_cpja7g_negatives.py",
"scripts/test_qchain_cpja7g_oracle.py",
"scripts/qchain_cpja7g_results.py",
"scripts/qchain_cpja7g_seal.py")
NEGATIVES=(("no-recovery",40,1),("double-loss",44,2),("no-injection",120,0))
def need(ok,why):
    if not ok:raise RuntimeError(why)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",required=True,type=Path)
    ap.add_argument("--evidence",required=True,type=Path)
    a=ap.parse_args()
    repo=a.repo.resolve()
    root=a.evidence.resolve()
    dest=root/"qualification-20261012.json"
    need(not dest.exists(),"REFUSE_OVERWRITE_FINAL_SEAL")
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
    branch=subprocess.check_output(["git","branch","--show-current"],cwd=repo,text=True).strip()
    dirty=subprocess.check_output(["git","status","--porcelain"],cwd=repo,text=True).strip()
    need(branch=="feat/qchain-active-gpu-soak-20261012" and not dirty,
         "GIT_UNCLEAN_OR_WRONG_BRANCH")
    anchor=load(root/"preflight/anchor.json")
    need(anchor["contract_sha256"]==sha(repo/SOURCES[3])
         and anchor["viewer_sha256"]==sha(root/"preflight/bin/qchain_cpja7_dual_viewer")
         and anchor["active_engine_sha256"]==sha(root/"preflight/bin/qchain_cpja7g_active_gpu_live"),
         "PREDECLARED_BINARIES_OR_CONTRACT_CHANGED")
    need(anchor["runs"]==[
       {"name":"active-balanced-3600","profile":"balanced","frames":3600,"stress":False},
       {"name":"active-eco-3600","profile":"eco","frames":3600,"stress":False}],
       "PREREGISTERED_RUNS_FALSIFIED")
    records=validate(root,repo)
    need(len(records)==2 and [x["profile"] for x in records]==["balanced","eco"]
         and sum(x["compute_dispatches"] for x in records)==43200
         and sum(x["vulkan_typed_acks"] for x in records)==14400
         and all(x["sensor_samples"]>=95 and x["frame_span_seconds"]>=95
                 and x["effective_source_present_rate_fps"]<60
                 for x in records),
         "POSITIVE_GPU_RENDER_OR_WSI_GATE_NOT_ADMITTED")
    original_failed=load(root/"bench/active-balanced-3600.safety.json")
    need(original_failed["verdict"]=="CPJA7G_GUARDED_ACTIVE_GPU_HOLD"
         and original_failed["runner_exit"]!=0
         and not (root/"runs/active-balanced-3600/run-verdict.json").exists()
         and "FileNotFoundError" in (root/"runs/active-balanced-3600/source.stderr").read_text(),
         "REJECTED_PREFLIGHT_RELABELED_AS_PASS")
    pilot=load(root/"runs/pilot-360/run-verdict.json")
    need(pilot["frames"]==360 and pilot["typed_ack"]==720
         and pilot["verdict"]=="CPJA7G_ACTIVE_DUAL_GPU_PASS",
         "360_FRAME_PILOT_NOT_PASS")
    negatives=[]
    for name,frames,faults in NEGATIVES:
        result=load(root/"negative"/name/"negative-verdict.json")
        need(result["mode"]==name and result["submitted_frames"]==frames
             and result["injections"]==faults and result["viewer_exit"]!=0
             and not result["success_receipt"]
             and result["verdict"].endswith("_FAIL_CLOSED_PASS")
             and not (root/"negative"/name/"run-verdict.json").exists(),
             "FALSE_POSITIVE_NEGATIVE_"+name)
        negatives.append({"name":name,"frames":frames,"faults":faults})
    need("CPJA7G_ADVERSARIAL_17_OF_17_PASS" in
         (root/"oracle/adversarial.log").read_text(),
         "ADVERSARIAL_FALSIFICATIONS_NOT_ALL_REJECTED")
    for file,token in (
        ("preflight/clippy.log","Finished"),
        ("preflight/ja7f-legacy-check.log","Finished"),
        ("preflight/blob-frame-tests.log","31 passed; 0 failed")):
        need(token in (root/file).read_text(),"TEST_NOT_COMPLETE_"+file)
    witnesses={}
    for source in SOURCES:
        p=repo/source
        need(p.is_file(),"SOURCE_MISSING_"+source)
        witnesses["source:"+source]=sha(p)
    for directory in ("preflight","bench","runs","negative","oracle"):
        for file in sorted((root/directory).rglob("*")):
            if file.is_file():
                witnesses[str(file.relative_to(root))]=sha(file)
    external={}
    for file in (
        RECEIPT,
        Path("/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/preflight/tile_views.so"),
        Path("/mnt/workbench/evidence/runs/qchain-cpja7cb-20261011-01/preflight/layer/libgnu6_cpja7cb_fault.so"),
        Path("/mnt/workbench/build/qchain-cpi02-engine-20261010/debug/examples/qchain_cpi02_gpu_live"),
        *sorted(BASE.glob("state4-*-frame*-dpr2.gpu-rgba.bin")),
        *sorted(Path("/mnt/workbench/build/qchain-cpi02-engine-20261010/debug/deps").glob("libblobin_f*_*.rlib"))
    ):
        need(file.is_file(),"EXTERNAL_DEPENDENCY_MISSING_"+str(file))
        external[str(file)]=sha(file)
    report={
        "schema":"gnu6.qchain.cpja7g_active_gpu_scoped.v1",
        "verdict":"CPJA7G_ACTIVE_COMPUTE_TWO_RUNS_SCOPED_PASS",
        "commit":head,"branch":branch,
        "parent_commit":"1bde593ab0ffcfa4cd696d79a2d644c08835a973",
        "preflight_early_failure":"active-balanced-3600 guard executable path wrong; no GPU frame was rendered",
        "accepted_runs":records,
        "pilot_frames":360,
        "live_fail_closed_controls":negatives,
        "adversarial_controls_rejected":17,
        "blob_frame_tests":31,
        "totals":{
          "accepted_gpu_frames":7200,
          "gpu_compute_dispatches":43200,
          "gpu_queue_submissions":7200,
          "vulkan_present_issued_and_typed_acks":14400,
          "out_of_order_accepted_acks":7200,
          "wayland_server_presented":14400,
          "compositor_screenshots":16},
        "device_originated_loss":False,
        "power_attributable_to_test":False,
        "gpu_saturation_qualified":False,
        "randomized_performance_study":False,
        "steady_60fps_qualified":False,
        "cp03_hybrid60":False,"zero_copy":False,
        "production_promotion":False,
        "merge_push_deploy":False,
        "source_and_evidence_sha256":witnesses,
        "external_reference_sha256":external
    }
    dest.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"commit",head,"sha256",sha(dest),
          "entries",len(witnesses)+len(external),
          "dispatches",report["totals"]["gpu_compute_dispatches"],
          "ack",report["totals"]["vulkan_present_issued_and_typed_acks"],flush=True)
if __name__=="__main__":main()
