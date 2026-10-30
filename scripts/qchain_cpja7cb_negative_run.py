#!/usr/bin/env python3
"""CP-JA7C fail-closed controls: Weston private, no device reset, no PASS receipt."""
import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

def need(cond, message):
    if not cond:
        raise RuntimeError(message)

def run(a):
    root=a.root
    need(root.is_dir() and not any(root.iterdir()),"NONEMPTY_NEGATIVE_RUN_ROOT")
    (root/"engine-ledger").mkdir(mode=0o700)
    runtime=Path(os.environ.get("XDG_RUNTIME_DIR","/run/user/1000"))
    ws=f"cpja7c-negative-{os.getpid()}"
    ipc=runtime/f"cpja7c-negative-{os.getpid()}.sock"
    need(not (runtime/ws).exists() and not ipc.exists(),"PRIVATE_SOCKET_IN_USE")
    env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime),WAYLAND_DISPLAY=ws)
    for k in ("CPJA7C_INJECT_LOST_AT","CPJA7C_RECOVER_IN_PROCESS",
              "CPJA7CB_LOADER_FAULT","VK_LAYER_PATH","VK_INSTANCE_LAYERS",
              "CPJA7CB_PROCESS_LOSS_COUNT"):
        env.pop(k,None)
    venv=dict(env,WAYLAND_DEBUG="client",RUST_BACKTRACE="1",
              VK_LAYER_PATH=str(a.layer_dir),
              VK_INSTANCE_LAYERS="VK_LAYER_GNU6_cpja7cb_fault")
    if a.mode=="no-recovery":
        venv["CPJA7CB_LOADER_FAULT"]="primary-id-41"
    elif a.mode=="double-loss":
        venv["CPJA7CB_LOADER_FAULT"]="primary-twice"
        venv["CPJA7C_RECOVER_IN_PROCESS"]="1"
    elif a.mode=="no-injection":
        venv["CPJA7C_RECOVER_IN_PROCESS"]="1"
    weston=source=viewer=None
    handles=[]
    try:
        handles.append((root/"weston.stdout").open("wb"))
        weston=subprocess.Popen(
            ["weston","--backend=headless","--renderer=gl","--shell=desktop",
             "--modules="+str(a.tile_plugin),"-S",ws,"--width=1536",
             "--height=1024","--no-config","--idle-time=0",
             "--log="+str(root/"weston.log")],
            env=env,stdout=handles[-1],stderr=subprocess.STDOUT,
            start_new_session=True)
        for _ in range(200):
            if (runtime/ws).is_socket() or weston.poll() is not None:break
            time.sleep(.025)
        need((runtime/ws).is_socket() and weston.poll() is None,
             "PRIVATE_WESTON_FAILED")
        for name in ("source","viewer"):
            for ext in ("stdout","stderr"):
                handles.append((root/f"{name}.{ext}").open("wb"))
        source=subprocess.Popen(
            ["python3",str(a.broker),"--engine",str(a.engine),
             "--baseline",str(a.baseline),"--receipt",str(a.receipt),
             "--socket",str(ipc),"--log",str(root/"engine-ledger"),
             "--frames","120"],env=env,stdout=handles[1],stderr=handles[2])
        for _ in range(200):
            if ipc.is_socket() or source.poll() is not None:break
            time.sleep(.025)
        need(ipc.is_socket(),"PRIVATE_BROKER_NOT_READY")
        viewer=subprocess.Popen(
            [str(a.viewer),str(ipc),str(a.receipt),"120"],
            env=venv,
            stdout=handles[3],stderr=handles[4])
        viewer.wait(timeout=24)
        need(viewer.returncode!=0,"NEGATIVE_VIEWER_MUST_FAIL")
        app=(root/"viewer.stdout").read_text(errors="replace")
        err=(root/"viewer.stderr").read_text(errors="replace")
        observed=len(re.findall(r"CPI02_WGPU_PRESENT_SUBMITTED seq=\d+",app))
        if a.mode=="no-recovery":
            need(observed==40,"FAIL_CLOSED_WRONG_BOUNDARY")
            need(err.count("CPJA7CB_LOADER_INJECTED_VK_ERROR_DEVICE_LOST")==1 and
                 err.count("CPJA7C_WGPU_DEVICE_LOST_CALLBACK")==1,
                 "NO_RECOVERY_NOT_DELIVERED")
            need("CPJA7C_SECOND_DEVICE_LOSS_FAIL_CLOSED after_epoch=0" in app,
                 "NOT_FAILED_CLOSED")
            need("CPJA7C_RECOVERY_READY" not in app,"FALSE_DEVICE_REBUILD")
        elif a.mode=="double-loss":
            need(observed==44,"SECOND_FAULT_WRONG_BOUNDARY")
            need(err.count("CPJA7CB_LOADER_INJECTED_VK_ERROR_DEVICE_LOST")==2 and
                 err.count("CPJA7C_WGPU_DEVICE_LOST_CALLBACK")==2,
                 "DOUBLE_LOSS_NOT_DELIVERED")
            need("CPJA7C_RECOVERY_READY new_epoch=1" in app and
                 "CPJA7C_SECOND_DEVICE_LOSS_FAIL_CLOSED after_epoch=1" in app,
                 "SECOND_LOSS_NOT_FAILED_CLOSED")
        else:
            need(observed==120,"NO_INJECTION_SOURCE_DRIFT")
            need("CPJA7C_RECOVERY_EPOCH_NOT_OBSERVED" in err,
                 "NO_INJECTION_FALSE_RECOVERY")
            need("CPJA7C_INJECTED_VK_ERROR_DEVICE_LOST" not in err,
                 "UNEXPECTED_INJECTION")
        need("CPI02_WGPU_STREAM_COMPLETE" not in app,
             "FALSE_COMPLETION_ON_NEGATIVE")
        need(not (root/"run-verdict.json").exists(),
             "FALSE_SUCCESS_RECEIPT_ON_NEGATIVE")
        report={
            "schema":"gnu6.qchain.cpja7cb_negative.v1",
            "verdict":"CPJA7CB_"+a.mode.upper().replace("-","_")+"_FAIL_CLOSED_PASS",
            "mode":a.mode,"viewer_exit":viewer.returncode,
            "submitted_frames":observed,"success_receipt":False,
            "injections":err.count("CPJA7CB_LOADER_INJECTED_VK_ERROR_DEVICE_LOST"),
            "device_lost_callbacks":err.count("CPJA7C_WGPU_DEVICE_LOST_CALLBACK"),
            "physical_gpu_reset":False,"private_weston_alive_until_cleanup":weston.poll() is None}
        (root/"negative-verdict.json").write_text(json.dumps(report,indent=2)+"\n")
        print(report["verdict"],"frames",observed,"viewer_exit",viewer.returncode,flush=True)
    finally:
        for proc in (viewer,source,weston):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.wait(timeout=3)
        for handle in handles:handle.close()
        ipc.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",required=True,
                   choices=("no-recovery","double-loss","no-injection"))
    for name in ("engine","viewer","broker","baseline","receipt","root","tile-plugin"):
        p.add_argument("--"+name,required=True,type=Path)
    p.add_argument("--layer-dir",required=True,type=Path)
    run(p.parse_args())

if __name__=="__main__":
    main()
