#!/usr/bin/env python3
"""Read-only QCHAIN software compositor oracle. Hyprland 18px corner mask is explicit."""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

WIDTH, HEIGHT, CHANNELS = 512, 384, 4
ROUNDING_RADIUS = 18

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def compare_rgba(expected: bytes, observed: bytes, radius: int = ROUNDING_RADIUS) -> dict:
    if len(expected) != WIDTH * HEIGHT * CHANNELS or len(observed) != len(expected):
        raise ValueError("RGBA_SIZE_MISMATCH")
    if radius != ROUNDING_RADIUS:
        raise ValueError("UNSUPPORTED_CORNER_MASK")
    masked = 0
    mismatches = 0
    outside = 0
    for index in range(WIDTH * HEIGHT):
        y, x = divmod(index, WIDTH)
        corner = (x < radius or x >= WIDTH - radius) and (
            y < radius or y >= HEIGHT - radius
        )
        if corner:
            masked += 1
        if expected[index*4:index*4+4] != observed[index*4:index*4+4]:
            mismatches += 1
            if not corner:
                outside += 1
    return {
        "corner_mask_squares": 4,
        "configured_corner_radius_px": radius,
        "excluded_corner_pixels": masked,
        "accepted_pixels": WIDTH * HEIGHT - masked,
        "different_pixels_total": mismatches,
        "different_pixels_outside_corner_mask": outside,
        "accepted_region_exact": outside == 0,
        "entire_frame_exact": mismatches == 0,
    }

def entries(text: str, pattern: str) -> list[tuple]:
    return re.findall(pattern, text)

