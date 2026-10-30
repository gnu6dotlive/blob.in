#!/usr/bin/env python3
"""Scoped BLOB-AC-02 reproducible checks; no live desktop input or GitHub Actions."""
from pathlib import Path
import hashlib
import json
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/runs/blob-ac02-20261012"
SOURCES = [
    "contracts/BLOB-AC-02-NATIVE-GESTURE-CONSUMER-20261012.md",
    "crates/showcase/src/lib.rs",
    "crates/showcase/src/ac02_scene.rs",
    "crates/showcase/src/bin/blobin_ui_ac02_wayland.rs",
    "docs/BLOB-AC-02-NATIVE-CONSUMER-QUALIFICATION-20261012.md",
    "docs/PROGRAM-INTEGRATION-SPINE-20261012.md",
    "scripts/blob_ac02_verify.py",
    "scripts/blob_ac02_native_smoke.py",
]
COMMANDS = [
    ["rustfmt", "--edition", "2021", "--check",
     "crates/showcase/src/ac02_scene.rs", "crates/showcase/src/bin/blobin_ui_ac02_wayland.rs"],
    ["cargo", "test", "--offline", "-p", "blobin-showcase", "--lib", "ac02_scene"],
    ["cargo", "test", "--offline", "-p", "blobin-showcase", "--lib"],
    ["cargo", "clippy", "--offline", "-p", "blobin-showcase",
     "--lib", "--bin", "blobin_ui_ac02_wayland", "--", "-D", "warnings"],
    ["cargo", "test", "--offline", "-p", "blobin-ui-core", "--all-targets"],
    ["cargo", "test", "--offline", "--workspace", "--lib"],
    ["cargo", "build", "--offline", "-p", "blobin-showcase", "--bin", "blobin_ui_ac02_wayland"],
]

def git(*args: str) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
    return p.stdout.strip()
def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
def record_command(index: int, args: list[str], result: subprocess.CompletedProcess[str]) -> dict:
    stdout = EVIDENCE / f"gate-{index:02}.stdout.txt"
    stderr = EVIDENCE / f"gate-{index:02}.stderr.txt"
    stdout.write_text(result.stdout.rstrip("\n") + ("\n" if result.stdout else ""), encoding="utf-8")
    stderr.write_text(result.stderr.rstrip("\n") + ("\n" if result.stderr else ""), encoding="utf-8")
    return {
        "argv": args, "exit_code": result.returncode,
        "stdout": str(stdout.relative_to(ROOT)), "stdout_sha256": digest(stdout),
        "stderr": str(stderr.relative_to(ROOT)), "stderr_sha256": digest(stderr)
    }

def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    metadata = subprocess.run(["cargo", "metadata", "--no-deps", "--format-version", "1", "--offline"],
                              cwd=ROOT, capture_output=True, text=True, check=True)
    target_dir = Path(json.loads(metadata.stdout)["target_directory"])
    binary = target_dir / "debug" / "blobin_ui_ac02_wayland"
    results = {
        "mandate": "BLOB-AC-02",
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "repo": "tension-atoi/blob.in-showcase",
        "branch": git("branch", "--show-current"),
        "baseline": git("rev-parse", "HEAD"),
        "origin": git("remote", "get-url", "origin"),
        "claim": "Native consumer semantic tests and native Wayland/Vulkan submission only; not real gesture E2E",
        "g05_visible_pixel_oracle": "HOLD",
        "g06_native_physical_gesture_oracle": "NOT_RUN",
        "cp03_hybrid_60": "NOT_PASS",
        "ui_g04_full": "NOT_PROMOTED",
        "sources": {p: digest(ROOT / p) for p in SOURCES},
        "commands": []
    }
    success = (results["branch"] == "main" and
               results["origin"] == "https://github.com/tension-atoi/blob.in-showcase.git")
    for i, cmd in enumerate(COMMANDS, 1):
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=150)
        results["commands"].append(record_command(i, cmd, r))
        print(f"AC02 gate-{i:02}: {'PASS' if r.returncode == 0 else 'FAIL'}", flush=True)
        if r.returncode != 0:
            success = False
            break
    if success:
        command = ["python3", "scripts/blob_ac02_native_smoke.py",
                   "--binary", str(binary), "--output", str(EVIDENCE / "native")]
        r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=45)
        results["commands"].append(record_command(8, command, r))
        print(f"AC02 gate-08 (private Weston native): {'PASS' if r.returncode == 0 else 'HOLD'}", flush=True)
        success = r.returncode == 0
        if success:
            native = json.loads((EVIDENCE / "native/native-smoke.json").read_text())
            success = (
                native.get("verdict") == "NATIVE_SURFACE_SUBMITTED_SCOPED_PASS_INPUT_E2E_NOT_RUN"
                and native.get("frame_submissions", 0) >= 1
                and native.get("physical_pointer_oracle") is False
                and native.get("compositor_present_feedback") is False
                and native.get("screenshooter_visual_qualified") is False
            )
            results["native"] = native
    results["result"] = ("SCOPED_PASS_NATIVE_SUBMISSION_G05_G06_HOLD" if success else "HOLD")
    (EVIDENCE / "qualification.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("BLOB_AC02_" + results["result"], flush=True)
    return 0 if success else 1

if __name__ == "__main__":
    raise SystemExit(main())
