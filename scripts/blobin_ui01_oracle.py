#!/usr/bin/env python3
"""Independent source trace + authentic Weston screenshot pixel witness."""
import argparse,hashlib,json
from pathlib import Path
from PIL import Image,ImageChops,ImageStat

def require(ok,name):
    if not ok:raise AssertionError(name)
def verify(root):
    root=Path(root)
    report=json.loads((root/"smoke-verdict.json").read_text())
    log=(root/"viewer.stdout").read_text(errors="replace")
    errors=(root/"viewer.stderr").read_text(errors="replace")
    trace=[json.loads(x) for x in (root/"ui-trace.jsonl").read_text().splitlines()]
    require(report["verdict"]=="UI01_NATIVE_VULKAN_INTERACTIVE_SCENE_SCOPED_PASS",
            "SPOOFED_PROBE_PASS")
    require(report["frames_submitted"]==180 and
            "BLOBIN_UI_PROBE_COMPLETE frames=180" in log,
            "MISSING_NATIVE_FRAME_COMPLETION")
    require("backend=Vulkan" in log and "adapter=NVIDIA GeForce RTX 3070" in log,
            "NOT_REAL_NVIDIA_VULKAN")
    require("panicked" not in errors and "BLOBIN_UI_INIT_FAILED" not in errors,
            "GPU_PANIC_OR_DRIVER_INIT_FAILED")
    expected=["SelectSurface(1)","ToggleInspector","SelectSurface(2)",
              "ToggleReducedMotion","ToggleReducedMotion","ToggleInspector"]
    actions=[row for row in trace if row["kind"]=="scripted_action"]
    require([x["data"]["action"] for x in actions]==expected,
            "UI_STATE_SEQUENCE_FALSIFIED")
    require([x["revision"] for x in actions]==list(range(1,7)),
            "NON_MONOTONIC_UI_REVISIONS")
    require(report["scripted_action_count"]==6,
            "WRONG_UI_ACTION_COUNT")
    require(report["real_pointer_mouse_interactions_automated"] is False and
            report["weston_presented_feedback_verified"] is False and
            report["steady_60fps_qualified"] is False and
            report["3d_implemented"] is False,"OVERCLAIMED_UI_RUNTIME")
    pics=[]
    for i,entry in enumerate(report["compositor_screenshots"],1):
        filename=f"sample-{i:02}.png"
        require(entry["file"]==filename,"SCREENSHOT_SEQUENCE_FALSIFIED")
        path=root/filename
        require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==entry["sha256"],
                "SCREENSHOT_BYTES_CHANGED")
        with Image.open(path) as im:
            require(im.size==(1536,1024),"SCREENSHOT_RESOLUTION_INVALID")
            window=im.convert("RGB").crop((105,170,1370,875))
            # Excludes desktop clock; a changing native UI must alter pixels.
            pics.append(window.copy())
            thumb=im.convert("RGB").resize((64,48)).tobytes()
            colors=len(set(zip(thumb[0::3],thumb[1::3],thumb[2::3])))
            require(colors>=80 and colors==entry["distinctive_thumbnail_colors"],
                    "SCREENSHOT_VARIETY_FALSIFIED")
    pixel_changes=[]
    for a,b in zip(pics,pics[1:]):
        delta=ImageChops.difference(a,b)
        value=sum(ImageStat.Stat(delta).mean)
        require(value>1.0,"ANIMATED_SCENE_UNCHANGED")
        pixel_changes.append(round(value,3))
    require(len({entry["sha256"] for entry in report["compositor_screenshots"]})==4,
            "COMPOSITOR_SAMPLES_NOT_DISTINCT")
    return {"schema":"blob.in.ui01.independent_oracle.v1",
            "verdict":"UI01_NATIVE_2D_MOTION_AND_LAYOUT_SCOPED_PASS",
            "source":"physical NVIDIA RTX 3070 / Vulkan / private Weston headless",
            "native_submitted_frames":180,
            "scripted_typed_actions":6,
            "pixel_change_mean_rgb_between_samples":pixel_changes,
            "sample_shas":[x["sha256"] for x in report["compositor_screenshots"]],
            "human_pointer_click_verified":False,
            "wp_presentation_feedback_verified":False,
            "steady_60fps":False,
            "3d_implemented":False}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    require(not a.out.exists(),"NO_ORACLE_OVERWRITE")
    report=verify(a.run)
    a.out.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],report["pixel_change_mean_rgb_between_samples"])
if __name__=="__main__":main()
