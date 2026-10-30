#!/usr/bin/env python3
"""Independent private Weston GPU-source compositor-capture oracle.

A vertical flip is allowed ONLY when the compositor startup log itself
announces 'screen capture uses y-flip: yes'. No masks or color tolerances.
"""
import argparse, hashlib, json, re
from pathlib import Path
from PIL import Image, ImageOps

def sha(data):return hashlib.sha256(data).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)
def verify(cap, weston_log, raw, manifest, compute_log, cpu_receipt):
    log=weston_log.read_text()
    need("Output 'headless' enabled" in log,"WESTON_OUTPUT_NOT_OBSERVED")
    need("GL renderer: NVIDIA GeForce RTX 3070" in log,
         "WESTON_GPU_RENDERER_UNATTESTED")
    orientation="y-flip" if "screen capture uses y-flip: yes" in log else "normal"
    m=json.loads(manifest.read_text())
    cpu=json.loads(cpu_receipt.read_text())
    need(len(m["stages"])==len(cpu["stages"])==5,"FIVE_SCENES_REQUIRED")
    need(m["transport_version"]=="QCHAIN-GPU-FRAME-v1","WRONG_PROTOCOL")
    need(sha(compute_log.read_bytes())==m["compute_run_log_sha256"],
         "COMPUTE_RECEIPT_MISMATCH")
    need(sha(cpu_receipt.read_bytes())==m["cpu_receipt_sha256"],
         "CANONICAL_RECEIPT_MISMATCH")
    source=(cap/"source.log").read_text()
    viewer=(cap/"viewer.log").read_text()
    need("QCHAIN_GPU_SOURCE_COMPLETE gpu_readback_frames=5" in source,
         "GPU_SOURCE_INCOMPLETE")
    need("QCHAIN_GPU_ALL_FIVE_WGPU_FRAMES_SUBMITTED" in viewer,
         "WAYLAND_VIEWER_INCOMPLETE")

    sent=re.findall(r"QCHAIN_GPU_SOURCE_TRANSMITTED stage=(\d+) sha256=([0-9a-f]{64}) run_log_sha256=([0-9a-f]{64})",source)
    recv=re.findall(r"QCHAIN_GPU_IPC_RECEIVED stage=(\d+) rgba_sha256=([0-9a-f]{64})",viewer)
    rendered=re.findall(r"QCHAIN_GPU_WGPU_PRESENT_SUBMITTED stage=(\d+) epoch=(\d+) scene_sha256=([0-9a-f]{64}) rgba_sha256=([0-9a-f]{64}) dimensions=(\d+)x(\d+)",viewer)
    need(len(sent)==len(recv)==len(rendered)==5,"RECEIPT_COUNT_MISMATCH")
    result=[]
    for stage in range(5):
        label=str(stage)
        entry=m["stages"][stage]
        cpu_stage=cpu["stages"][stage]
        need(entry["stage"]==entry["epoch"]==cpu_stage["epoch"]==stage,
             "EPOCH_IDENTITY_DRIFT")
        need(entry["scene_sha256"]==cpu_stage["scene_sha256"]
             and entry["semantic_digest"]==cpu_stage["f2_semantic_digest"],
             "SEMANTIC_SCENE_BINDING_MISMATCH")
        needed=f"state{stage}-ceramic-frame0-dpr2.gpu-rgba.bin"
        need(entry["gpu_file"]==needed,"GPU_PIXEL_SOURCE_WRONG")
        gpu= (raw/needed).read_bytes()
        need(len(gpu)==786432 and sha(gpu)==entry["gpu_rgba_sha256"],
             "GPU_BYTES_CHANGED")
        need(sent[stage]==(label,sha(gpu),m["compute_run_log_sha256"]),
             "SOURCE_IPC_PROVENANCE_MISMATCH")
        need(recv[stage]==(label,sha(gpu)),"CLIENT_IPC_PROVENANCE_MISMATCH")
        need(rendered[stage]==(label,label,entry["scene_sha256"],
                                 sha(gpu),"512","384"),
             "WAYLAND_SUBMISSION_IDENTITY_MISMATCH")

        png=cap/f"stage-{stage:02}.png"
        with Image.open(png) as im:
            need(im.size==(512,384),"COMPOSITOR_GEOMETRY_MISMATCH")
            pix=im.convert("RGBA")
            raw_capture=pix.tobytes()
            normalized=ImageOps.flip(pix).tobytes() if orientation=="y-flip" else raw_capture
        need(len(normalized)==len(gpu),"CAPTURE_SIZE_INVALID")
        deltas=[p for p in range(196608)
                if normalized[4*p:4*p+4]!=gpu[4*p:4*p+4]]
        need(not deltas,f"WAYLAND_PIXEL_PARITY_RED_STAGE_{stage}")
        result.append({"stage":stage,"scene_sha256":entry["scene_sha256"],
            "gpu_rgba_sha256":sha(gpu),
            "capture_png_sha256":sha(png.read_bytes()),
            "capture_raw_rgba_sha256":sha(raw_capture),
            "normalized_capture_sha256":sha(normalized),
            "normalization":orientation,
            "compared_pixels":196608,
            "pixel_difference":0,"exact":True})
    need(len({x["scene_sha256"] for x in result})==5,
         "SCENE_IDENTITY_COLLISION")
    return {"schema":"gnu6.qchain.cpi01_weston_independent.v1",
        "verdict":"QCHAIN_CPI01_HEADLESS_WESTON_5_FRAMES_NORMALIZED_PIXEL_EXACT_PASS",
        "backend":"Weston 15 isolated headless GL on NVIDIA",
        "normalization":orientation,
        "frame_captures":5,
        "total_pixels_exact":5*196608,"pixel_errors":0,
        "user_hyprland_not_touched":True,
        "weston_debug_only_isolated_socket":True,
        "gpu_memfd_readback":True,"zero_copy":False,
        "wayland_surface_submit_verified":True,
        "physical_photon_observation":False,
        "continuous_60fps":"NOT_RUN",
        "stages":result}

def main():
    p=argparse.ArgumentParser()
    for k in ("captures","weston_log","raw","manifest","compute_log","cpu_receipt","out"):
        p.add_argument("--"+k.replace("_","-"),required=True,type=Path)
    a=p.parse_args()
    need(not a.out.exists(),"REFUSE_OVERWRITE")
    r=verify(a.captures,a.weston_log,a.raw,a.manifest,a.compute_log,a.cpu_receipt)
    a.out.write_text(json.dumps(r,indent=2)+"\n")
    print(r["verdict"],"frames",r["frame_captures"],
          "pixels",r["total_pixels_exact"],"orientation",r["normalization"])
if __name__=="__main__":main()
