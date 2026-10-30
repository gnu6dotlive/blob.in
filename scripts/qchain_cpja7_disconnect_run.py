#!/usr/bin/env python3
"""Private isolated Weston + real GPU live stream; sample eight distinct variants."""
import argparse,hashlib,json,os,re,subprocess,time
from pathlib import Path
from PIL import Image,ImageOps
def need(cond,reason):
    if not cond:raise RuntimeError(reason)
def sha(b):return hashlib.sha256(b).hexdigest()
def run(a):
    root=a.root
    need(root.is_dir() and not any(root.iterdir()),"CPI02_RUN_DIRECTORY_NOT_EMPTY")
    (root/"engine-ledger").mkdir(mode=0o700)
    runtime=Path(os.environ.get("XDG_RUNTIME_DIR","/run/user/1000"))
    ws=f"qci02-w-{os.getpid()}"
    ipc=runtime/f"qci02-{os.getpid()}.sock"
    need(not (runtime/ws).exists() and not ipc.exists(),"PRIVATE_SOCKET_EXISTS")
    weston_log=root/"weston.log"
    env=dict(os.environ, XDG_RUNTIME_DIR=str(runtime),
             WAYLAND_DISPLAY=ws, RUST_BACKTRACE="1")
    files=[]
    weston=source=viewer=None
    samples=[]
    started=time.monotonic()
    try:
        weston=subprocess.Popen(["weston","--backend=headless","--renderer=gl",
              "--shell=kiosk","--debug","-S",ws,"--width=512",
              "--height=384","--no-config","--idle-time=0",
              f"--log={weston_log}"],env=env,
              stdout=(root/"weston.stdout").open("wb"),
              stderr=subprocess.STDOUT,start_new_session=True)
        for _ in range(200):
            if (runtime/ws).is_socket():break
            if weston.poll() is not None:break
            time.sleep(0.025)
        need((runtime/ws).is_socket(),"PRIVATE_WESTON_BOOT_FAILED")
        debugger=subprocess.Popen(["weston-debug","-o",str(root/"weston-timeline-proto.log"),"proto"],env=env,stdout=subprocess.DEVNULL,stderr=(root/"weston-debug.err").open("wb"))
        for name in ("source","viewer"):
            files.append((root/f"{name}.stdout").open("wb"))
            files.append((root/f"{name}.stderr").open("wb"))
        source=subprocess.Popen(["python3",str(a.broker),"--engine",str(a.engine),
          "--baseline",str(a.baseline),"--receipt",str(a.receipt),
          "--socket",str(ipc),"--log",str(root/"engine-ledger"),
          "--frames","120"],env=env,stdout=files[0],stderr=files[1])
        for _ in range(200):
            if ipc.is_socket():break
            if source.poll() is not None:break
            time.sleep(0.025)
        need(ipc.is_socket(),"LIVE_GPU_BROKER_NOT_READY")
        viewer=subprocess.Popen([str(a.viewer),str(ipc),str(a.receipt),"120"],
               stdout=files[2],stderr=files[3],env=dict(env,WAYLAND_DEBUG="client"))

        # Kill only this test's private Weston compositor after 60 source frames.
        deadline=time.monotonic()+15
        reached=False
        while time.monotonic()<deadline:
            log=(root/"viewer.stdout").read_text(errors="replace")
            nums=[int(v) for v in re.findall(r"CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+)",log)]
            if 59 in nums:
                reached=True
                break
            if viewer.poll() is not None:
                break
            time.sleep(.008)
        need(reached,"PRIVATE_COMPOSITOR_DISCONNECT_FRAME_59_NOT_REACHED")
        print("CPJA7_PRIVATE_WESTON_TERMINATE after_seq=59",flush=True)
        weston.terminate()
        weston.wait(timeout=3)
        try: viewer.wait(timeout=8)
        except subprocess.TimeoutExpired:
            viewer.kill()
            viewer.wait(timeout=3)
        need(viewer.returncode!=0,"COMPOSITOR_DISCONNECT_MUST_FAIL_CLOSED")
        need("CPI02_WGPU_STREAM_COMPLETE" not in (root/"viewer.stdout").read_text(),
             "FALSE_COMPLETION_AFTER_COMPOSITOR_LOSS")
        need(not (root/"run-verdict.json").exists(),"FALSE_SUCCESS_RECEIPT")
        report={"schema":"gnu6.qchain.cpja7_compositor_disconnect.v1",
             "verdict":"CPJA7_PRIVATE_WESTON_LOST_VIEWER_FAIL_CLOSED",
             "disconnect_after_source_seq":59,"viewer_exit":viewer.returncode,
             "no_success_receipt":True,"physical_vk_device_lost":False}
        (root/"disconnect-oracle.json").write_text(json.dumps(report,indent=2)+"\n")
        print(report["verdict"],flush=True)
        return
    finally:
        for proc in (viewer,source,locals().get("debugger"),weston):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.wait(timeout=3)
        for f in files:f.close()
        ipc.unlink(missing_ok=True)
def main():
    p=argparse.ArgumentParser()
    for k in ("engine","viewer","broker","baseline","receipt","root"):
        p.add_argument("--"+k,required=True,type=Path)
    a=p.parse_args()
    run(a)
if __name__=="__main__":main()
