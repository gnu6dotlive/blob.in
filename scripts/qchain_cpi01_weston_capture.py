#!/usr/bin/env python3
"""Opt-in Weston headless capture: never contacts the user's Hyprland socket."""
import argparse, hashlib, json, os, re, subprocess, time
from pathlib import Path
from PIL import Image

def need(v,why):
    if not v:raise RuntimeError(why)
def sha(data):return hashlib.sha256(data).hexdigest()
def data(p):return p.read_bytes()
def main():
    a=argparse.ArgumentParser()
    for k in ("source","viewer","raw","manifest","compute_log","cpu_receipt","socket","out"):
        a.add_argument("--"+k.replace("_","-"),type=Path if k!="socket" else str,required=True)
    args=a.parse_args()
    out=args.out
    need(out.is_dir() and not any(out.iterdir()),"CAPTURE_ROOT_NOT_EMPTY")
    runtime=os.environ.get("XDG_RUNTIME_DIR","/run/user/1000")
    need(args.socket.startswith("qchain-cpi-debug-"),"UNAUTHORIZED_WAYLAND_SOCKET")
    need(Path(runtime,args.socket).is_socket(),"PRIVATE_HEADLESS_WESTON_NOT_RUNNING")
    env=dict(os.environ,WAYLAND_DISPLAY=args.socket,XDG_RUNTIME_DIR=runtime)
    own_socket=Path(runtime,f"qci-cpi-{os.getpid()}.sock")
    need(not own_socket.exists(),"PRIVATE_IPC_SOCKET_EXISTS")
    handles=[]
    results=[]
    start=time.monotonic()

    try:
        server_out=(out/"source.log").open("wb");handles.append(server_out)
        server_err=(out/"source.err").open("wb");handles.append(server_err)
        viewer_out=(out/"viewer.log").open("wb");handles.append(viewer_out)
        viewer_err=(out/"viewer.err").open("wb");handles.append(viewer_err)
        source=subprocess.Popen([str(args.source),str(args.raw),str(args.manifest),
                 str(args.compute_log),str(args.cpu_receipt),str(own_socket)],
                 stdout=server_out,stderr=server_err,env=env)
        for _ in range(160):
            if own_socket.is_socket():break
            if source.poll() is not None:break
            time.sleep(0.025)
        need(own_socket.is_socket(),"GPU_SOURCE_FAILED_TO_BIND")
        viewer=subprocess.Popen([str(args.viewer),str(own_socket),str(args.manifest)],
                stdout=viewer_out,stderr=viewer_err,env=env)
        seen=set()
        for stage in range(5):
            deadline=time.monotonic()+22
            while time.monotonic()<deadline:
                if viewer.poll() is not None:raise RuntimeError("VIEWER_EXITED_BEFORE_STAGE_"+str(stage))
                log=(out/"viewer.log").read_text(errors="replace")
                if re.search(r"QCHAIN_GPU_WGPU_PRESENT_SUBMITTED stage="+str(stage)+r"\b",log):
                    break
                time.sleep(0.04)
            else:raise RuntimeError("GPU_WGPU_STAGE_NOT_SUBMITTED_"+str(stage))
            time.sleep(0.42) # fixed stabilization, no mask expansion
            before=set(out.glob("wayland-screenshot-*.png"))
            shot=subprocess.run(["weston-screenshooter"],cwd=out,env=env,
                    capture_output=True,text=True,timeout=7)
            need(shot.returncode==0 and "unauthorized" not in
                 (shot.stdout+shot.stderr).lower(),"HEADLESS_CAPTURE_UNAUTHORIZED")
            newer=set(out.glob("wayland-screenshot-*.png"))-before
            need(len(newer)==1,"HEADLESS_SCREENSHOT_NOT_UNIQUE")
            captured=next(iter(newer))
            png=out/f"stage-{stage:02}.png"
            captured.rename(png)

            with Image.open(png) as img:
                need(img.size==(512,384),"HEADLESS_OUTPUT_DIMENSION_CHANGED")
                pixels=img.convert("RGBA").tobytes()
            expected=data(args.raw/f"state{stage}-ceramic-frame0-dpr2.gpu-rgba.bin")
            need(len(pixels)==len(expected)==786432,"PIXEL_SIZE_MISMATCH")
            differing=sum(1 for n in range(0,len(expected),4)
                          if expected[n:n+4]!=pixels[n:n+4])
            err=[abs(a-b) for a,b in zip(pixels,expected)]
            info={"stage":stage,"capture_sha256":sha(data(png)),
                "raw_capture_sha256":sha(pixels),"gpu_rgba_sha256":sha(expected),
                "different_pixels":differing,"max_channel_error":max(err),
                "mean_absolute_channel_error":sum(err)/len(err),
                "exact_all_pixels":differing==0}
            results.append(info)
            print("CP_I01_WESTON_FRAME",json.dumps(info),flush=True)
        viewer.wait(timeout=7)
        source.wait(timeout=7)
        need(viewer.returncode==source.returncode==0,"SOURCE_OR_VIEWER_FAILED")
        verdict=("QCHAIN_CPI01_HEADLESS_WESTON_COMPOSITOR_5_EXACT_PASS"
              if all(x["exact_all_pixels"] for x in results)
              else "QCHAIN_CPI01_HEADLESS_WESTON_PRESENTATION_OBSERVED_BOUNDED")
        report={"schema":"gnu6.qchain.cpi01_headless_capture.v1",
           "verdict":verdict,"backend":"Weston 15 headless GL over NVIDIA GPU",
           "gpu_compute_source":"CP-H2 cycle20 GPU outputs read back to host memfd",
           "wayland_compositor":"private Weston headless --debug kiosk",
           "hyprland_user_session_touched":False,"frames":results,
           "viewer_exit":viewer.returncode,"source_exit":source.returncode,
           "wall_seconds":round(time.monotonic()-start,3),
           "zero_copy":False,"photon_observed":False}
        (out/"qualification.json").write_text(json.dumps(report,indent=2)+"\n")
        print(verdict)

    finally:
        for process_name in ("viewer","source"):
            proc=locals().get(process_name)
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.wait(timeout=3)
        for h in handles:h.close()
        own_socket.unlink(missing_ok=True)
if __name__=="__main__":main()
