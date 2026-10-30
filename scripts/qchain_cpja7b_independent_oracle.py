#!/usr/bin/env python3
"""Read-only independent verification of CP-JA7B capture pixels, logs and receipts."""
import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

# Coordinates were measured on Weston desktop; this oracle does not import
# the producer / runner or rely on its stored PASS decision.
BOXES = ((92, 190, 604, 574), (810, 190, 1322, 574))


def require(test, error):
    if not test:
        raise AssertionError(error)


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def decode(p):
    with Image.open(p) as image:
        require(image.size == (1536, 1024), "COMPOSITOR_GEOMETRY_CHANGED")
        return np.asarray(ImageOps.flip(image.convert("RGBA")), dtype=np.uint8)


def region(canvas, box):
    x0, y0, x1, y1 = box
    return canvas[y0:y1, x0:x1, :]


def pixel_error(actual, expected):
    delta = np.abs(actual.astype(np.int16) - expected.astype(np.int16))
    return int(np.any(delta[:, :, :3] > 3, axis=2).sum()), int(np.count_nonzero(delta[:, :, 3])), list(map(int,delta.max(axis=(0,1))))


def audit(run_dir, baseline):
    receipt = json.loads((run_dir / "run-verdict.json").read_text())
    positive = receipt["verdict"] == "CPJA7B_VISIBLE_DUAL_SURFACES_PASS"
    recovery = receipt["verdict"] == "CPJA7B_VISIBLE_DUAL_AND_PRIMARY_AFTER_SECONDARY_CLOSE_PASS"
    require(positive or recovery, "UNRECOGNIZED_PRODUCER_VERDICT")
    require(len(receipt["samples"]) == 8, "MISSING_SAMPLES")
    frame_refs = []
    for material in ("ceramic","gel","metal","paper"):
        for j in (0,1):
            raw = (baseline / f"state4-{material}-frame{j}-dpr2.gpu-rgba.bin").read_bytes()
            require(len(raw) == 512 * 384 * 4, "CANONICAL_DATA_MISSING")
            frame_refs.append((digest(raw), np.frombuffer(raw, dtype=np.uint8).reshape(384,512,4).copy()))
    statuses = []
    for idx, sample in enumerate(receipt["samples"]):
        screenshot = run_dir / f"sample-{idx:02}.png"
        require(digest(screenshot.read_bytes()) == sample["screenshot_sha256"],
                f"SCREENSHOT_HASH_FORGERY_{idx}")
        rgba = decode(screenshot)
        left = region(rgba, BOXES[0])
        right = region(rgba, BOXES[1])
        expected_hash, reference = frame_refs[idx]
        require(expected_hash == sample["canonical_rgba_sha256"], f"CANONICAL_HASH_FORGERY_{idx}")
        require(digest(left.tobytes()) == sample["primary_region_rgba_sha256"],
                f"PRIMARY_REGION_HASH_FORGERY_{idx}")
        require(digest(right.tobytes()) == sample["secondary_region_rgba_sha256"],
                f"SECONDARY_REGION_HASH_FORGERY_{idx}")
        lead = pixel_error(left, reference)
        require(lead[0] == 0 and lead[1] == 0, f"PRIMARY_PIXEL_ERROR_{idx}")
        stripped = reference.copy()
        stripped[:,:16,:] = [0,0,0,255]
        companion = pixel_error(right, stripped)
        closed = recovery and idx >= 4
        if closed:
            require(companion[0] > 0, f"SECONDARY_NOT_VISUALLY_RELEASED_{idx}")
            require(np.count_nonzero(right[:,:16,:3]) > 0,
                    f"SECONDARY_BLACK_STRIPE_STILL_VISIBLE_{idx}")
        else:
            require(companion[0] == 0 and companion[1] == 0,
                    f"SECONDARY_PIXEL_ERROR_{idx}")
            require(pixel_error(left,stripped)[0] > 0 and pixel_error(right,reference)[0] > 0,
                    f"DUAL_WINDOWS_NOT_DISTINCT_{idx}")
        statuses.append({"idx":idx, "phase":"recovered" if closed else "dual",
                         "primary_max_rgba":lead[2],
                         "secondary_max_rgba":companion[2],
                         "primary_invalid":lead[0], "secondary_invalid":companion[0]})
    trace = (run_dir / "viewer.stdout").read_text()
    records = re.findall(r"CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+) stage=(\d+).*?rgba_sha256=([0-9a-f]{64})", trace)
    require(len(records) == 120 and [int(r[0]) for r in records] == list(range(120)),
            "STREAM_GAP_OR_DUPLICATE")
    require(all(r[2] == frame_refs[((int(r[0])-5)//12)%8][0]
                for r in records if int(r[0]) >= 5),
            "FRAME_SOURCE_UNTRUSTWORTHY")
    expected_secondary = 60 if recovery else 120
    require(len(re.findall(r"CPJA7_SECONDARY_PRESENT seq=\d+",trace)) == expected_secondary,
            "SECONDARY_PRESENT_COUNT_CHANGED")
    require((("CPJA7_SECONDARY_RELEASE after_seq=59" in trace) == recovery),
            "RELEASE_MARKER_INCONSISTENT")
    require("CPI02_WGPU_STREAM_COMPLETE submitted=120" in trace,
            "COMPLETION_MARKER_MISSING")
    client = (run_dir / "viewer.stderr").read_text(errors="replace")
    server = (run_dir / "weston-timeline-proto.log").read_text(errors="replace")
    acks = [(int(g),int(seq)) for g,seq in re.findall(
        r"CPJA6_TYPED_ACK generation=(\d+) present_id=(\d+) status=VK_SUCCESS",client)]
    gens = sorted(set(g for g,_ in acks))
    require(len(gens) == 2, "TYPED_VK_GENERATIONS_MISSING")
    require([i for g,i in acks if g == gens[0]] == list(range(1,121)),
            "PRIMARY_TYPED_VK_ACK_MISSING")
    require([i for g,i in acks if g == gens[1]] == list(range(1,expected_secondary+1)),
            "SECONDARY_TYPED_VK_ACK_MISSING")
    require(len(acks)==120+expected_secondary, "TYPED_VK_ACK_COUNT_MISMATCH")
    require(not re.search(r"CPJA6_SWAPCHAIN_POISONED|CPJA5_HAL_PRESENT_WAIT_TIMEOUT",client),
            "UNQUALIFIED_TYPED_HAL_ERROR")
    requests = re.findall(
        r"wp_presentation#\d+\.feedback\(wl_surface#(\d+), new id wp_presentation_feedback#\d+\)",
        client)
    compositor = (run_dir / "weston.stdout").read_text(errors="replace")
    mapped = re.search(r"CPJA7B_TILE_VIEWS count=2 primary_id=(\d+) secondary_id=(\d+)",
                       compositor)
    require(mapped is not None,"SURFACE_IDENTITIES_MISSING")
    primary_id,secondary_id = mapped.groups()
    require(requests.count(primary_id)==120 and
            requests.count(secondary_id)==expected_secondary,
            "WAYLAND_FEEDBACK_REQUESTS_BY_SURFACE_MISMATCH")
    cp = re.findall(r"wp_presentation_feedback#\d+\.presented\(([^)]*)\)",client)
    cd = re.findall(r"wp_presentation_feedback#\d+\.discarded\(",client)
    sp = re.findall(r"ev wp_presentation_feedback@\d+\.presented\(([^)]*)\)",server)
    sd = re.findall(r"ev wp_presentation_feedback@\d+\.discarded\(",server)
    require(cp==sp and len(cd)==len(sd), "SERVER_CLIENT_FEEDBACK_DIVERGENCE")
    require(len(sp)+len(sd)==120+expected_secondary,
            "UNRESOLVED_COMPOSITOR_FEEDBACK")
    require(len(sd)==0, "COMPOSITOR_DISCARDED_A_VISIBLE_SURFACE")
    require("CPJA7B_TILE_PLUGIN_ACTIVE" in compositor
            and "CPJA7B_TILE_VIEWS count=2" in compositor,
            "TWO_MAPPED_VIEWS_NOT_PROVEN")
    if recovery:
        require("CPJA7B_TILE_VIEWS count=1" in compositor,
                "ONE_MAPPED_VIEW_TRANSITION_INCONSISTENT")
    return {"schema":"gnu6.qchain.cpja7b_independent_oracle.v1",
            "verdict": "CPJA7B_INDEPENDENT_VISUAL_RECOVERY_PASS" if recovery
                else "CPJA7B_INDEPENDENT_DUAL_VISIBILITY_PASS",
            "producer_verdict_sha256": digest((run_dir / "run-verdict.json").read_bytes()),
            "per_pixel_abs_rgb_bound":3,"screenshots":8,
            "mapped_window_transition":"2_to_1" if recovery else "2_only",
            "recorded_source_frames":120,
            "recorded_secondary_presents":expected_secondary,
            "typed_vk_ack_primary":120,
            "typed_vk_ack_secondary":expected_secondary,
            "typed_vk_generations":gens,
            "wayland_surface_feedback_requests":{"primary":requests.count(primary_id),
                "secondary":requests.count(secondary_id)},
            "weston_presented":len(sp),"weston_discarded":len(sd),
            "client_presented":len(cp),"client_discarded":len(cd),
            "full_vulkan_device_recovery_claim":False,
            "multiple_present_in_flight_claim":False,
            "samples":statuses}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--baseline",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=audit(a.run,a.baseline)
    require(not a.out.exists(), "ORACLE_OUTPUT_ALREADY_EXISTS")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"])


if __name__=="__main__":
    main()
