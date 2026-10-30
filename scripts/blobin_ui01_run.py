#!/usr/bin/env python3
"""Private Weston + genuine Vulkan/wgpu interactive UI smoke; not a 60fps gate."""
import argparse,hashlib,json,os,subprocess,time
from pathlib import Path
from PIL import Image,ImageOps

def require(ok,code):
    if not ok:raise RuntimeError(code)
def run(root,binary,frames):
    require(root.is_dir() and not any(root.iterdir()),"NONEMPTY_RUN_ROOT")
    require(binary.is_file(),"BINARY_MISSING")
    runtime=Path(os.environ.get("XDG_RUNTIME_DIR","/run/user/1000"))
    display=f"blobin-ui01-{os.getpid()}"
    require(not (runtime/display).exists(),"WAYLAND_DISPLAY_ALREADY_EXISTS")
    env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime),WAYLAND_DISPLAY=display,
             RUST_BACKTRACE="1")
    for key in ("VK_LAYER_PATH","VK_INSTANCE_LAYERS","CPJA7CB_LOADER_FAULT"):
        env.pop(key,None)
    processes=[]
    start=time.monotonic()
    weston=None
    viewer=None
    try:
        weston=subprocess.Popen([
            "weston","--backend=headless","--renderer=gl","--shell=desktop",
            "--debug","-S",display,"--width=1536","--height=1024",
            "--no-config","--idle-time=0",f"--log={root/'weston.log'}",
        ],cwd=root,env=env,stdout=(root/"weston.stdout").open("wb"),
        stderr=subprocess.STDOUT,start_new_session=True)
        processes.append(weston)
        for _ in range(250):
            if (runtime/display).is_socket() or weston.poll() is not None:break
            time.sleep(0.02)
        require((runtime/display).is_socket() and weston.poll() is None,
                "PRIVATE_WESTON_NOT_STARTED")
        trace=root/"ui-trace.jsonl"
        viewer=subprocess.Popen([str(binary),f"--probe-frames={frames}",
            f"--trace={trace}"],cwd=root,env=env,
            stdout=(root/"viewer.stdout").open("wb"),
            stderr=(root/"viewer.stderr").open("wb"),start_new_session=True)
        processes.append(viewer)
        pics=[]
        for idx,target in enumerate((35,80,125,160),1):
            for _ in range(1200):
                lines=(root/"viewer.stdout").read_text(errors="replace")
                values=[int(s.split("frame=")[1].split()[0])
                        for s in lines.splitlines()
                        if s.startswith("BLOBIN_UI_SUBMITTED frame=")]
                if values and max(values)>=target:break
                require(viewer.poll() is None,"UI_EXITED_BEFORE_CAPTURE")
                time.sleep(0.008)
            require(values and max(values)>=target,"FRAME_CAPTURE_TARGET_TIMEOUT")
            previous=set(root.glob("wayland-screenshot-*.png"))
            capture=subprocess.run(["weston-screenshooter"],cwd=root,env=env,
                                   capture_output=True,text=True,timeout=5)
            require(capture.returncode==0
                    and "unauthorized" not in (capture.stdout+capture.stderr).lower(),
                    "WESTON_SCREENSHOT_DENIED")
            incoming=set(root.glob("wayland-screenshot-*.png"))-previous
            require(len(incoming)==1,"SCREENSHOT_NOT_CREATED")
            screenshot=root/f"sample-{idx:02}.png"
            incoming.pop().rename(screenshot)
            with Image.open(screenshot) as image:
                require(image.size==(1536,1024),"WRONG_COMPOSITOR_DIMENSIONS")
                # Weston headless screenshooter returns bottom-up framebuffer rows.
                upright=ImageOps.flip(image)
                upright.save(screenshot)
                thumb=upright.convert("RGB").resize((64,48)).tobytes()
                distinctive=len(set(zip(thumb[0::3],thumb[1::3],thumb[2::3])))
                require(distinctive>=80,"SCREENSHOT_TOO_UNIFORM")
            pics.append({"file":screenshot.name,
                         "sha256":hashlib.sha256(screenshot.read_bytes()).hexdigest(),
                         "distinctive_thumbnail_colors":distinctive})
            print("BLOBIN_UI_WESTON_CAPTURE_PASS",target,screenshot.name,flush=True)
        viewer.wait(timeout=30)
        stdout=(root/"viewer.stdout").read_text()
        require(viewer.returncode==0 and
                f"BLOBIN_UI_PROBE_COMPLETE frames={frames}" in stdout,
                "NATIVE_GPU_UI_PROBE_INCOMPLETE")
        trace_rows=[json.loads(s) for s in trace.read_text().splitlines()]
        scripted=[r for r in trace_rows if r["kind"]=="scripted_action"]
        require(len(scripted)==6 and
                [r["data"]["action"] for r in scripted]==[
                   "SelectSurface(1)","ToggleInspector","SelectSurface(2)",
                   "ToggleReducedMotion","ToggleReducedMotion","ToggleInspector"],
                "SCRIPTED_UI_INTERACTIONS_MISSING")
        require("backend=Vulkan" in stdout or "backend=VULKAN" in stdout
                or "backend=Vulkan" in stdout,
                "NON_VULKAN_RUNTIME_NOT_QUALIFIED")
        report={"schema":"blob.in.ui01.native_wayland_smoke.v1",
                "verdict":"UI01_NATIVE_VULKAN_INTERACTIVE_SCENE_SCOPED_PASS",
                "frames_submitted":frames,"scripted_action_count":len(scripted),
                "compositor_screenshots":pics,"gpu_binary_sha256":
                hashlib.sha256(binary.read_bytes()).hexdigest(),
                "elapsed_seconds":time.monotonic()-start,
                "real_pointer_mouse_interactions_automated":False,
                "weston_presented_feedback_verified":False,
                "steady_60fps_qualified":False,
                "3d_implemented":False}
        (root/"smoke-verdict.json").write_text(json.dumps(report,indent=2)+"\n")
        return report
    finally:
        for proc in reversed(processes):
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=3)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--binary",type=Path,required=True)
    p.add_argument("--frames",type=int,default=180)
    a=p.parse_args()
    report=run(a.root,a.binary,a.frames)
    print(report["verdict"],report["frames_submitted"],
          "screenshots",len(report["compositor_screenshots"]),flush=True)
if __name__=="__main__":main()
