#!/usr/bin/env python3
"""Bounded opt-in QCHAIN Wayland test. Capture the active QCHAIN window only."""
from pathlib import Path
import hashlib,json,os,re,subprocess,time
E=Path("/mnt/workbench/evidence/runs/qchain-gpu-hardening-20261010-01/wayland")
SOURCE=Path("/mnt/workbench/build/qchain-gpu-independent-20261010/debug/examples/qchain_gpu_source")
VIEWER=Path("/mnt/workbench/build/blobin-qchain-gpu-wayland-20261010/debug/qchain_gpu_viewer")
RAW=Path("/mnt/workbench/evidence/runs/qchain-gpu-ipc-wayland-20261010-01/compute/raw")
RECEIPT=Path("/mnt/workbench/evidence/runs/qchain-gpu-ipc-wayland-20261010-01/compute/gpu-source-manifest.json")
COMPUTE_LOG=Path("/mnt/workbench/evidence/runs/qchain-gpu-ipc-wayland-20261010-01/compute/compute.log")
CPU_RECEIPT=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-reconciliation.json")
SOCKDIR=E/"socket"
SOCKET=SOCKDIR/"render.sock"
env=os.environ.copy()
env["WAYLAND_DISPLAY"]="wayland-1"
env["HYPRLAND_INSTANCE_SIGNATURE"]="efb50993780079460b0cbed1363e2166a2de1d9f_1791647968_1117103218"
def sh(cmd,timeout=3):
 return subprocess.run(cmd,env=env,capture_output=True,check=True,timeout=timeout,text=True).stdout
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if not all(x.is_file() for x in (SOURCE,VIEWER,RECEIPT)):
 raise SystemExit("ABORT_MISSING_TRUSTED_INPUT")
SOCKDIR.mkdir(mode=0o700,exist_ok=True)
os.chmod(SOCKDIR,0o700)
if SOCKET.exists():raise SystemExit("ABORT_SOCKET_ALREADY_EXISTS")
monitors=json.loads(sh(["hyprctl","monitors","-j"]))
assert any(x.get("name")=="HDMI-A-1" and x.get("scale")==1 for x in monitors)
record={"schema":"gnu6.qchain.wayland_observation.v1","status":"RUN_STARTED",
 "source_binary_sha256":sha(SOURCE),"viewer_binary_sha256":sha(VIEWER),
 "cpu_receipt_sha256":sha(RECEIPT),"display":"wayland-1",
 "captures":[],"physical_photons_qualified":False,"cp03_full_pass":False}
