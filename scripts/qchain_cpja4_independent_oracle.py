#!/usr/bin/env python3
"""CP-JA4 independent source/typed-Vulkan/server-Wayland exact-sequence oracle.

Observes the app's vkWaitForPresentKHR result log; it is not a driver trace
or a signed attestation of implementation, so require pinned built source.
"""
import argparse,hashlib,json,re,statistics,math
from pathlib import Path
import qchain_cpja4_pixel_oracle as pixel_oracle
def need(ok,code):
    if not ok:raise ValueError(code)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pct(s,p):
    v=sorted(s);return v[min(len(v)-1,max(0,math.ceil(len(v)*p)-1))]
def verify(run,baseline,receipt,source):
    pixel=pixel_oracle.verify(run,baseline,receipt)
    stdout=(run/"viewer.stdout").read_text()
    client=(run/"viewer.stderr").read_text()
    server=(run/"weston-timeline-proto.log").read_text()
    canonical=json.loads(receipt.read_text())["stages"]
    need("CPJA4_DEVICE_READY" in stdout and
         "enabled=VK_KHR_swapchain,VK_KHR_present_id,VK_KHR_present_wait" in stdout and
         "present_features=true,true" in stdout,
         "VULKAN_DEVICE_EXTENSION_ATTESTATION_MISSING")
    need("vk::PresentIdKHR::default().present_ids(&ids)" in source.read_text()
         and ".wait_for_present(self.swapchain, id, 5_000_000_000)" in source.read_text(),
         "PINNED_VULKAN_WSI_SOURCE_NOT_REVIEWED")
    raw=re.findall(r"CPJA4_TYPED_PRESENT_ACK seq=(\d+) present_id=(\d+) scene_sha256=([0-9a-f]{64}) rgba_sha256=([0-9a-f]{64}) wait_result=VK_SUCCESS",stdout)
    need(len(raw)==120,"TYPED_ACK_COUNT")
    captures=json.loads((run/"run-verdict.json").read_text())
    source_frames=json.loads((run/"engine-ledger/timeline.json").read_text())["frames"]
    need(len(source_frames)==120,"REAL_GPU_STREAM_INCOMPLETE")

    for seq,(number,pid,scene,pixels) in enumerate(raw):
        stage=min(seq,4)
        need(int(number)==seq and int(pid)==seq+1,"PRESENT_ID_SEQUENCE_DRIFT")
        need(scene==canonical[stage]["scene_sha256"],"SCENE_SEMANTIC_IDENTITY_DRIFT")
        need(pixels==source_frames[seq]["pixel_sha256"],
             "TYPED_ACK_SOURCE_FRAME_HASH_DRIFT")
    need("CPJA4_TYPED_STREAM_COMPLETE source_frames=120 typed_acknowledgements=120 sentinel_frames=0" in stdout,
         "END_OF_STREAM_SILENT_INCOMPLETE")
    need("CPJA4_SENTINEL_PRESENT" not in stdout,"UNAUTHORIZED_SENTINEL")
    submit=re.findall(r"CPJA4_VK_PRESENT_SUBMITTED seq=(\d+)",stdout)
    need(len(submit)==120 and list(map(int,submit))==list(range(120)),
         "FRAME_SUBMISSIONS_DRIFT")
    waits=re.findall(r"CPJA4_WAIT_DURATION seq=(\d+) microseconds=(\d+)",stdout)
    need(len(waits)==120 and [int(s) for s,_ in waits]==list(range(120)),
         "BOUNDED_WAIT_DURATION_COUNT")
    duration=[int(d) for _,d in waits]
    need(all(0<=d<5_000_000 for d in duration),"WAIT_TIMEOUT_OR_NEGATIVE")
    server_presented=re.findall(r"ev wp_presentation_feedback@\d+\.presented\(([^)]*)\)",server)
    client_presented=re.findall(r"wp_presentation_feedback#\d+\.presented\(([^)]*)\)",client)
    requested=re.findall(r" -> wp_presentation#\d+\.feedback\(",client)
    discarded=re.findall(r"wp_presentation_feedback#\d+\.discarded",client)
    need(len(server_presented)==len(client_presented)==len(requested)==120,
         "WAYLAND_CLIENT_SERVER_PRESENTATION_MISMATCH")
    need(client_presented==server_presented,
         "WAYLAND_PRESENTED_TIMESTAMPS_NOT_INDEPENDENTLY_MATCHED")
    need(not discarded,"WAYLAND_FRAME_DISCARDED")
    need(pixel["exact_compositor_samples"]==8 and pixel["pixels_compared"]==1572864,
         "EIGHT_CAPTURE_COMPOSITOR_PARITY_FAILED")
    need(captures["source_exit"]==captures["viewer_exit"]==0,
         "NONZERO_PROCESS_EXIT")
    return {"schema":"gnu6.qchain.cpja4_independent_oracle.v1",
       "verdict":"CPJA4_VULKAN_PRESENT_WAIT_120_OF_120_EXACT_PASS",
       "native_presenter":"Ash Vulkan standalone, not wgpu-hal fork",
       "real_gpu_source_frames":120,
       "frame_seq_to_present_id":"presentId = frame.seq + 1",
       "per_frame_vk_wait_for_present_success":120,
       "wayland_feedback_client":120,"wayland_feedback_server":120,
       "sentinel_frames":0,"discarded_wayland_feedback":0,
       "compositor_exact_samples":8,"compositor_exact_pixels":1572864,
       "vk_wait_duration_us":{"median":statistics.median(duration),
           "p95":pct(duration,.95),"p99":pct(duration,.99),"max":max(duration)},
       "source_sha256":sha(source),"viewer_log_sha256":sha(run/"viewer.stdout"),
       "weston_protocol_sha256":sha(run/"weston-timeline-proto.log"),
       "compositor_capture_exact":True,
       "physical_photon_observation":"NOT_RUN",
       "wgpu_hal_integration":"NOT_RUN",
       "cross_vendor":"NOT_RUN",
       "fps_60_claim":False,"zero_copy":False}

def main():
    p=argparse.ArgumentParser()
    for f in ("run","baseline","receipt","source","out"):
        p.add_argument("--"+f,required=True,type=Path)
    a=p.parse_args()
    need(not a.out.exists(),"REFUSE_OVERWRITE")
    result=verify(a.run,a.baseline,a.receipt,a.source)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],"typed",result["per_frame_vk_wait_for_present_success"],
          "client",result["wayland_feedback_client"],
          "server",result["wayland_feedback_server"])
if __name__=="__main__":main()