def evaluate(evidence: Path, cpu_root: Path, cpu_receipt: Path) -> dict:
    log = (evidence / "viewer.log").read_text()
    source_log = (evidence / "source.log").read_text()
    run = json.loads((evidence / "capture-reconciliation.json").read_text())
    origin = json.loads(cpu_receipt.read_text())
    if origin["verdict"] != "F2_F3_F4_CPU_CHAIN_PASS_BRIDGE_NOT_RUN":
        raise ValueError("CPU_WITNESS_STATUS_INVALID")
    if origin["qchain_full_e2e_pass"] is not False:
        raise ValueError("CPU_WITNESS_WRONG_AUTHORITY")
    if run["viewer_exit_code"] != 0 or run["source_exit_code"] != 0:
        raise ValueError("WINDOW_OR_SOURCE_FAILURE")
    if run["winit_present_submitted_stages"] != list(range(5)):
        raise ValueError("INCOMPLETE_PRESENTATION")
    if sha(cpu_receipt.read_bytes()) != run["cpu_receipt_sha256"]:
        raise ValueError("CPU_RECEIPT_IDENTITY_CHANGED")
    receive = entries(log, r"QCHAIN_IPC_RECEIVED stage=(\d+) rgba_sha256=([0-9a-f]{64})")
    presented = entries(log, r"QCHAIN_WGPU_PRESENT_SUBMITTED stage=(\d+) epoch=(\d+) scene_sha256=([0-9a-f]{64}) rgba_sha256=([0-9a-f]{64}) dimensions=(\d+)x(\d+)")
    sent = entries(source_log, r"QCHAIN_SOURCE_TRANSMITTED stage=(\d+) sha256=([0-9a-f]{64})")
    if len(receive) != 5 or len(sent) != 5:
        raise ValueError("MISSING_SOURCE_OR_IPC_MESSAGES")
    captures = run["captures"]
    if len(captures) != 5:
        raise ValueError("FIVE_COMPOSITOR_CAPTURES_REQUIRED")
    by_capture = {c["stage"]: c for c in captures}
    if sorted(by_capture) != list(range(5)):
        raise ValueError("DUPLICATE_OR_MISSING_STAGE_CAPTURE")
    stages = []
    expected_proofs = origin["stages"]
    if len(expected_proofs) != 5:
        raise ValueError("WRONG_CPU_STAGES")
    for index, proof in enumerate(expected_proofs):
        if proof["stage"] != index or proof["epoch"] != index:
            raise ValueError("BAD_CPU_WITNESS_SEQUENCE")
        scene_sha = proof["scene_sha256"]
        rgba_sha = proof["f4_rgba_sha256"]
        if receive[index] != (str(index), rgba_sha):
            raise ValueError("IPC_RECEIPT_HASH_WRONG")
        if sent[index] != (str(index), rgba_sha):
            raise ValueError("SERVER_SENT_HASH_WRONG")
        for row in presented:
            if row[0] == str(index) and (
                row[1] != str(index) or row[2] != scene_sha or row[3] != rgba_sha
                or row[4:6] != ("512", "384")
            ):
                raise ValueError("WGPU_PRESENT_PROVENANCE_WRONG")
        if not any(row[0] == str(index) for row in presented):
            raise ValueError("WGPU_PRESENT_MISSING_STAGE")
        record = by_capture[index]
        if record.get("captured") is not True or record.get("geometry", "").split(" ")[-1] != "512x384":
            raise ValueError("NO_512x384_WINDOW_CAPTURE")
        if not record.get("qchain_window_rounding_disabled"):
            raise ValueError("UNVERIFIED_WINDOW_SPECIFIC_PROPS")
        png = evidence / f"stage-{index:02}.png"
        if sha(png.read_bytes()) != record["capture_sha256"]:
            raise ValueError("SCREENSHOT_BYTES_CHANGED")
        actual = subprocess.run(
            ["magick", str(png), "-depth", "8", "RGBA:-"],
            check=True, capture_output=True, timeout=5
        ).stdout
        frame = (cpu_root / f"scene-{index:02}.f4-rgba.bin").read_bytes()
        if sha(frame) != rgba_sha or sha(frame) != record["expected_rgba_sha256"]:
            raise ValueError("ORIGINAL_F4_PIXELS_CHANGED")
        if sha(actual) != record["raw_capture_rgba_sha256"]:
            raise ValueError("SCREENSHOT_DECODE_CHANGED")
        audit = compare_rgba(frame, actual)
        if not audit["accepted_region_exact"]:
            raise ValueError("VISIBLE_PIXEL_DIFFERENCE_OUTSIDE_CORNER_MASK")
        stages.append({
            "stage": index,
            "scene_sha256": scene_sha,
            "f4_rgba_sha256": rgba_sha,
            "compositor_png_sha256": sha(png.read_bytes()),
            **audit,
        })
    return {
        "schema": "gnu6.qchain.compositor_e2e.v1",
        "verdict": "QCHAIN_F2_F3_F4_CPU_IPC_WAYLAND_SOFTWARE_E2E_PASS_CORNER_MASKED",
        "f2_f3_f4_cpu_sourced": True,
        "native_seqpacket_sealed_memfd_receipts": 5,
        "wgpu_vulkan_presentation_submissions": len(presented),
        "distinct_presented_stages": 5,
        "hyprland_window_specific_observations": 5,
        "masked_compositor_captures_qualified": 5,
        "full_unmasked_frame_pixel_exact": all(s["entire_frame_exact"] for s in stages),
        "allowed_mask": "four 18x18 squares at screenshot corners, derived from Hyprland corner rounding 18px",
        "physical_photons_qualified": False,
        "cp03_full_pass": False,
        "p06_3d_photorealism_qualified": False,
        "gpu_compute_oracle": "NOT_RUN",
        "stages": stages,
    }

def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit("usage: qchain_compositor_gate.py WAYLAND_EVIDENCE CPU_RAW CPU_RECEIPT OUTPUT_NEW")
    evidence, cpu_root, cpu_receipt, output = map(Path, sys.argv[1:])
    if output.exists():
        raise SystemExit("REFUSE_OVERWRITE_EVIDENCE")
    result = evaluate(evidence, cpu_root, cpu_receipt)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print("QCHAIN_F2_F3_F4_CPU_IPC_WAYLAND_SOFTWARE_E2E_PASS_CORNER_MASKED")
    print("STAGES", len(result["stages"]), "PRESENT_SUBMISSIONS", result["wgpu_vulkan_presentation_submissions"])
    for stage in result["stages"]:
        print("FRAME", stage["stage"], "accepted_pixel_count", stage["accepted_pixels"],
              "mismatch_outside_mask", stage["different_pixels_outside_corner_mask"],
              "unmasked_entire_frame_exact", stage["entire_frame_exact"])
    print("PHOTONS", "NOT_QUALIFIED", "CP03_FULL", "OPEN")

if __name__ == "__main__":
    main()
