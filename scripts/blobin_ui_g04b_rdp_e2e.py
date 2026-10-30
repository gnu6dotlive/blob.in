#!/usr/bin/env python3
"""UI-G04/B isolated RDP -> Weston -> Wayland -> winit -> UI-core E2E.
Run inside: unshare -Urn -- bash -lc 'ip link set lo up; python3 ...'
RDP loopback cannot be reached from the user's normal network namespace.
"""
from pathlib import Path
import argparse,hashlib,json,os,socket,subprocess,time,sys
p=argparse.ArgumentParser()
p.add_argument("--output",type=Path,required=True)
p.add_argument("--binary",type=Path,required=True)
p.add_argument("--injector",type=Path,required=True)
args=p.parse_args()
out=args.output.resolve()
out.mkdir(parents=True,exist_ok=True)
private=out/"tls"
private.mkdir(exist_ok=True,mode=0o700)
cert=private/"rdp-cert.pem";key=private/"rdp-key.pem"
openssl=subprocess.run(["openssl","req","-x509","-newkey","rsa:2048",
    "-nodes","-keyout",str(key),"-out",str(cert),"-subj","/CN=localhost",
    "-days","1"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
if openssl.returncode:raise RuntimeError("RDP_TEST_TLS_CERT_FAILED")
os.chmod(key,0o600)
runtime=Path(os.environ.get("XDG_RUNTIME_DIR","/run/user/1000"))
display="blob-g04b-rdp-"+str(os.getpid())
env=dict(os.environ,WAYLAND_DISPLAY=display,XDG_RUNTIME_DIR=str(runtime),
         RUST_BACKTRACE="1",WLOG_LEVEL="WARN",BLOBIN_G04B_ALLOW_GL="1")
for name in ("VK_LAYER_PATH","VK_INSTANCE_LAYERS","CPJA7CB_LOADER_FAULT"):env.pop(name,None)
port=3397
procs=[]
def require(condition,message):
    if not condition:raise RuntimeError(message)
def start(name,command,env=env):
    stdout=(out/(name+".stdout")).open("wb")
    stderr=(out/(name+".stderr")).open("wb")
    try:
        proc=subprocess.Popen(command,cwd=out,env=env,stdout=stdout,stderr=stderr,
                              start_new_session=True)
    finally:
        stdout.close();stderr.close()
    procs.append(proc)
    return proc
try:
    weston=start("weston",["weston","--backend=rdp","--renderer=gl",
        "--shell=kiosk","--address=127.0.0.1",f"--port={port}",
        f"--rdp-tls-cert={cert}",f"--rdp-tls-key={key}",f"--rdp4-key={key}",
        "--width=900","--height=600","--no-config","--idle-time=0",
        "-S",display,f"--log={out/'weston.log'}"])
    for _ in range(200):
        if (runtime/display).is_socket() or weston.poll() is not None:break
        time.sleep(0.03)
    require((runtime/display).is_socket() and weston.poll() is None,"WESTON_RDP_NOT_STARTED")
    viewer=start("viewer",[str(args.binary.resolve()),f"--trace={out/'input-trace.jsonl'}",
        "--run-ms=14000"])
    for _ in range(250):
        if viewer.poll() is not None:break
        path=out/"input-trace.jsonl"
        if path.exists() and '"kind":"window_ready"' in path.read_text():break
        time.sleep(0.03)
    require(viewer.poll() is None,"NATIVE_VIEWER_EXITED_BEFORE_INJECTION")
    require('"kind":"window_ready"' in (out/"input-trace.jsonl").read_text(),
            "NATIVE_VIEWER_WINDOW_NOT_READY")
    injector=start("injector",[str(args.injector.resolve()),str(port)])
    injector.wait(timeout=18)
    print("RDP_INJECTOR_EXIT",injector.returncode,flush=True)
    viewer.wait(timeout=20)
    print("NATIVE_VIEWER_EXIT",viewer.returncode,flush=True)
    lines=[json.loads(s) for s in (out/"input-trace.jsonl").read_text().splitlines()]
    ingress=[s for s in lines if s.get("kind")=="ingress"]
    receipts=[s for s in lines if s.get("kind")=="receipt"]
    acts=[s for s in receipts if s.get("activation")]
    injections=(out/"injector.stdout").read_text(errors="replace")
    completed="RDP_INPUT_SEND_COMPLETE success=1" in injections
    sources=sorted(set(s.get("event") for s in ingress))
    valid=(
        injector.returncode==0 and viewer.returncode==0
        and completed and "RDP_CONNECTED actual_protocol_transport=1" in injections
        and len(ingress)>=7 and len(receipts)==len(ingress)
        and any(s.get("event")=="mouse_down" for s in ingress)
        and any(s.get("event")=="mouse_up" for s in ingress)
        and any(s.get("event")=="cursor_moved" for s in ingress)
        and any(s.get("event")=="key" for s in ingress)
        and len(acts)>=3
    )
    report={"gate":"UI-G04/B","transport":"isolated_local_RDP_Weston_to_Wayland_winit",
        "network_namespace":"user+net; loopback only; no host desktop interaction",
        "verdict":"COMPOSITOR_INPUT_SCOPED_PASS" if valid else "E2E_HOLD",
        "rdp_connected":("RDP_CONNECTED" in injections),
        "rdp_commands_succeeded":completed,
        "winit_ingress":len(ingress),"router_receipts":len(receipts),
        "activation_count":len(acts),"activation_targets":[s["activation"] for s in acts],
        "winit_event_types":sources,
        "frame_submissions":next((s["frame_submissions"] for s in lines if s.get("kind")=="summary"),0),
        "hardware_hid_input_verified":False,
        "source_built_binary_sha256":hashlib.sha256(args.binary.read_bytes()).hexdigest(),
        "input_trace_sha256":hashlib.sha256((out/"input-trace.jsonl").read_bytes()).hexdigest(),
        "rdp_injector_sha256":hashlib.sha256(args.injector.read_bytes()).hexdigest(),
        "compositor_presentation_feedback_verified":False,
        "cp03_hybrid60_pass":False}
    (out/"e2e-verdict.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2),flush=True)
    if not valid:sys.exit(2)
except Exception as exc:
    print("G04B_RDP_E2E_FAILURE",repr(exc),file=sys.stderr,flush=True)
    sys.exit(1)
finally:
    for proc in reversed(procs):
        if proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=3)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=3)