server=None;viewer=None
with (E/"source.log").open("wb") as sout,(E/"source-error.log").open("wb") as serr, (E/"viewer.log").open("wb") as vout,(E/"viewer-error.log").open("wb") as verr:
 try:
  server=subprocess.Popen([str(SOURCE),str(RAW),str(RECEIPT),str(COMPUTE_LOG),str(CPU_RECEIPT),str(SOCKET)],stdout=sout,stderr=serr,env=env)
  for _ in range(50):
   if SOCKET.is_socket():break
   if server.poll() is not None:raise RuntimeError("QCHAIN_SOURCE_FAILED_TO_START")
   time.sleep(0.06)
  if not SOCKET.is_socket():raise RuntimeError("SOURCE_SOCKET_NOT_READY")
  viewer=subprocess.Popen([str(VIEWER),str(SOCKET),str(RECEIPT)],
                          stdout=vout,stderr=verr,env=env)
  seen=set()
  began=time.monotonic()
  while time.monotonic()-began<20:
   vout.flush()
   content=(E/"viewer.log").read_text(errors="replace")
   observed=[int(x) for x in re.findall(r"QCHAIN_GPU_WGPU_PRESENT_SUBMITTED stage=(\d+)",content)]
   for stage in observed:
    if stage in seen:continue
    seen.add(stage)
    time.sleep(1.28)
    info={"stage":stage}
    try:
     clients=json.loads(sh(["hyprctl","clients","-j"]))
     windows=[w for w in clients if w.get("class")=="blobin-qchain-gpu-viewer"]
     active=json.loads(sh(["hyprctl","activewindow","-j"]))
     if len(windows)!=1 or active.get("class")!="blobin-qchain-gpu-viewer":
      raise ValueError("QCHAIN_WINDOW_NOT_EXCLUSIVELY_ACTIVE")
     w=windows[0]
     addr=w.get("address")
     if not isinstance(addr,str) or not addr.startswith("0x"):
      raise ValueError("QCHAIN_WINDOW_ADDRESS_UNVERIFIED")
     # Ephemeral per-window prop only; no global config or other window mutation.
     prop=subprocess.run(["hyprctl","setprop",f"address:{addr}","rounding","0"],
                         env=env,capture_output=True,text=True,timeout=2)
     info["qchain_window_rounding_disabled"]=prop.returncode==0
     if prop.returncode!=0:info["rounding_rejection"]=prop.stderr[:120]
     time.sleep(0.10)
     size=w.get("size");at=w.get("at")
     if size!=[512,384] or not isinstance(at,list) or len(at)!=2:
      raise ValueError("UNEXPECTED_WINDOW_GEOMETRY")
     if not any(m.get("activeWorkspace",{}).get("id")==w.get("workspace",{}).get("id") for m in json.loads(sh(["hyprctl","monitors","-j"]))):
      raise ValueError("QCHAIN_WINDOW_NOT_ON_VISIBLE_WORKSPACE")
     image=E/f"stage-{stage:02}.png"
     if image.exists():raise ValueError("CAPTURE_EXISTS_ALREADY")
     geometry=f"{at[0]},{at[1]} {size[0]}x{size[1]}"
     subprocess.run(["grim","-g",geometry,str(image)],env=env,check=True,capture_output=True,timeout=4)
     captured=subprocess.run(["magick",str(image),"-depth","8","RGBA:-"],
                             env=env,check=True,capture_output=True,timeout=4).stdout
     expected=(RAW/f"state{stage}-ceramic-frame0-dpr2.gpu-rgba.bin").read_bytes()
     if len(captured)!=len(expected):raise ValueError("CAPTURE_DIFFERENT_PIXEL_DIMENSIONS")
     total=len(expected)
     mae=sum(abs(a-b) for a,b in zip(captured,expected))/total
     exact=sum(a==b for a,b in zip(captured,expected))/total
     flipped=b"".join(captured[i*2048:(i+1)*2048] for i in range(383,-1,-1))
     flip_mae=sum(abs(a-b) for a,b in zip(flipped,expected))/total
     info.update({"captured":True,"geometry":geometry,"capture_sha256":sha(image),
                 "expected_rgba_sha256":sha(RAW/f"state{stage}-ceramic-frame0-dpr2.gpu-rgba.bin"),
                 "raw_capture_rgba_sha256":hashlib.sha256(captured).hexdigest(),
                 "mean_absolute_channel_error":round(mae,5),
                 "exact_byte_ratio":round(exact,6),
                 "flipped_y_mae":round(flip_mae,5),
                 "pixel_match_strict":captured==expected})
    except Exception as exc:
     info.update({"captured":False,"reason":type(exc).__name__+":"+str(exc)[:190]})
    record["captures"].append(info)
    print("QCHAIN_CAPTURE_RESULT",json.dumps(info),flush=True)
   if viewer.poll() is not None:break
   time.sleep(0.09)
  if viewer.poll() is None:viewer.wait(timeout=3)
  record["viewer_exit_code"]=viewer.returncode
  record["source_exit_code"]=server.wait(timeout=3)
  record["winit_present_submitted_stages"]=sorted(seen)
  record["viewport_captures_count"]=sum(x.get("captured",False) for x in record["captures"])
  record["compositor_exact_pixels_verified"]=(
      len(seen)==5 and len(record["captures"])==5 and
      all(x.get("pixel_match_strict",False) for x in record["captures"])
  )
  record["status"]="GPU_FIVE_FRAMES_SUBMITTED_AND_EXACT_CAPTURED" if record["compositor_exact_pixels_verified"] else (
    "FIVE_FRAMES_SUBMITTED_CAPTURE_NOT_EXACT" if len(seen)==5 else "FAIL_CANNOT_ATTEST_FIVE_FRAMES"
  )
 finally:
  for process in (viewer,server):
   if process is not None and process.poll() is None:
    process.terminate()
    try:process.wait(timeout=2)
    except subprocess.TimeoutExpired:process.kill()
  record["source_stdout_sha256"]=sha(E/"source.log")
  record["viewer_stdout_sha256"]=sha(E/"viewer.log")
  (E/"capture-reconciliation.json").write_text(json.dumps(record,indent=2)+"\n")
print("QCHAIN_EXPERIMENT_FINAL",record["status"],"frames",record.get("winit_present_submitted_stages",[]),
      "captures",record.get("viewport_captures_count"),"viewer_exit",record.get("viewer_exit_code"))
if record.get("viewer_exit_code")!=0 or record.get("source_exit_code")!=0 or len(record.get("winit_present_submitted_stages",[]))!=5:
 raise SystemExit(12)
