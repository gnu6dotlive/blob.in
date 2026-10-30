#!/usr/bin/env python3
"""BLOB-AC-02 isolated native Wayland launch (no synthetic compositor input)."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import time
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--binary", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
runtime = Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000"))
display = "blob-ac02-" + str(os.getpid())
env = dict(os.environ, WAYLAND_DISPLAY=display, XDG_RUNTIME_DIR=str(runtime),
           BLOBIN_AC02_ALLOW_GL="1", RUST_BACKTRACE="1")
for key in ("VK_LAYER_PATH", "VK_INSTANCE_LAYERS", "CPJA7CB_LOADER_FAULT"):
    env.pop(key, None)
procs = []
report = {"gate": "BLOB-AC-02", "compositor": "private Weston headless GL",
          "physical_pointer_oracle": False, "compositor_present_feedback": False,
          "renderer_owner": "ac02_standalone_fixture"}
try:
    with (out / "weston.stdout").open("wb") as w:
        proc = subprocess.Popen([
            "weston", "--backend=headless", "--renderer=gl", "--shell=kiosk",
            "-S", display, "--no-config", "--width=940", "--height=640",
            "--idle-time=0", "--log=" + str(out / "weston.log")
        ], env=env, cwd=out, stdout=w, stderr=subprocess.STDOUT, start_new_session=True)
    procs.append(proc)
    for _ in range(200):
        if (runtime / display).is_socket() or proc.poll() is not None:
            break
        time.sleep(0.025)
    if not (runtime / display).is_socket() or proc.poll() is not None:
        raise RuntimeError("WESTON_SOCKET_UNAVAILABLE")
    binary = args.binary.resolve()
    with (out / "viewer.stdout").open("wb") as std, (out / "viewer.stderr").open("wb") as err:
        native = subprocess.Popen([str(binary), "--trace=" + str(out / "native-events.jsonl"),
                                   "--run-ms=4000"], env=env, cwd=out,
                                  stdout=std, stderr=err, start_new_session=True)
    procs.append(native)
    # Screenshot is independent compositor framebuffer evidence, not an input oracle.
    time.sleep(1.1)
    existing_pictures = set(out.glob("wayland-screenshot-*.png"))
    shot = subprocess.run(["weston-screenshooter"], env=env, cwd=out,
                          capture_output=True, text=True, timeout=8)
    (out / "screenshooter.stdout").write_text(shot.stdout)
    (out / "screenshooter.stderr").write_text(shot.stderr)
    pictures = sorted(set(out.glob("wayland-screenshot-*.png")) - existing_pictures)
    report["screenshot_attempt"] = {
        "exit_code": shot.returncode, "count": len(pictures),
        "sha256": {pic.name: hashlib.sha256(pic.read_bytes()).hexdigest() for pic in pictures}
    }
    report["screenshooter_visual_qualified"] = False
    report["screenshooter_note"] = "Captured pixels are unqualified, even if capture succeeded; prior Weston capture was black."
    native.wait(timeout=28)
    if native.returncode != 0:
        raise RuntimeError("NATIVE_BINARY_FAILED")
    records = [json.loads(row) for row in (out / "native-events.jsonl").read_text().splitlines()]
    ready = [r for r in records if r.get("kind") == "window_ready"]
    summary = [r for r in records if r.get("kind") == "summary"]
    if len(ready) != 1 or len(summary) != 1:
        raise RuntimeError("MISSING_WINDOW_READY_OR_SUMMARY")
    if summary[0]["frame_submissions"] < 1 or not ready[0]["native_window"]:
        raise RuntimeError("NO_SUBMITTED_NATIVE_FRAME")
    if summary[0]["gesture_commits"] != 0 or summary[0]["receipt_count"] != summary[0]["ingress_count"]:
        raise RuntimeError("INVALID_UNATTRIBUTED_GESTURE_OR_RECEIPT")
    report.update({
        "verdict": "NATIVE_SURFACE_SUBMITTED_SCOPED_PASS_INPUT_E2E_NOT_RUN",
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "backend": ready[0]["backend"],
        "frame_submissions": summary[0]["frame_submissions"],
        "native_ingress_count": summary[0]["ingress_count"],
        "gesture_commits": summary[0]["gesture_commits"],
        "source": "winit_wayland"
    })
    print(json.dumps(report, indent=2), flush=True)
except Exception as exc:
    report.update(verdict="HOLD", failure=str(exc))
    print("BLOB_AC02_NATIVE_HOLD", str(exc), file=sys.stderr)
finally:
    (out / "native-smoke.json").write_text(json.dumps(report, indent=2) + "\n")
    for proc in reversed(procs):
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
sys.exit(0 if report.get("verdict", "").startswith("NATIVE_SURFACE_") else 1)
