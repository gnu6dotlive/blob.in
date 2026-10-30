#!/usr/bin/env python3
"""Independent CP-JA7C oracle: reconstructs all facts directly, never imports runner."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps

REGIONS=((92,190,604,574),(810,190,1322,574))

def require(ok,code):
    if not ok: raise AssertionError(code)

def sha(b):
    return hashlib.sha256(b).hexdigest()

def read_region(full,box):
    x0,y0,x1,y1=box
    return full[y0:y1,x0:x1]

def pixel_metrics(actual,reference):
    d=np.abs(actual.astype(np.int16)-reference.astype(np.int16))
    return (int(np.any(d[:,:,:3]>3,axis=2).sum()),
            int(np.count_nonzero(d[:,:,3])),
            list(map(int,d.max(axis=(0,1)))))

def audit(root,baseline,receipt):
    screen_paths=sorted(root.glob("sample-*.png"))
    require(len(screen_paths)==8 and
            [p.name for p in screen_paths]==[f"sample-{i:02}.png" for i in range(8)],
            "EIGHT_UNALTERED_SAMPLE_NAMES_REQUIRED")
    app=(root/"viewer.stdout").read_text(errors="replace")
    client=(root/"viewer.stderr").read_text(errors="replace")
    server=(root/"weston-timeline-proto.log").read_text(errors="replace")
    compositor=(root/"weston.stdout").read_text(errors="replace")
    stages=json.loads(receipt.read_text())["stages"]
    require(len(stages)==5,"CANONICAL_STAGES_NOT_FIVE")
    refs=[]
    for material in ("ceramic","gel","metal","paper"):
        for j in (0,1):
            raw=(baseline/f"state4-{material}-frame{j}-dpr2.gpu-rgba.bin").read_bytes()
            require(len(raw)==512*384*4,"CANONICAL_FRAME_BYTES")
            refs.append((sha(raw), np.frombuffer(raw,np.uint8).reshape(384,512,4).copy()))
    records=re.findall(
        r"CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+) stage=(\d+) elapsed_us=(\d+)"
        r" received_to_submit_us=(\d+) epoch=(\d+) scene_sha256=([0-9a-f]{64})"
        r" rgba_sha256=([0-9a-f]{64}) dimensions=(\d+)x(\d+)", app)
    require(len(records)==120 and [int(r[0]) for r in records]==list(range(120)),
            "SOURCE_SEQUENCE_GAP_DUPLICATE")
    for r in records:
        seq=int(r[0])
        stage=int(r[1])
        require(stage==min(seq,4) and int(r[4])==stage and
                r[5]==stages[stage]["scene_sha256"] and
                r[7:]==("512","384"), "SOURCE_SCENE_OR_DIMENSION_DRIFT")
        if seq>=5:
            require(r[6]==refs[((seq-5)//12)%8][0],
                    "CANONICAL_FRAME_SHA_MISMATCH")
    samples=[]
    for idx,p in enumerate(screen_paths):
        with Image.open(p) as im:
            require(im.size==(1536,1024),"COMPOSITOR_CAPTURE_SIZE_CHANGED")
            full=np.asarray(ImageOps.flip(im.convert("RGBA")),dtype=np.uint8)
        ref_sha,ref=refs[idx]
        secondary=ref.copy()
        secondary[:,:16,:]=[0,0,0,255]
        left,right=(read_region(full,box) for box in REGIONS)
        primary_errors=pixel_metrics(left,ref)
        secondary_errors=pixel_metrics(right,secondary)
        require(primary_errors[:2]==(0,0) and secondary_errors[:2]==(0,0),
                "COMPOSITOR_PIXEL_BOUNDS_EXCEEDED_"+str(idx))
        require(pixel_metrics(left,secondary)[0]>0 and
                pixel_metrics(right,ref)[0]>0,
                "PRIMARY_SECONDARY_SURFACES_ALIASED_"+str(idx))
        samples.append({"index":idx,"phase":"post_rebuild" if idx>=3 else "pre_loss",
                        "png_sha256":sha(p.read_bytes()),"canonical_sha256":ref_sha,
                        "primary_max_rgba_delta":primary_errors[2],
                        "secondary_max_rgba_delta":secondary_errors[2]})
    marker="CPJA7CB_LOADER_INJECTED_VK_ERROR_DEVICE_LOST primary=1 present_id=41"
    require(client.count(marker)==1 and "dispatch=vkGetDeviceProcAddr synthetic=1" in client,
            "LOADER_FAULT_BOUNDARY_OR_WITNESS_NOT_EXACT")
    require(client.count("CPJA7CB_LOADER_NEGOTIATED interface=2")==2 and
            client.count("CPJA7CB_DEVICE_CREATED dispatch=1")==2 and
            client.count("CPJA7CB_LOADER_FIRST_FORWARD success_path=1")==2,
            "ACTUAL_VULKAN_LOADER_LAYER_DISPATCH_NOT_RECONCILED")
    require("CPJA7C_INJECTED_VK_ERROR_DEVICE_LOST" not in client,
            "HAL_SIDE_SYNTHETIC_INJECTION_NOT_ALLOWED")
    require(client.count("CPJA7C_WGPU_DEVICE_LOST_CALLBACK reason=Unknown detail=Device is lost")==1,
            "REAL_WGPU_DEVICE_LOST_CALLBACK_NOT_OBSERVED")
    events=[
        "CPJA7C_FAIL_CLOSED_PENDING_RECOVERY seq=40 completed=40 epoch=0",
        "CPJA7C_RECOVERY_BEGIN old_epoch=0 completed=40 pending_seq=Some(40)",
        "CPJA7C_RECOVERY_READY new_epoch=1 completed=40 pending_seq=Some(40)",
        "CPJA7C_RECOVERY_COMPLETE epochs=1 submitted=120",
        "CPI02_WGPU_STREAM_COMPLETE submitted=120"
    ]
    positions=[app.find(x) for x in events]
    require(-1 not in positions and positions==sorted(positions),
            "LOSS_RECOVERY_EVENT_ORDER_INVALID")
    require(app.count("CPJA7_TWO_SWAPS_ONE_DEVICE")==2,
            "SECOND_LOGICAL_DEVICE_NOT_INITIALIZED")
    ack=[(int(g),int(i)) for g,i in re.findall(
        r"CPJA6_TYPED_ACK generation=(\d+) present_id=(\d+) status=VK_SUCCESS",client)]
    require(len(ack)==240,"VK_TYPED_ACK_TOTAL_MISMATCH")
    for g,n in ((1,40),(2,40),(3,80),(4,80)):
        require([i for gen,i in ack if gen==g]==list(range(1,n+1)),
                f"VK_TYPED_GENERATION_{g}_SEQUENCE_MISMATCH")
    require("CPJA6_TYPED_ACK generation=1 present_id=41" not in client,
            "FALSE_ACK_AFTER_INJECTED_LOSS")
    requests=re.findall(
        r"wp_presentation#\d+\.feedback\(wl_surface#(\d+), new id wp_presentation_feedback#\d+\)",
        client)
    surface_ids=list(dict.fromkeys(requests))
    require(len(surface_ids)==4 and
            [requests.count(k) for k in surface_ids]==[40,40,80,80] and
            all(k in surface_ids[:2] for k in requests[:80]) and
            all(k in surface_ids[2:] for k in requests[80:]),
            "WAYLAND_SURFACE_RESURRECTION_INVALID")
    cp=re.findall(r"wp_presentation_feedback#\d+\.presented\(([^)]*)\)",client)
    cd=re.findall(r"wp_presentation_feedback#\d+\.discarded\(",client)
    sp=re.findall(r"ev wp_presentation_feedback@\d+\.presented\(([^)]*)\)",server)
    sd=re.findall(r"ev wp_presentation_feedback@\d+\.discarded\(",server)
    require(cp==sp and len(sp)==240 and not cd and not sd,
            "COMPOSITOR_PRESENTATION_EVENTS_DIVERGE")
    require("CPJA7B_TILE_PLUGIN_ACTIVE" in compositor and
            "CPJA7B_TILE_VIEWS count=2" in compositor,
            "PRIVATE_COMPOSITOR_NOT_TILED")
    return {
        "schema":"gnu6.qchain.cpja7cb_independent_oracle.v1",
        "verdict":"CPJA7CB_INDEPENDENT_LOADER_DISPATCH_FAULT_RECOVERY_PASS",
        "source_frame_count":120,
        "synthetic_hal_loss_count":1,
        "wgpu_device_lost_callbacks":1,
        "old_device_typed_ack":80,
        "new_device_typed_ack":160,
        "failed_present_ack":0,
        "new_wayland_surface_resources":surface_ids[2:],
        "old_wayland_surface_resources":surface_ids[:2],
        "wayland_server_presented":len(sp),
        "wayland_server_discarded":len(sd),
        "compositor_samples":samples,
        "actual_vendor_icd_device_loss":False,
        "loader_layer":"VK_LAYER_GNU6_cpja7cb_fault",
        "fault_injected_by_explicit_loader_layer":True,
        "multiple_in_flight":False,
        "hybrid60":False
    }

def main():
    p=argparse.ArgumentParser()
    for key in ("run","baseline","receipt","out"):
        p.add_argument("--"+key,required=True,type=Path)
    a=p.parse_args()
    require(not a.out.exists(),"REFUSE_OVERWRITE")
    report=audit(a.run,a.baseline,a.receipt)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"screenshots",len(report["compositor_samples"]))

if __name__=="__main__":
    main()
