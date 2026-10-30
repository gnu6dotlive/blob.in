#!/usr/bin/env python3
"""BLOB-AC-03: isolated Weston seat -> winit -> gestures -> actual GPU swapchain readback.
Never injects events into the user's desktop. No compositor presentation claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path, data):
    path.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n", encoding="utf-8")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--binary",type=Path,required=True)
    p.add_argument("--module",type=Path,required=True)
    p.add_argument("--inside",action="store_true")
    a=p.parse_args()
    out=a.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    binary=a.binary.resolve()
    module=a.module.resolve()
    if not a.inside:
        # No host network exposure: fail rather than fall back to user's seat.
        result=subprocess.run(["unshare","-Urn",sys.executable,str(Path(__file__).resolve()),
           "--out",str(out),"--binary",str(binary),"--module",str(module),"--inside"],
           capture_output=True,text=True,timeout=40)
        (out/"isolation.stdout").write_text(result.stdout.rstrip("\n")+("\n" if result.stdout else ""))
        (out/"isolation.stderr").write_text(result.stderr.rstrip("\n")+("\n" if result.stderr else ""))
        print(result.stdout,end="",flush=True)
        if result.stderr: print(result.stderr,file=sys.stderr)
        return result.returncode
    subprocess.run(["ip","link","set","lo","up"],check=True,timeout=4)
    display="blob-ac03-private-"+str(os.getpid())
    runtime=Path(os.environ.get("XDG_RUNTIME_DIR","/run/user/1000"))
    env=os.environ.copy()
    env.update(WAYLAND_DISPLAY=display,BLOB_AC03_ISOLATED_COMPOSITOR="1",
               BLOBIN_AC02_ALLOW_GL="1",RUST_BACKTRACE="1")
    for key in ("VK_LAYER_PATH","VK_INSTANCE_LAYERS","CPJA7CB_LOADER_FAULT"):
        env.pop(key,None)
    procs=[]
    receipt={"program":"BLOB-AC-03","scope":"isolated Weston compositor + real winit delivery + GPU swapchain COPY_SRC, not compositor-presented frame",
             "namespace":"unshare -Urn; private loopback and unique Wayland socket",
             "physical_HID":False,"compositor_presentation_feedback":False,
             "client_binary_sha256":sha(binary),"weston_module_sha256":sha(module)}
    try:
        with (out/"weston.stdout.txt").open("wb") as stdout:
            server=subprocess.Popen(["weston","--backend=headless","--renderer=gl",
                "--shell=kiosk","--no-config","--width=940","--height=640",
                "--idle-time=0","-S",display,"--modules="+str(module),
                "--log="+str(out/"weston.log")],
                cwd=out,stdout=stdout,stderr=subprocess.STDOUT,env=env,start_new_session=True)
        procs.append(server)
        for _ in range(100):
            if (runtime/display).is_socket() or server.poll() is not None:break
            time.sleep(.03)
        if not (runtime/display).is_socket() or server.poll() is not None:
            raise RuntimeError("PRIVATE_WESTON_SOCKET_ABSENT")
        viewer_cmd=[str(binary),"--trace="+str(out/"winit-events.jsonl"),
                    "--run-ms=6900","--pixel-evidence-dir="+str(out)]
        with (out/"viewer.stdout.txt").open("wb") as so, (out/"viewer.stderr.txt").open("wb") as se:
            viewer=subprocess.Popen(viewer_cmd,cwd=out,stdout=so,stderr=se,
                                    env=env,start_new_session=True)
        procs.append(viewer)
        viewer.wait(timeout=18)
        if viewer.returncode:raise RuntimeError("NATIVE_VIEWER_EXIT="+str(viewer.returncode))
        if server.poll() is not None:raise RuntimeError("COMPOSITOR_EARLY_EXIT")
        raw=[out/(stage+".rgba") for stage in ("before","preview","after")]
        if not all(f.exists() for f in raw):
            raise RuntimeError("MISSING_GPU_SWAPCHAIN_READBACK: "+str([f.name for f in raw if not f.exists()]))
        events=[json.loads(s) for s in (out/"winit-events.jsonl").read_text().splitlines()]
        ingress=[e for e in events if e.get("kind")=="ingress"]
        routed=[e for e in events if e.get("kind")=="receipt"]
        begins=[e for e in events if e.get("kind")=="gesture_begin"]
        previews=[e for e in events if e.get("kind")=="gesture_preview"]
        commits=[e for e in events if e.get("kind")=="gesture_reorder"]
        images=[e for e in events if e.get("kind")=="gpu_swapchain_copy"]
        summary=[e for e in events if e.get("kind")=="summary"]
        if not(
            [e["serial"] for e in ingress]==list(range(1,7))
            and [e["serial"] for e in routed]==list(range(1,7))
            and [e["event"] for e in ingress]==["cursor_moved","cursor_moved","mouse_down","cursor_moved","cursor_moved","mouse_up"]
            and len(begins)==1 and begins[0]["serial"]==3
            and [e["dx"] for e in previews]==[55.0,140.0] and all(e["dy"]==0.0 for e in previews)
            and [e["serial"] for e in commits]==[6] and commits[0]["revision"]==2
            and len(summary)==1 and summary[0]["gesture_commits"]==1
            and summary[0]["activation_count"]==0 and summary[0]["ui_revision"]==2
            and summary[0]["frame_submissions"]>=4
            and {e["stage"] for e in images}=={"before","preview","after"}
        ):
            raise RuntimeError("GESTURE_OR_FRAME_ORACLE_MISMATCH")
        # Actual-copy pixel images, not compositor framebuffer nor reproduced geometry.
        from PIL import Image
        px={}
        expected_color_formats={"Bgra8Unorm","Bgra8UnormSrgb","Rgba8Unorm","Rgba8UnormSrgb"}
        for event in images:
            stage=event["stage"]
            if event["format"] not in expected_color_formats:
                raise RuntimeError("UNSUPPORTED_GPU_SWAPCHAIN_COLOR_FORMAT")
            width=int(event["width"]);height=int(event["height"])
            if (width,height)!=(940,640):
                raise RuntimeError("UNEXPECTED_SWAPCHAIN_DIMENSIONS")
            data=(out/(stage+".rgba")).read_bytes()
            if len(data)!=width*height*4:
                raise RuntimeError("MALFORMED_GPU_BUFFER")
            fmt="BGRA" if event["format"].startswith("Bgra") else "RGBA"
            pic=Image.frombytes("RGBA",(width,height),data,"raw",fmt)
            px[stage]={"left":pic.getpixel((120,145)), "right":pic.getpixel((550,145)),
                       "top_background":pic.getpixel((10,10)),
                       "image_sha256_raw":sha(out/(stage+".rgba"))}
            pic.save(out/(stage+".png"),"PNG")
            (out/(stage+".rgba")).unlink() # compressed evidence retained; raw hashes preserved
        stage_events={e["stage"]:e for e in images}
        if [e["stage"] for e in images] != ["before","preview","after"] or (
            [stage_events[k]["ui_revision"] for k in ("before","preview","after")] != [1,1,2]
        ) or (
            [stage_events[k]["gesture_commits"] for k in ("before","preview","after")] != [0,0,1]
        ):
            raise RuntimeError("GPU_STAGE_REVISION_OR_ORDER_MISMATCH")
        def isblue(c):return c[2]>c[0]*1.6 and c[1]>c[0]*1.5 and c[2]>150 and c[3]>=250
        def isorange(c):return c[0]>c[2]*2 and c[0]>c[1]*1.4 and c[0]>130 and c[3]>=250
        if not (
            isblue(px["before"]["left"]) and isorange(px["before"]["right"]) and
            isorange(px["after"]["left"]) and isblue(px["after"]["right"]) and
            px["preview"]["left"]!=px["after"]["left"] and
            px["before"]["left"]!=px["after"]["left"]
        ):
            raise RuntimeError("PIXEL_COLOR_OR_POSITION_ORACLE_MISMATCH: "+str(px))
        # Source trace is parsed independently of the injected step logs.
        steps=(out/"weston.stdout.txt").read_text()
        expected=["BLOB_AC03_PRIVATE_SEAT_READY","BLOB_AC03_COMPOSITOR_STEP down A",
                  "BLOB_AC03_COMPOSITOR_STEP preview dx55","BLOB_AC03_COMPOSITOR_STEP preview dx140",
                  "BLOB_AC03_COMPOSITOR_STEP up A"]
        if not all(x in steps for x in expected):
            raise RuntimeError("COMPOSITOR_STEP_PROVENANCE_MISSING")
        receipt.update(
            verdict="COMPOSITOR_DELIVERED_GESTURE_PLUS_GPU_CLIENT_PIXEL_PASS",
            ingress_count=len(ingress),router_receipts=len(routed),
            begins=len(begins),previews=len(previews),commits=len(commits),
            initial_ui_revision=1,final_ui_revision=2,
            frame_submissions=summary[0]["frame_submissions"],
            pixel_provenance="wgpu swapchain texture COPY_SRC before queue.present; client rendered GPU pixels only",
            pixels=px,
            images={name:sha(out/(name+".png")) for name in ("before","preview","after")},
            winit_trace_sha256=sha(out/"winit-events.jsonl"),
            weston_stdout_sha256=sha(out/"weston.stdout.txt"))
    except Exception as exc:
        receipt["verdict"]="HOLD"
        receipt["reason"]=str(exc)
        print("AC03_HOLD",str(exc),file=sys.stderr,flush=True)
    finally:
        for proc in reversed(procs):
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
        write_json(out/"isolated-receipt.json",receipt)
        print(json.dumps(receipt,indent=2),flush=True)
    return 0 if receipt["verdict"].endswith("_PASS") else 1

if __name__=="__main__":
    sys.exit(main())
