#!/usr/bin/env python3
"""CP-JA7E: create-only, commit-bound, minimal claims evidence seal."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path

SOURCES=(
"crates/showcase/Cargo.toml",
"crates/showcase/src/bin/qchain_cpja7_dual_viewer.rs",
"vendor/wgpu-hal-30.0.1/Cargo.toml",
"vendor/wgpu-hal-30.0.1/src/vulkan/swapchain/mod.rs",
"vendor/wgpu-hal-30.0.1/src/vulkan/swapchain/cpja7db_collector.rs",
"vendor/wgpu-hal-30.0.1/src/vulkan/swapchain/cpja7e_policy.rs",
"scripts/qchain_cpja7e_run.py",
"scripts/qchain_cpja7e_seal.py",
"docs/QCHAIN-CP-JA7E-SCHEDULER-PROFILE-20261011.md")
PROFILES=("latency","balanced","eco")
def require(b,msg):
    if not b:raise RuntimeError(msg)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text())
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--evidence",type=Path,required=True)
    a=p.parse_args()
    repo=a.repo.resolve();e=a.evidence.resolve()
    out=e/"qualification-20261011.json"
    require(not out.exists(),"REFUSE_OVERWRITE")
    branch=subprocess.check_output(["git","branch","--show-current"],cwd=repo,text=True).strip()
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
    require(branch=="feat/qchain-adaptive-async-scheduler-20261011","BRANCH_DRIFT")
    require(not subprocess.check_output(["git","status","--porcelain"],cwd=repo,text=True).strip(),"WORKTREE_DIRTY")
    digests={}
    for name in SOURCES:
        path=repo/name
        require(path.exists(),"MISSING_SOURCE_"+name)
        digests["source:"+name]=sha(path)
    table=load(e/"bench/metrics-initial.json")
    require(len(table)==6,"BENCHMARK_TABLE_RUNS")
    rows=[]
    for profile in PROFILES:
        for suffix in ("","-loss"):
            name=profile+suffix
            prod=load(e/"runs"/name/"run-verdict.json")
            independent=load(e/"oracle"/(name+".json"))
            metric=next((r for r in table if r["run"]==name),None)
            mode="loader-recovery" if suffix else "normal"
            required_acks=238 if suffix else 240
            require(metric is not None and metric["profile"]==profile and
                    metric["mode"]==mode and metric["all_idle_completed"] and
                    metric["workers"]==(4 if suffix else 2) and
                    metric["cadence_us"]=={"latency":250,"balanced":1000,"eco":4000}[profile],
                    "METRICS_INCONSISTENT_"+name)
            require(metric["wait_calls"]>=240 and metric["cpu_us"]>0
                    and metric["idle_block_us"]>0 and
                    metric["acked"]==required_acks,"METRICS_WRONG_"+name)
            require(prod["typed_acks"]==independent["acknowledged"]==required_acks
                    and prod["frames"]==independent["source_frames"]==120
                    and prod["issue_count"]==independent["issued"]==240
                    and independent["server_wayland_presented"]==240
                    and len(independent["screenshots"])==8
                    and prod["maximum_inflight"]==2
                    and prod["mode"]==independent["mode"]==mode
                    and independent["verdict"]=="CPJA7DB_INDEPENDENT_ASYNC_OUT_OF_ORDER_AUTHORITY_PASS",
                    "SOURCE_PIXEL_OR_ASYNC_GATE_FAILED_"+name)
            rows.append({"run":name,"mode":mode,"frames":120,"acks":required_acks,
                         "wait_calls":metric["wait_calls"],"thread_cpu_us":metric["cpu_us"],
                         "cadence_us":metric["cadence_us"]})
            run=e/"runs"/name
            for file in list(run.glob("sample-*.png"))+[
                run/"run-verdict.json",run/"viewer.stdout",run/"viewer.stderr",
                run/"weston.stdout",run/"weston-timeline-proto.log",
                e/"oracle"/(name+".json")]:
                require(file.exists(),"MISSING_EVIDENCE_"+name)
                digests[str(file.relative_to(e))]=sha(file)
    controls=[]
    for mode,frames,faults in (("no-recovery",40,1),("double-loss",44,2),("no-injection",120,0)):
        path=e/"negative"/mode/"negative-verdict.json"
        receipt=load(path)
        require(receipt["viewer_exit"]!=0 and receipt["submitted_frames"]==frames
                and receipt["mode"]==mode and receipt["injections"]==faults
                and not receipt["success_receipt"] and
                receipt["verdict"].endswith("_FAIL_CLOSED_PASS"),
                "FALSE_FAIL_CLOSED_"+mode)
        controls.append(mode)
        for file in ("negative-verdict.json","viewer.stdout","viewer.stderr"):
            f=e/"negative"/mode/file
            digests[str(f.relative_to(e))]=sha(f)
    for name in ("bench/metrics-initial.json","preflight/adaptive/qchain_cpja7_dual_viewer",
                 "preflight/build-2.log","preflight/clippy.log","preflight/blob-frame-tests.log"):
        f=e/name;require(f.exists(),"MISSING_ARTIFACT_"+name);digests[name]=sha(f)
    require("Finished" in (e/"preflight/clippy.log").read_text()
            and "31 passed; 0 failed" in (e/"preflight/blob-frame-tests.log").read_text(),
            "STATIC_CHECKS_NOT_PASS")
    report={"schema":"gnu6.qchain.cpja7e_scheduler.v1",
        "verdict":"CPJA7E_ADAPTIVE_IDLE_AND_BOUNDED_POLLING_SCOPED_PASS",
        "parent":"95fc63f11061c6c166408c0c3d0f8117d95e53fe",
        "branch":branch,"commit":head,
        "profiles":{"latency":250,"balanced":1000,"eco":4000},
        "positive_runs":rows,"negative_runs":controls,
        "frames":720,"vulkan_present_issued":1440,
        "typed_acks":1434,"compositor_captures":48,
        "idle_channel_blocking_qualified":True,
        "performance_statistical_qualification":False,
        "physical_gpu_device_loss":False,"cp03_hybrid60":False,
        "merge_push_deploy":False,
        "source_and_evidence_sha256":digests}
    out.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"commit",head,"sha256",sha(out),
          "entries",len(digests))
if __name__=="__main__":main()
