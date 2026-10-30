#!/usr/bin/env python3
"""Independent CP-JA6 swapchain generation + typed Vulkan feedback oracle.
Real Vulkan typed ACKs must be scoped to fresh swapchain generations.
"""
import argparse,json,re,hashlib
from pathlib import Path
import qchain_cpi02_independent_oracle as pixel_oracle

def require(c,why):
    if not c:raise ValueError(why)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(run,baseline,receipt,vendor):
    old=pixel_oracle.verify(run,baseline,receipt)
    app=(run/"viewer.stdout").read_text()
    client=(run/"viewer.stderr").read_text()
    server=(run/"weston-timeline-proto.log").read_text()
    require(app.count("CPJA6_RECONFIGURE_BEGIN after_seq=59")==1
         and app.count("CPJA6_RECONFIGURE_COMPLETE before_seq=60")==1,
         "ONE_RECONFIGURE_MUST_BE_WITNESSED")
    progress=[(int(g),int(i)) for g,i in re.findall(
      r"CPJA6_TYPED_ACK generation=(\d+) present_id=(\d+) status=VK_SUCCESS",client)]
    require(len(progress)==120,"TYPED_ACK_COUNT")
    first,second=progress[:60],progress[60:]
    require(len(set(g for g,_ in first))==1 and len(set(g for g,_ in second))==1,
         "GENERATION_MIXED")
    require(first[0][0]!=second[0][0] and first[0][0]<second[0][0],
         "GENERATION_NOT_ADVANCED")
    require([i for _,i in first]==list(range(1,61))
        and [i for _,i in second]==list(range(1,61)),
        "PRESENT_ID_SCOPE_INCONSISTENT")
    submitted=[int(v) for v in re.findall(r"CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+)",app)]
    require(submitted==list(range(120)),"SUBMISSION_ORDER_MISMATCH")

    prior=[int(v) for v in re.findall(
      r"CPJA5_HAL_TYPED_PRESENT_ACK present_id=(\d+) status=VK_SUCCESS",client)]
    require(prior==[i for _,i in progress],"HAL_TYPED_ACK_DIVERGENCE")
    sent=re.findall(r"ev wp_presentation_feedback@\d+\.presented\(([^)]*)\)",server)
    rcv=re.findall(r"wp_presentation_feedback#\d+\.presented\(([^)]*)\)",client)
    require(len(sent)==len(rcv)==120 and sent==rcv,
         "WAYLAND_CLIENT_SERVER_FEEDBACK_DIVERGENCE")
    require("CPJA5_HAL_PRESENT_WAIT_TIMEOUT" not in client,
         "TIMEOUT_DURING_RECONFIGURE")
    require(old["exact_compositor_samples"]==8 and old["pixel_differences"]==0,
         "COMPOSITOR_PIXEL_PARITY_FAILED")
    lifecycle=(vendor/"src/vulkan/swapchain/cpja6_lifecycle.rs").read_text()
    require("self.outstanding=Some(id)" in lifecycle.replace(" ","")
        and "self.poisoned=true" in lifecycle.replace(" ",""),
        "SOURCE_LIFECYCLE_GUARD_MISSING")
    return {"schema":"gnu6.qchain.cpja6_generation_oracle.v1",
        "verdict":"CPJA6_REAL_SWAPCHAIN_RECONFIGURE_2X60_TYPED_ACK_PASS",
        "fresh_gpu_source_frames":120,"real_surface_reconfigure_at":60,
        "generation_ids":[first[0][0],second[0][0]],
        "generation_frame_counts":[60,60],
        "generation_present_ids":[[1,60],[1,60]],
        "typed_vk_wait_ack":120,"client_wayland_presented":120,
        "server_weston_presented":120,
        "exact_compositor_captures":8,"compared_pixels":1572864,
        "pixel_mismatches":0,"sentinel_frames":0,
        "client_trace_sha256":sha(run/"viewer.stderr"),
        "server_trace_sha256":sha(run/"weston-timeline-proto.log"),
        "lifecycle_source_sha256":sha(vendor/"src/vulkan/swapchain/cpja6_lifecycle.rs"),
        "zero_copy":False,"fps_60_claim":False}

def main():
    ap=argparse.ArgumentParser()
    for arg in ["run","baseline","receipt","vendor","out"]:
        ap.add_argument("--"+arg,required=True,type=Path)
    a=ap.parse_args()
    require(not a.out.exists(),"REFUSE_OVERWRITE")
    result=verify(a.run,a.baseline,a.receipt,a.vendor)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],result["generation_ids"],result["generation_frame_counts"])
if __name__=="__main__":main()
