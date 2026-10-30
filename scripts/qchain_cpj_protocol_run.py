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

        targets=[9,21,33,45,57,69,81,93]
        for idx,target in enumerate(targets):
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                log=(root/"viewer.stdout").read_text(errors="replace")
                observed=[int(v) for v in re.findall(r"CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+)",log)]
                if target in observed:break
                if viewer.poll() is not None:break
                time.sleep(0.008)
            need(target in observed,"SAMPLE_TARGET_MISSED_"+str(target))
            before=set(root.glob("wayland-screenshot-*.png"))
            captured=subprocess.run(["weston-screenshooter"],cwd=root,env=env,
                          capture_output=True,text=True,timeout=4)
            need(captured.returncode==0 and
                 "unauthorized" not in (captured.stdout+captured.stderr).lower(),
                 "HEADLESS_SCREENSHOT_DENIED")
            after=set(root.glob("wayland-screenshot-*.png"))-before
            need(len(after)==1,"SCREENSHOT_NOT_UNIQUE")
            png=root/f"sample-{idx:02}.png"
            next(iter(after)).rename(png)
            with Image.open(png) as im:
                need(im.size==(512,384),"CAPTURE_DIMENSIONS_NOT_512X384")
                normalized=ImageOps.flip(im.convert("RGBA")).tobytes()
            variant=idx
            material=("ceramic","gel","metal","paper")[variant//2]
            original=a.baseline/f"state4-{material}-frame{variant%2}-dpr2.gpu-rgba.bin"
            expected=original.read_bytes()
            difference=sum(normalized[i:i+4]!=expected[i:i+4]
                           for i in range(0,len(expected),4))
            samples.append({"target_seq":target,"variant":variant,
                 "png_sha256":sha(png.read_bytes()),
                 "normalized_sha256":sha(normalized),
                 "expected_sha256":sha(expected),"pixel_differences":difference})
            print("CPI02_WESTON_SAMPLE",idx,"pixels_diff",difference,flush=True)
        viewer.wait(timeout=20)
        source.wait(timeout=10)
        need(viewer.returncode==source.returncode==0,"LIVE_SOURCE_OR_VIEWER_FAILED")

        log=(root/"viewer.stdout").read_text()
        records=re.findall(r"CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+) stage=(\d+) elapsed_us=(\d+) received_to_submit_us=(\d+) epoch=(\d+) scene_sha256=([0-9a-f]{64}) rgba_sha256=([0-9a-f]{64}) dimensions=(\d+)x(\d+)",log)
        need(len(records)==120 and [int(x[0]) for x in records]==list(range(120)),
             "STREAM_SEQUENCE_LOSS")
        need("CPI02_WGPU_STREAM_COMPLETE submitted=120" in log,"VIEWER_DID_NOT_COMPLETE")
        need(all(x["pixel_differences"]==0 for x in samples),"WESTON_SAMPLED_PIXEL_DIFF")
        stage_bytes=json.loads(a.receipt.read_text())["stages"]
        need(all(x[5]==stage_bytes[int(x[1])]["scene_sha256"] for x in records),
             "GPU_SEMANTIC_IDENTITY_LOST")
        timing=[int(x[2]) for x in records]
        intervals=[b-a for a,b in zip(timing,timing[1:])]
        report={"schema":"gnu6.qchain.cpi02_live_wayland.v1",
           "verdict":"QCHAIN_CPI02_120_LIVE_GPU_FRAMES_SEALED_IPC_SUBMITTED_8_EXACT_WESTON_SAMPLES_PASS",
           "gpu_frames_generated_in_single_session":120,
           "live_memfd_frame_receipts":120,
           "winit_wgpu_present_calls":120,
           "distinct_compositor_samples":len(samples),
           "sampled_pixels_exact":len(samples)*512*384,
           "sampler_pixel_errors":0,
           "submission_intervals_us":intervals,
           "viewer_elapsed_us":timing[-1],
           "viewer_exit":viewer.returncode,
           "source_exit":source.returncode,
           "wall_seconds":round(time.monotonic()-started,3),
           "compositor":"Weston 15 headless GL, --debug isolated",
           "orientation":"Weston-declared y-flip",
           "compositor_feedback_per_frame":False,
           "gpu_to_wayland_zero_copy":False,
           "fps_60_claim":False,
           "samples":samples}
        (root/"run-verdict.json").write_text(json.dumps(report,indent=2)+"\n")
        print(report["verdict"],"seconds",report["wall_seconds"],flush=True)

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
