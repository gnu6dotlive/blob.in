#!/usr/bin/env python3
"""Isolated Wayland/native wgpu smoke; does not inject compositor input."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,time,sys
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument("--output",type=Path,required=True)
parser.add_argument("--binary",type=Path,required=True)
args=parser.parse_args()
out=args.output.resolve()
out.mkdir(parents=True,exist_ok=True)
runtime=Path(os.environ.get("XDG_RUNTIME_DIR","/run/user/1000"))
display="blob-g04b-smoke-"+str(os.getpid())
env=dict(os.environ,WAYLAND_DISPLAY=display,XDG_RUNTIME_DIR=str(runtime),RUST_BACKTRACE="1")
for item in ("VK_LAYER_PATH","VK_INSTANCE_LAYERS","CPJA7CB_LOADER_FAULT"):env.pop(item,None)
procs=[]
try:
    with (out/"weston.stdout").open("wb") as fp:
        weston=subprocess.Popen([
            "weston","--backend=headless","--renderer=gl","--shell=kiosk",
            "-S",display,"--no-config","--width=900","--height=600",
            "--idle-time=0",f"--log={out/'weston.log'}"
        ],env=env,cwd=out,stdout=fp,stderr=subprocess.STDOUT,start_new_session=True)
    procs.append(weston)
    for _ in range(200):
        if (runtime/display).is_socket() or weston.poll() is not None:break
        time.sleep(0.02)
    if not (runtime/display).is_socket() or weston.poll() is not None:
        raise RuntimeError("WESTON_PRIVATE_SOCKET_UNAVAILABLE")
    with (out/"viewer.stdout").open("wb") as fp, (out/"viewer.stderr").open("wb") as fe:
        native=subprocess.Popen([str(args.binary.resolve()),
            f"--trace={out/'input-trace.jsonl'}","--run-ms=4500"],
            env=env,cwd=out,stdout=fp,stderr=fe,start_new_session=True)
    procs.append(native)
    native.wait(timeout=28)
    if native.returncode != 0:raise RuntimeError("NATIVE_PROBE_NONZERO_EXIT")
    lines=[json.loads(row) for row in (out/"input-trace.jsonl").read_text().splitlines()]
    ready=[x for x in lines if x["kind"]=="window_ready"]
    frame=[x for x in lines if x["kind"]=="summary"]
    if len(ready)!=1 or len(frame)!=1 or frame[0]["frame_submissions"]<1:
        raise RuntimeError("NATIVE_WAYLAND_WINDOW_OR_FRAME_MISSING")
    report={"gate":"UI-G04/B",
        "verdict":"NATIVE_WAYLAND_LAUNCH_SCOPED_PASS_INPUT_E2E_HOLD",
        "private_compositor":True,"gpu_backend":ready[0]["backend"],
        "native_window":True,"frames_submitted":frame[0]["frame_submissions"],
        "winit_ingress":frame[0]["ingress_count"],
        "compositor_pointer_keyboard_e2e":False,
        "compositor_presented_feedback":False,
        "binary_sha256":hashlib.sha256(args.binary.read_bytes()).hexdigest()}
    (out/"native-smoke.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report),flush=True)
except Exception as exc:
    print("UI_G04B_NATIVE_SMOKE_FAIL",exc,file=sys.stderr)
    sys.exit(1)
finally:
    for proc in reversed(procs):
        if proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=3)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=3)
