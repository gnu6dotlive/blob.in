#!/usr/bin/env python3
"""Independent CP-JA7E-C 300-frame source / Vulkan / Wayland / pixel oracle."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps

REGIONS=((92,190,604,574),(810,190,1322,574))
TARGETS=(9,45,81,117,153,189,225,261)
def need(ok,code):
    if not ok:raise AssertionError(code)
def sha(blob):return hashlib.sha256(blob).hexdigest()
def groups(s,p):return [tuple(int(x) for x in v) for v in re.findall(p,s)]
def verify(root,baseline,receipt):
    app=(root/"viewer.stdout").read_text(errors="replace")
    client=(root/"viewer.stderr").read_text(errors="replace")
    weston=(root/"weston.stdout").read_text(errors="replace")
    server=(root/"weston-timeline-proto.log").read_text(errors="replace")
    canonical=json.loads(receipt.read_text())["stages"]
    need(len(canonical)==5,"ORACLE_STAGES_NOT_FIVE")
    refs=[]
    for material in ("ceramic","gel","metal","paper"):
        for index in (0,1):
            p=baseline/f"state4-{material}-frame{index}-dpr2.gpu-rgba.bin"
            b=p.read_bytes()
            need(len(b)==512*384*4,"ORACLE_CANONICAL_BYTE_LENGTH")
            refs.append((sha(b),np.frombuffer(b,np.uint8).reshape(384,512,4).copy()))
    source=re.findall(
       r"CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+) stage=(\d+) elapsed_us=(\d+)"
       r" received_to_submit_us=(\d+) epoch=(\d+) scene_sha256=([0-9a-f]{64})"
       r" rgba_sha256=([0-9a-f]{64}) dimensions=(\d+)x(\d+)",app)
    need(len(source)==300 and [int(x[0]) for x in source]==list(range(300)),
         "ORACLE_SOURCE_SEQUENCE_NOT_300")
    for r in source:
        seq,stage=int(r[0]),int(r[1])
        need(stage==min(seq,4) and int(r[4])==stage
             and r[5]==canonical[stage]["scene_sha256"]
             and r[-2:]==("512","384"),"ORACLE_SCENE_SEMANTICS")
        if seq>=5:
            need(r[6]==refs[((seq-5)//12)%8][0],
                 "ORACLE_CANONICAL_SOURCE_SHA_DRIFT")
    images=sorted(root.glob("sample-*.png"))
    need(len(images)==8 and [p.name for p in images]==
         [f"sample-{j:02}.png" for j in range(8)],
         "ORACLE_EIGHT_SCREENSHOTS_MISSING")
    visuals=[]
    for j,p in enumerate(images):
        with Image.open(p) as picture:
            need(picture.size==(1536,1024),"ORACLE_COMPOSITOR_GEOMETRY")
            rgba=np.asarray(ImageOps.flip(picture.convert("RGBA")),dtype=np.uint8)
        target=TARGETS[j]
        source_sha,ref=refs[((target-5)//12)%8]
        secondary=ref.copy()
        secondary[:,:16]=np.array([0,0,0,255],dtype=np.uint8)
        deltas=[]
        for (x0,y0,x1,y1),expected in zip(REGIONS,(ref,secondary)):
            observed=rgba[y0:y1,x0:x1]
            need(observed.shape==expected.shape,"ORACLE_REGION_SHAPE")
            d=np.abs(observed.astype(np.int16)-expected.astype(np.int16))
            need(not np.any(d[:,:,:3]>3) and not np.any(d[:,:,3]),
                 f"ORACLE_RGBA_DRIFT_CAPTURE_{j}")
            deltas.append([int(v) for v in d.max(axis=(0,1))])
        need(np.any(rgba[190:574,92:108,:3]!=
                    rgba[190:574,810:826,:3]),
             "ORACLE_PRIMARY_SECONDARY_INDISTINGUISHABLE")
        visuals.append({"sample":j,"target_seq":target,
                        "sha256_png":sha(p.read_bytes()),
                        "canonical_sha256":source_sha,
                        "primary_rgba_max_delta":deltas[0],
                        "secondary_rgba_max_delta":deltas[1]})
    issue=groups(client,r"CPJA7DB_ASYNC_ISSUED generation=(\d+) present_id=(\d+) pending=(\d+) cap=2")
    wait=groups(client,r"CPJA7DB_WORKER_WAIT_SUCCESS generation=(\d+) present_id=(\d+) observation=(\d+)")
    delivered=groups(client,r"CPJA7DB_WORKER_DELIVER generation=(\d+) present_id=(\d+) arrival=(\d+)")
    ack=groups(client,r"CPJA7DB_ASYNC_TYPED_ACK generation=(\d+) present_id=(\d+) pending=(\d+)")
    nonfifo=groups(client,r"CPJA7DB_OUT_OF_ORDER_TYPED_ACK generation=(\d+) present_id=(\d+) previous_oldest=Some\((\d+)\)")
    batches=groups(client,r"CPJA7DB_DELIVERY_REORDERED generation=(\d+) old=(\d+) new=(\d+) proof=two_real_vk_wait_success")
    expected={(g,id) for g in (1,2) for id in range(1,301)}
    for name,records in (("issue",issue),("wait",wait),("delivered",delivered),("ack",ack)):
        need(len(records)==600 and {(g,id) for g,id,_ in records}==expected,
             f"ORACLE_VULKAN_{name}_WRONG")
    need(len(nonfifo)==300 and
         {(g,id,old) for g,id,old in nonfifo}==
         {(g,odd+1,odd) for g in (1,2) for odd in range(1,301,2)},
         "ORACLE_NONFIFO_ACK_NOT_JUSTIFIED")
    need(len(batches)==300 and
         {(g,old,new) for g,old,new in batches}==
         {(g,odd,odd+1) for g in (1,2) for odd in range(1,301,2)},
         "ORACLE_WORKER_REORDER_MISSING")
    need(all(p in (1,2) for _,_,p in issue),"ORACLE_INFLIGHT_CAP")
    for gen in (1,2):
        need([id for g,id,_ in issue if g==gen]==list(range(1,301)),
             "ORACLE_ISSUE_NOT_MONOTONIC")
        need([id for g,id,_ in delivered if g==gen]==
             [y for odd in range(1,301,2) for y in (odd+1,odd)],
             "ORACLE_DELIVERY_REORDER_NOT_REAL")
    cp=re.findall(r"wp_presentation_feedback#\d+\.presented\(([^)]*)\)",client)
    sp=re.findall(r"ev wp_presentation_feedback@\d+\.presented\(([^)]*)\)",server)
    need(len(cp)==len(sp)==600 and Counter(cp)==Counter(sp)
         and not re.search(r"wp_presentation_feedback#\d+\.discarded\(",client)
         and not re.search(r"ev wp_presentation_feedback@\d+\.discarded\(",server),
         "ORACLE_WAYLAND_FEEDBACK_RECONCILIATION")
    requests=re.findall(
      r"wp_presentation#\d+\.feedback\(wl_surface#(\d+), new id wp_presentation_feedback#\d+\)",
      client)
    ids=list(dict.fromkeys(requests))
    need(len(ids)==2 and [requests.count(id) for id in ids]==[300,300],
         "ORACLE_SURFACE_IDENTITIES_NOT_TWO")
    need("CPJA7B_TILE_PLUGIN_ACTIVE" in weston
         and "CPJA7B_TILE_VIEWS count=2" in weston,
         "ORACLE_PRIVATE_COMPOSITOR_MISSING")
    need("CPI02_WGPU_STREAM_COMPLETE submitted=300" in app and
         "CPJA7C_RECOVERY_BEGIN" not in app and
         "CPJA7CB_LOADER_INJECTED" not in client,
         "ORACLE_UNEXPECTED_GPU_FAULT_OR_MISSING_COMPLETE")
    stops=re.findall(r"CPJA7DB_WORKER_STOP generation=(\d+) pending_discarded=(\d+) ready_unclaimed=(\d+)",client)
    need(len(stops)==2 and all(a==b=="0" for _,a,b in stops),
         "ORACLE_WORKER_RESOURCES_NOT_CLOSED")
    profile=re.findall(r"CPJA7E_WORKER_METRICS generation=\d+ profile=(latency|balanced|eco)",client)
    need(len(profile)==2 and profile[0]==profile[1],
         "ORACLE_WORKER_PROFILES_DIFFER")
    lat=sorted(int(r[3]) for r in source if int(r[0])>=5)
    def q(t):
        f=(len(lat)-1)*t
        i=int(f)
        return round(lat[i]*(1-(f-i))+lat[min(len(lat)-1,i+1)]*(f-i),2)
    p95,p99=q(.95),q(.99)
    need(p95<=100000 and p99<=200000,"ORACLE_RECEIVE_SUBMIT_LATENCY_OVER_BOUND")
    return {"schema":"gnu6.qchain.cpja7ec_independent.v1",
            "verdict":"CPJA7EC_INDEPENDENT_NATIVE_300FRAME_PASS",
            "profile":profile[0],"source_frames":300,
            "vulkan_issues":600,"vulkan_real_wait_success":600,
            "vulkan_typed_ack":600,"reordered_typed_ack":300,
            "wayland_server_presented":600,"wayland_client_presented":600,
            "p95_us":p95,"p99_us":p99,"screenshots":visuals,
            "true_driver_device_loss":False,"zero_copy":False}
def main():
    ap=argparse.ArgumentParser()
    for key in ("run","baseline","receipt","out"):
        ap.add_argument("--"+key,required=True,type=Path)
    x=ap.parse_args()
    need(not x.out.exists(),"ORACLE_OVERWRITE_DENIED")
    r=verify(x.run,x.baseline,x.receipt)
    x.out.write_text(json.dumps(r,indent=2)+"\n")
    print(r["verdict"],"profile",r["profile"],"frames",r["source_frames"])
if __name__=="__main__":main()
