#!/usr/bin/env python3
"""CP-JA7C strict production acceptance: injected WSI loss, wgpu rebuild, compositor."""
import hashlib
import json
import os
import re
import time

def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)

def verify_recovery(root, samples, started):
    require("CPJA7C_INJECT_LOST_AT" not in os.environ,
            "OLD_SYNTHETIC_INJECTION_MUST_BE_DISABLED")
    client = (root / "viewer.stderr").read_text(errors="replace")
    stdout = (root / "viewer.stdout").read_text()
    server = (root / "weston-timeline-proto.log").read_text(errors="replace")
    compositor = (root / "weston.stdout").read_text(errors="replace")
    require(client.count("CPJA7CB_LOADER_INJECTED_VK_ERROR_DEVICE_LOST primary=1 present_id=41") == 1,
            "LOADER_DISPATCH_DEVICE_LOST_NOT_OBSERVED")
    require(client.count("CPJA7CB_LOADER_NEGOTIATED") >= 1 and
            client.count("CPJA7CB_DEVICE_CREATED dispatch=1") == 2 and
            client.count("CPJA7CB_LOADER_FIRST_FORWARD success_path=1") == 2,
            "ACTUAL_VULKAN_LOADER_DISPATCH_NOT_QUALIFIED")
    require("CPJA7C_INJECTED_VK_ERROR_DEVICE_LOST" not in client,
            "OLD_HAL_SYNTHETIC_FAULT_CONTAMINATES_RUN")
    require(client.count("CPJA7C_WGPU_DEVICE_LOST_CALLBACK reason=Unknown") == 1,
            "ACTUAL_WGPU_CALLBACK_MISSING")
    markers = (
        "CPJA7C_FAIL_CLOSED_PENDING_RECOVERY seq=40 completed=40 epoch=0",
        "CPJA7C_RECOVERY_BEGIN old_epoch=0 completed=40 pending_seq=Some(40)",
        "CPJA7C_RECOVERY_READY new_epoch=1 completed=40 pending_seq=Some(40)",
        "CPJA7C_RECOVERY_COMPLETE epochs=1 submitted=120",
        "CPI02_WGPU_STREAM_COMPLETE submitted=120",
    )
    require(all(marker in stdout for marker in markers),
            "DEVICE_RECOVERY_SEQUENCE_UNPROVEN")
    require(stdout.count("CPJA7_TWO_SWAPS_ONE_DEVICE") == 2,
            "LOGICAL_DEVICE_REBUILD_NOT_OBSERVED")
    require(stdout.count("CPJA7C_RECOVERY_BEGIN") == 1,
            "UNBOUNDED_RECOVERY_RETRY")
    ack = [(int(g), int(i)) for g,i in re.findall(
        r"CPJA6_TYPED_ACK generation=(\d+) present_id=(\d+) status=VK_SUCCESS",
        client)]
    expected = {1:40, 2:40, 3:80, 4:80}
    for generation, count in expected.items():
        require([i for g,i in ack if g == generation] ==
                list(range(1,count+1)),
                "VULKAN_ACK_MISMATCH_GENERATION_"+str(generation))
    require(len(ack) == 240 and
            "CPJA6_TYPED_ACK generation=1 present_id=41" not in client,
            "FAILED_PRESENT_FALSLY_ACKNOWLEDGED")
    requests = re.findall(
        r"wp_presentation#\d+\.feedback\(wl_surface#(\d+), new id wp_presentation_feedback#\d+\)", client)
    resource_ids = list(dict.fromkeys(requests))
    require(len(resource_ids) == 4 and
            [requests.count(i) for i in resource_ids] == [40,40,80,80] and
            all(i in resource_ids[:2] for i in requests[:80]) and
            all(i in resource_ids[2:] for i in requests[80:]),
            "WAYLAND_SURFACE_RECREATION_NOT_DEMONSTRATED")
    c_presented = re.findall(
        r"wp_presentation_feedback#\d+\.presented\(([^)]*)\)", client)
    c_discarded = re.findall(r"wp_presentation_feedback#\d+\.discarded\(", client)
    s_presented = re.findall(
        r"ev wp_presentation_feedback@\d+\.presented\(([^)]*)\)", server)
    s_discarded = re.findall(
        r"ev wp_presentation_feedback@\d+\.discarded\(", server)
    require(c_presented == s_presented and len(s_presented) == 240 and
            len(c_discarded) == len(s_discarded) == 0,
            "WAYLAND_PRESENTATION_FEEDBACK_NOT_RECONCILED")
    require("CPJA7B_TILE_PLUGIN_ACTIVE" in compositor and
            "CPJA7B_TILE_VIEWS count=2" in compositor,
            "COMPOSITOR_TWO_VIEWS_MISSING")
    require(len(samples) == 8 and
            all(s["primary"]["pixels_over_rgb3"] == 0 and
                s["secondary"]["pixels_over_rgb3"] == 0
                for s in samples), "VISUAL_REPLAY_DIFF_INVALID")
    report = {
        "schema":"gnu6.qchain.cpja7cb_loader_device_loss.v1",
        "verdict":"CPJA7CB_LOADER_DISPATCH_DEVICE_LOST_IN_PROCESS_RECOVERY_PASS",
        "fault":{"api":"Vulkan loader explicit layer dispatch vkQueuePresentKHR", "synthetic":True,
                 "vk_result":"VK_ERROR_DEVICE_LOST",
                 "generation":1, "present_id":41,"source_seq":40},
        "wgpu_device_lost_callback":"Unknown",
        "source_frames":120, "source_sequence_preserved":True,
        "old_swapchain_typed_ack":{"primary":40,"secondary":40},
        "new_swapchain_typed_ack":{"primary":80,"secondary":80},
        "failed_presentation_ack":False, "new_logical_device_epochs":1,
        "window_resource_ids":resource_ids,
        "wayland_per_surface_feedback_requests":[40,40,80,80],
        "wayland_presented":240,"wayland_discarded":0,
        "compositor_visible_samples":8,
        "max_rgb_delta_per_channel":3,
        "alpha_exact":True,"compositor_byte_exact_claim":False,
        "physical_gpu_device_lost":False,
        "loader_layer":"VK_LAYER_GNU6_cpja7cb_fault",
        "vendor_icd_returned_device_lost":False,
        "multiple_presents_in_flight":False,
        "cp03_hybrid60":False,"zero_copy":False,
        "elapsed_seconds":round(time.monotonic()-started,3),
        "samples":samples,
    }
    path=root/"run-verdict.json"
    require(not path.exists(),"REFUSE_OVERWRITE")
    path.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"elapsed_seconds",report["elapsed_seconds"],flush=True)
