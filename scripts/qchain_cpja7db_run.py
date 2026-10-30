#!/usr/bin/env python3
"""CP-JA7B: compositor-space evidence of two distinct surfaces and primary recovery."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

SIZE = (1536, 1024)
RECTS = ((92, 190, 604, 574), (810, 190, 1322, 574))
FRAME_BYTES = 512 * 384 * 4
MAX_CHANNEL_DELTA = 3  # empirically observed Weston GL compositor bound; never auto-expand


def need(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def analyze(actual, reference):
    diff = np.abs(actual.astype(np.int16) - reference.astype(np.int16))
    return {
        "max_delta_rgba": diff.max(axis=(0, 1)).tolist(),
        "pixels_over_rgb3": int(np.any(diff[:, :, :3] > MAX_CHANNEL_DELTA, axis=2).sum()),
        "pixels_alpha_mismatch": int(np.count_nonzero(diff[:, :, 3])),
        "pixels_rgb_not_exact": int(np.any(diff[:, :, :3] != 0, axis=2).sum()),
        "mean_abs_rgb": round(float(diff[:, :, :3].mean()), 6),
    }


def matched(stats):
    return stats["pixels_over_rgb3"] == 0 and stats["pixels_alpha_mismatch"] == 0


def run(a):
    root = a.root
    need(root.is_dir() and not any(root.iterdir()), "RUN_DIRECTORY_NOT_EMPTY")
    need(a.tile_plugin.is_file() and a.viewer.is_file(), "BINARIES_MISSING")
    (root / "engine-ledger").mkdir(mode=0o700)
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000"))
    ws = f"cpja7db-w-{os.getpid()}"
    ipc = runtime / f"cpja7db-{os.getpid()}.sock"
    need(not (runtime / ws).exists() and not ipc.exists(), "PRIVATE_SOCKET_EXISTS")
    env = dict(os.environ, XDG_RUNTIME_DIR=str(runtime), WAYLAND_DISPLAY=ws,
               RUST_BACKTRACE="1")
    for key in ("VK_LAYER_PATH", "VK_INSTANCE_LAYERS", "CPJA7CB_LOADER_FAULT",
                "CPJA7C_INJECT_LOST_AT", "CPJA7C_RECOVER_IN_PROCESS",
                "CPJA7CB_PROCESS_LOSS_COUNT"):
        env.pop(key, None)
    weston = source = viewer = debugger = None
    streams = []
    samples = []
    started = time.monotonic()
    try:
        weston = subprocess.Popen([
            "weston", "--backend=headless", "--renderer=gl", "--shell=desktop",
            "--modules=" + str(a.tile_plugin), "--debug", "-S", ws,
            "--width=1536", "--height=1024", "--no-config", "--idle-time=0",
            f"--log={root / 'weston.log'}",
        ], env=env, stdout=(root / "weston.stdout").open("wb"),
           stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(200):
            if (runtime / ws).is_socket() or weston.poll() is not None:
                break
            time.sleep(0.025)
        need((runtime / ws).is_socket() and weston.poll() is None,
             "PRIVATE_WESTON_BOOT_FAILED")
        debugger = subprocess.Popen(
            ["weston-debug", "-o", str(root / "weston-timeline-proto.log"), "proto"],
            env=env, stdout=subprocess.DEVNULL,
            stderr=(root / "weston-debug.err").open("wb"))
        for name in ("source", "viewer"):
            streams.extend(((root / f"{name}.stdout").open("wb"),
                            (root / f"{name}.stderr").open("wb")))
        source = subprocess.Popen(
            ["python3", str(a.broker), "--engine", str(a.engine),
             "--baseline", str(a.baseline), "--receipt", str(a.receipt),
             "--socket", str(ipc), "--log", str(root / "engine-ledger"),
             "--frames", "120"],
            env=env, stdout=streams[0], stderr=streams[1])
        for _ in range(200):
            if ipc.is_socket() or source.poll() is not None:
                break
            time.sleep(0.025)
        need(ipc.is_socket(), "LIVE_GPU_BROKER_NOT_READY")
        viewer_env = dict(env, WAYLAND_DEBUG="client", RUST_LOG="info")
        if a.mode == "loader-recovery":
            viewer_env.update(
                VK_LAYER_PATH=str(a.layer_dir),
                VK_INSTANCE_LAYERS="VK_LAYER_GNU6_cpja7cb_fault",
                CPJA7CB_LOADER_FAULT="primary-id-41",
                CPJA7C_RECOVER_IN_PROCESS="1")
        if a.drop_secondary_after:
            viewer_env["CPJA7_DROP_SECONDARY_AFTER"] = str(a.drop_secondary_after)
        viewer = subprocess.Popen(
            [str(a.viewer), str(ipc), str(a.receipt), "120"],
            env=viewer_env, stdout=streams[2], stderr=streams[3])

        targets = ([9, 21, 33, 45, 60, 69, 81, 93]
                   if a.drop_secondary_after else
                   [9, 21, 33, 45, 57, 69, 81, 93])
        canonical = []
        for material in ("ceramic", "gel", "metal", "paper"):
            for j in range(2):
                f = a.baseline / f"state4-{material}-frame{j}-dpr2.gpu-rgba.bin"
                payload = f.read_bytes()
                need(len(payload) == FRAME_BYTES, "INVALID_CANONICAL_FRAME")
                canonical.append((sha(payload),
                                  np.frombuffer(payload, np.uint8).reshape((384, 512, 4)).copy()))

        for idx, target in enumerate(targets):
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                log = (root / "viewer.stdout").read_text(errors="replace")
                submitted = [int(x) for x in
                             re.findall(r"CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+)", log)]
                if target in submitted or viewer.poll() is not None:
                    break
                time.sleep(0.005)
            need(target in submitted, f"SAMPLE_TARGET_MISSED_{target}")
            if a.drop_secondary_after and idx >= 4:
                need("CPJA7_SECONDARY_RELEASE after_seq=59" in log,
                     "SECONDARY_RELEASE_NOT_OBSERVED")
            before = set(root.glob("wayland-screenshot-*.png"))
            capture = subprocess.run(["weston-screenshooter"], cwd=root, env=env,
                                     capture_output=True, text=True, timeout=4)
            need(capture.returncode == 0 and
                 "unauthorized" not in (capture.stdout + capture.stderr).lower(),
                 "SCREENSHOT_DENIED")
            new = set(root.glob("wayland-screenshot-*.png")) - before
            need(len(new) == 1, "SCREENSHOT_NOT_UNIQUE")
            screenshot = root / f"sample-{idx:02}.png"
            new.pop().rename(screenshot)
            with Image.open(screenshot) as im:
                need(im.size == SIZE, "COMPOSITOR_CAPTURE_DIMENSIONS_MISMATCH")
                full = np.asarray(ImageOps.flip(im.convert("RGBA")), dtype=np.uint8)
            regions = [full[y0:y1, x0:x1] for (x0,y0,x1,y1) in RECTS]
            need(all(region.shape == (384,512,4) for region in regions),
                 "CAPTURE_REGION_GEOMETRY_MISMATCH")
            expected_sha, ref = canonical[idx]
            secondary = ref.copy()
            secondary[:, :16, :] = np.array((0, 0, 0, 255), dtype=np.uint8)
            primary_stats = analyze(regions[0], ref)
            secondary_stats = analyze(regions[1], secondary)
            need(matched(primary_stats), f"PRIMARY_PIXEL_OR_FRAME_MISMATCH_{idx}")
            closed = a.drop_secondary_after is not None and idx >= 4
            if closed:
                need(not matched(secondary_stats),
                     f"SECONDARY_VISUALLY_STILL_PRESENT_{idx}")
                # Confirm it has disappeared, not merely changed image: its
                # old 16px stripe cannot linger under the mapped window.
                need(np.any(regions[1][:, :16, :3] != 0),
                     f"SECONDARY_SIGNATURE_STILL_PRESENT_{idx}")
            else:
                need(matched(secondary_stats),
                     f"SECONDARY_PIXEL_OR_FRAME_MISMATCH_{idx}")
                need(not matched(analyze(regions[0], secondary)),
                     "PRIMARY_INDISTINGUISHABLE_FROM_SECONDARY")
                need(not matched(analyze(regions[1], ref)),
                     "SECONDARY_INDISTINGUISHABLE_FROM_PRIMARY")
            samples.append({
                "target_seq": target, "variant": idx, "phase": "after_close" if closed else "both_visible",
                "screenshot_sha256": sha(screenshot.read_bytes()),
                "canonical_rgba_sha256": expected_sha,
                "primary_region_rgba_sha256": sha(regions[0].tobytes()),
                "secondary_region_rgba_sha256": sha(regions[1].tobytes()),
                "primary": primary_stats, "secondary": secondary_stats,
                "region_coordinates_flipped": [list(v) for v in RECTS],
            })
            print("CPJA7DB_SAMPLE",idx,"target",target,"phase",samples[-1]["phase"],
                  "primary",primary_stats["max_delta_rgba"],
                  "secondary",secondary_stats["max_delta_rgba"],flush=True)
        viewer.wait(timeout=25)
        source.wait(timeout=10)
        need(viewer.returncode == source.returncode == 0, "VIEWER_OR_ENGINE_EXIT_NONZERO")
        viewer_log = (root / "viewer.stdout").read_text()
        records = re.findall(
            r"CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+) stage=(\d+) elapsed_us=(\d+)"
            r" received_to_submit_us=(\d+) epoch=(\d+) scene_sha256=([0-9a-f]{64})"
            r" rgba_sha256=([0-9a-f]{64}) dimensions=(\d+)x(\d+)", viewer_log)
        need(len(records) == 120 and
             [int(x[0]) for x in records] == list(range(120)),
             "STREAM_SEQUENCE_LOSS")
        need("CPI02_WGPU_STREAM_COMPLETE submitted=120" in viewer_log,
             "VIEWER_COMPLETION_MISSING")
        stages = json.loads(a.receipt.read_text())["stages"]
        need(all(rec[5] == stages[int(rec[1])]["scene_sha256"] for rec in records),
             "GPU_STAGE_IDENTITY_MISMATCH")
        need(all(rec[6] == canonical[((int(rec[0])-5)//12)%8][0]
                 for rec in records if int(rec[0]) >= 5),
             "GPU_PIXEL_FRAME_HASH_MISMATCH")
        from qchain_cpja7db_gate import qualify
        qualify(root, samples, started, a.mode)
        return
    finally:
        for process in (viewer, source, debugger, weston):
            if process is not None and process.poll() is None:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
        for stream in streams:
            stream.close()
        ipc.unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser()
    for key in ("engine","viewer","broker","baseline","receipt","root","tile-plugin"):
        p.add_argument("--" + key, required=True, type=Path)
    p.add_argument("--drop-secondary-after", type=int, choices=[60])
    p.add_argument("--layer-dir", type=Path)
    p.add_argument("--mode", required=True, choices=["normal","loader-recovery"])
    p.add_argument("--parent-commit", default="1a586ef77f3ab69755c79adeacf4187910854892")
    run(p.parse_args())


if __name__ == "__main__":
    main()
