#!/usr/bin/env python3
"""CP-H2: independent archival builds, real GPU reruns, IPC restarts and bounded telemetry.

No Wayland focus changes, production writes, or GPU-claim promotion.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import psutil

def need(ok, message):
    if not ok: raise RuntimeError(message)
def sha(b): return hashlib.sha256(b).hexdigest()
def file_sha(p): return sha(p.read_bytes())
def shell_run(args, logfile, *, timeout=45, env=None):
    start=time.monotonic()
    with logfile.open("wb") as log:
        result=subprocess.run(args, stdout=log, stderr=subprocess.STDOUT,
                              timeout=timeout, env=env, check=False)
    need(result.returncode==0,"COMMAND_FAILED "+logfile.name+
         " "+str(result.returncode))
    return round(time.monotonic()-start,4)

def compute(engine, out, log, *, env=None, timeout=75):
    start=time.monotonic()
    with log.open("wb") as writer:
        proc=subprocess.Popen([str(engine),str(out)],stdout=writer,
            stderr=subprocess.STDOUT,env=env)
        observed=[]
        deadline=start+timeout
        while proc.poll() is None:
            if time.monotonic()>deadline:
                proc.kill();proc.wait();raise RuntimeError("GPU_COMPUTE_TIMEOUT")
            try: observed.append(psutil.Process(proc.pid).memory_info().rss)
            except psutil.NoSuchProcess: pass
            time.sleep(0.025)
        result=proc.wait()
    need(result==0,"GPU_COMPUTE_FAILED "+str(result))
    output=log.read_text()
    need("QCHAIN_CP_F_PERSISTENT_SESSION_PASS states=5 materials=4 frames=40" in output,
         "GPU_COMPUTE_RECEIPT_MISSING")
    return {"seconds":round(time.monotonic()-start,4),
        "peak_process_rss_bytes_sampled":max(observed) if observed else None,
        "memory_sample_period_seconds":0.025,
        "process_exit":result,"compute_log_sha256":file_sha(log)}

def validate_artifacts(produced, baseline):
    before={f.name:f for f in baseline.iterdir() if f.is_file()}
    after={f.name:f for f in produced.iterdir() if f.is_file()}
    need(before.keys()==after.keys(),"FULL_GPU_ARTIFACT_SET_MISMATCH")
    for name,original in before.items():
        need(file_sha(after[name])==file_sha(original),
             "GPU_OUTPUT_REGRESSION "+name)
    rgba=[n for n in before if n.endswith(".gpu-rgba.bin")]
    need(len(before)==52 and len(rgba)==40,"GPU_ARTIFACT_COUNT_INVALID")
    stats=(produced/"session-stats.tsv").read_text().splitlines()
    need(len(stats)==2 and stats[1].strip()=="1\t3\t5\t40",
         "PERSISTENT_SESSION_REUSE_MISMATCH")
    return {"files_exact":len(before),"rgba_exact":len(rgba),
            "source_frame_sha256":[file_sha(produced/f"state{i}-ceramic-frame0-dpr2.gpu-rgba.bin")
             for i in range(5)]}
def fail_gpu_then_restore(engine,root):
    fault=root/"fault-gpu-unavailable"
    fault.mkdir()
    log=root/"fault-gpu-unavailable.log"
    env=dict(os.environ)
    env["VK_DRIVER_FILES"]="/nonexistent-qchain-h2-vulkan-icd.json"
    started=time.monotonic()
    with log.open("wb") as writer:
        p=subprocess.run([str(engine),str(fault)],stdout=writer,
              stderr=subprocess.STDOUT,timeout=15,env=env,check=False)
    need(p.returncode!=0,"UNAVAILABLE_GPU_SILENTLY_FELL_BACK")
    need(not any(fault.iterdir()),"UNAVAILABLE_GPU_LEFT_FALSE_EVIDENCE")
    return {"exit_code":p.returncode,"duration_seconds":
       round(time.monotonic()-started,4),"gpu_fallback":False,
       "log_sha256":file_sha(log)}

def run_cycle(index, args, root):
    day=root/f"cycle-{index:02}"
    day.mkdir()
    raw=day/"raw";raw.mkdir()
    times=compute(args.engine,raw,day/"compute.log",timeout=args.timeout)
    artifacts=validate_artifacts(raw,args.reference)
    manifest=day/"gpu-source-manifest.json"
    elapsed=shell_run([sys.executable,str(args.manifest_builder),
       str(raw),str(args.cpu_raw),str(args.cpu_receipt),
       str(day/"compute.log"),str(manifest)],
       day/"manifest-build.log",timeout=15)
    source=json.loads(manifest.read_text())
    need(source["compute_run_log_sha256"]==file_sha(day/"compute.log"),
         "MANIFEST_NOT_BOUND_TO_THIS_GPU_COMPUTE")
    need(len(source["stages"])==5,"MANIFEST_SCENE_COUNT")
    for stage,item in enumerate(source["stages"]):
        need(item["gpu_rgba_sha256"]==artifacts["source_frame_sha256"][stage],
             "MANIFEST_GPU_PIXEL_IDENTITY_DRIFT")
    recovery_dir=day/"restarts";recovery_dir.mkdir()
    recovery_json=day/"restart-verdict.json"
    # AF_UNIX sun_path is short (typically 108 bytes); keep sockets under XDG_RUNTIME_DIR.
    runtime=Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000"))
    short=runtime/f"qh2-{os.getpid()}-{index}"
    need(not short.exists() and not short.is_symlink(),"SOCKET_ALIAS_EXISTS")
    short.symlink_to(recovery_dir,target_is_directory=True)
    try:
        ipc_time=shell_run([sys.executable,str(args.recovery),
          str(args.source),str(args.probe),str(raw),str(manifest),
          str(day/"compute.log"),str(args.cpu_receipt),
          str(short),str(recovery_json)],
          day/"recovery.stdout.log",timeout=args.timeout)
    finally:
        short.unlink(missing_ok=True)
    results=json.loads(recovery_json.read_text())
    need(results["total_verified_frames"]==15 and
         results["early_disconnect_denied"],"IPC_RECOVERY_NOT_COMPLETE")
    return {"index":index,"engine":times,"artifacts":artifacts,
       "manifest_sha256":file_sha(manifest),
       "manifest_build_seconds":elapsed,
       "transport_restart_seconds":ipc_time,
       "ipc_verified_frames":15,
       "recovery_receipt_sha256":file_sha(recovery_json),
       "full_chain_seconds":round(times["seconds"]+elapsed+ipc_time,4)}
def interrupt_gpu_after_first_frame(engine,root,timeout=30):
    folder=root/"fault-mid-frame"
    folder.mkdir()
    log=root/"fault-mid-frame.log"
    started=time.monotonic()
    with log.open("wb") as f:
        proc=subprocess.Popen([str(engine),str(folder)],
               stdout=f,stderr=subprocess.STDOUT)
        first=folder/"state0-ceramic-frame0-dpr2.gpu-rgba.bin"
        saw=False
        while time.monotonic()-started < timeout and proc.poll() is None:
            if first.is_file() and first.stat().st_size==786432:
                saw=True
                proc.terminate()
                break
            time.sleep(0.005)
        if proc.poll() is None and not saw:
            proc.terminate()
        try: status=proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            status=proc.wait(timeout=5)
    artifacts=list(folder.glob("*.gpu-rgba.bin"))
    incomplete=0<len(artifacts)<40 and status!=0
    return {"first_frame_observed":saw,"interrupted":incomplete,
        "gpu_frames_before_termination":len(artifacts),
        "process_exit":status,
        "duration_seconds":round(time.monotonic()-started,4),
        "result":"PASS_INTERRUPTED_MID_COMPUTE" if incomplete
             else "INCONCLUSIVE_RACE_OR_EARLY_FAILURE",
        "log_sha256":file_sha(log)}
def main():
    parser=argparse.ArgumentParser()
    for name in ("engine","source","probe","manifest_builder","recovery",
                 "cpu_raw","cpu_receipt","reference","root","report"):
        parser.add_argument("--"+name.replace("_","-"),required=True,type=Path)
    parser.add_argument("--cycles",type=int,default=3)
    parser.add_argument("--timeout",type=int,default=75)
    args=parser.parse_args()
    need(args.cycles>=2 and args.cycles<=25,"CYCLE_LIMIT")
    need(args.root.is_dir() and not any(args.root.iterdir()),
         "RUN_ROOT_MUST_BE_FRESH_AND_EMPTY")
    need(not args.report.exists(),"REFUSE_OVERWRITE")
    need(all(p.exists() for p in (args.engine,args.source,args.probe,
         args.manifest_builder,args.recovery,args.cpu_raw,args.cpu_receipt,
         args.reference)),"MISSING_REQUIRED_INPUT")
    cycles=[]
    for n in range(1,args.cycles+1):
        result=run_cycle(n,args,args.root)
        cycles.append(result)
        print("CPH2_COMPLETE_GPU_IPC_CYCLE",n,
              "gpu_seconds",result["engine"]["seconds"],
              "ipc_frames",result["ipc_verified_frames"],flush=True)
        if n==1:
            mid=interrupt_gpu_after_first_frame(args.engine,args.root)
            print("CPH2_MID_COMPUTE_FAULT",mid["result"],flush=True)
            startup=fail_gpu_then_restore(args.engine,args.root)
            print("CPH2_UNAVAILABLE_GPU_REFUSAL",startup["exit_code"],flush=True)
    need(all(c["artifacts"]["files_exact"]==52 for c in cycles),
         "GPU_REFERENCE_SET_DRIFT")
    need(len(set(tuple(c["artifacts"]["source_frame_sha256"]) for c in cycles))==1,
         "DIFFERENT_GPU_IMAGES_ACROSS_RESTARTS")
    summary={"schema":"gnu6.qchain.cph2_full_engine_recovery.v1",
       "verdict":"QCHAIN_CPH2_FRESH_GPU_ENGINE_AND_SEALED_IPC_RESTART_PASS",
       "source":"Fresh archival F2-F4 Vulkan engine, separate archival CP-H transport",
       "engine_cycle_count":len(cycles),
       "gpu_frames_newly_computed":40*len(cycles),
       "all_reference_artifacts_exact":52*len(cycles),
       "ipc_frames_verified":15*len(cycles),
       "restart_source_processes":4*len(cycles),
       "mid_computation_interruption":mid,
       "gpu_startup_failure":startup,
       "cpu_fixture_unchanged":True,
       "gpu_driver_trace":"NOT_RUN",
       "gpu_memory_vram_measurements":"NOT_RUN",
       "wayland_new_capture":"NOT_RUN",
       "auto_restart_supervisor":False,
       "cp03_hybrid60":"OPEN","cycles":cycles}
    args.report.write_text(json.dumps(summary,indent=2)+"\n")
    print(summary["verdict"],"gpu_frames",
          summary["gpu_frames_newly_computed"],
          "ipc",summary["ipc_frames_verified"],flush=True)
if __name__=="__main__":
    main()
