#!/usr/bin/env python3
"""Independent CP-JA5 patched wgpu-hal typed Vulkan present-wait oracle.
Binds to real CP-F compute frames and Weston screenshot witness.
HAL logs are diagnostics, not signed driver telemetry.
"""
import argparse,hashlib,json,re,statistics
from pathlib import Path
import qchain_cpi02_independent_oracle as pixels

def need(ok,why):
    if not ok:raise ValueError(why)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,baseline,receipt,patch):
    pixel=pixels.verify(root,baseline,receipt)
    log=(root/"viewer.stderr").read_text()
    stdout=(root/"viewer.stdout").read_text()
    server=(root/"weston-timeline-proto.log").read_text()
    need("CPJA5_HAL_DEVICE_EXTENSIONS_ENABLE VK_KHR_present_id VK_KHR_present_wait" in log,
         "LOGICAL_DEVICE_FEATURES_NOT_ENABLED")
    ids=[int(i) for i in re.findall(
        r"CPJA5_HAL_TYPED_PRESENT_ACK present_id=(\d+) status=VK_SUCCESS swapchain_generation=local",log)]
    need(ids==list(range(1,121)),"TYPED_PRESENT_ID_SEQUENCE_MISMATCH")
    need("CPJA5_HAL_PRESENT_WAIT_TIMEOUT" not in log
         and "CPJA5_HAL_PRESENT_WAIT_ERROR" not in log,"TYPED_WAIT_ERROR")
    seq=[int(i) for i in re.findall(r"CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+)",stdout)]
    need(seq==list(range(120)),"WGPU_PRESENT_SEQUENCE_MISMATCH")

    client=re.findall(r"wp_presentation_feedback#\d+\.presented\(([^)]*)\)",log)
    weston=re.findall(r"ev wp_presentation_feedback@\d+\.presented\(([^)]*)\)",server)
    requested=re.findall(r" -> wp_presentation#\d+\.feedback\(",log)
    discarded=re.findall(r"wp_presentation_feedback#\d+\.discarded\(",log)
    need(len(client)==len(weston)==len(requested)==120,
         "WAYLAND_FEEDBACK_CLIENT_SERVER_COUNT_DRIFT")
    need(client==weston,"WAYLAND_CLIENT_SERVER_TIMESTAMP_DRIFT")
    need(len(discarded)==0,"WAYLAND_DISCARDED_PRESENTATION")
    assert pixel["rendered_frames"]==120
    need(pixel["exact_compositor_samples"]==8 and pixel["pixel_differences"]==0,
         "COMPOSITOR_CAPTURE_MISMATCH")
    src=(patch/"src/vulkan/swapchain/native.rs").read_text()
    adapter=(patch/"src/vulkan/adapter.rs").read_text()
    need("wait.wait_for_present(self.raw, present_id, 5_000_000_000)" in src,
         "VENDORED_HAL_TYPED_WAIT_SOURCE_MISSING")
    need("vk::PresentIdKHR::default().present_ids(&ids)" in src,
         "VENDORED_HAL_PRESENT_ID_SOURCE_MISSING")
    need("gnu6-cpja5-present-wait" in adapter,"DEVICE_FEATURE_GATE_MISSING")
    return {"schema":"gnu6.qchain.cpja5_oracle.v1",
       "verdict":"QCHAIN_CPJA5_WGPU_HAL_TYPED_120_OF_120_WESTON_EXACT_PASS",
       "renderer":"wgpu 30.0.1 with vendored patched wgpu-hal 30.0.1",
       "gpu_compute_frames":120,"wgpu_present_calls":120,
       "native_vulkan_wait_success":len(ids),
       "wayland_client_presented":len(client),
       "wayland_server_presented":len(weston),
       "distinct_present_ids":len(set(ids)),
       "no_sentinel":True,"captured_exact_frames":8,
       "exact_pixels_compared":8*512*384,
       "no_pixel_differences":True,
       "source_vendor_sha256":sha(patch/"src/vulkan/swapchain/native.rs"),
       "source_adapter_sha256":sha(patch/"src/vulkan/adapter.rs"),
       "client_trace_sha256":sha(root/"viewer.stderr"),
       "server_trace_sha256":sha(root/"weston-timeline-proto.log"),
       "full_gpu_driver_trace":"NOT_RUN","physical_photons":"NOT_RUN",
       "actual_60fps":"NOT_QUALIFIED","zero_copy":False}

def main():
    p=argparse.ArgumentParser()
    for n in ("run","baseline","receipt","patch","out"):
        p.add_argument("--"+n,required=True,type=Path)
    a=p.parse_args()
    need(not a.out.exists(),"REFUSE_OVERWRITE")
    r=verify(a.run,a.baseline,a.receipt,a.patch)
    a.out.write_text(json.dumps(r,indent=2)+"\n")
    print(r["verdict"],"ids",r["native_vulkan_wait_success"],
          "server",r["wayland_server_presented"],
          "client",r["wayland_client_presented"])
if __name__=="__main__":main()
