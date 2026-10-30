#!/usr/bin/env python3
"""BLOB-AC-01 scoped local proof; never runs GH Actions or modifies the render pipeline."""
from __future__ import annotations
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/runs/blob-ac01-20261012"
SOURCES = [
    "contracts/BLOB-AC-01-TRANSACTIONAL-GESTURES-20261012.md",
    "crates/blobin-ui-core/src/lib.rs",
    "crates/blobin-ui-core/src/gestures.rs",
    "crates/blobin-ui-core/tests/gestures.rs",
    "crates/blobin-ui-core/examples/gesture_workbench.rs",
    "scripts/blob_ac01_verify.py",
]
COMMANDS = [
    ["cargo", "fmt", "-p", "blobin-ui-core", "--", "--check"],
    ["cargo", "test", "--offline", "-p", "blobin-ui-core", "--all-targets"],
    ["cargo", "clippy", "--offline", "-p", "blobin-ui-core", "--all-targets", "--", "-D", "warnings"],
    ["cargo", "tree", "--offline", "-p", "blobin-ui-core"],
    ["cargo", "run", "--offline", "-p", "blobin-ui-core", "--example", "gesture_workbench"],
    ["cargo", "test", "--offline", "--workspace", "--lib"],
]
def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    ledger: dict = {
        "contract": "BLOB-AC-01",
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "repo": "tension-atoi/blob.in-showcase",
        "branch": git("branch", "--show-current"),
        "baseline_sha": git("rev-parse", "HEAD"),
        "origin": git("remote", "get-url", "origin"),
        "scope": "headless gesture control only; UI-G04B still HOLD; CP03 HYBRID-60 still OPEN",
        "source": {p: digest(ROOT / p) for p in SOURCES},
        "commands": [],
    }
    ok = ledger["branch"] == "main" and ledger["origin"] == "https://github.com/tension-atoi/blob.in-showcase.git"
    for i, args in enumerate(COMMANDS, 1):
        p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=150)
        label = f"gate-{i:02d}"
        stdout = EVIDENCE / f"{label}.stdout.txt"
        stderr = EVIDENCE / f"{label}.stderr.txt"
        stdout.write_text(p.stdout.rstrip('\n') + ('\n' if p.stdout else ""), encoding="utf-8")
        stderr.write_text(p.stderr.rstrip('\n') + ('\n' if p.stderr else ""), encoding="utf-8")
        ledger["commands"].append({
            "argv": args, "exit_code": p.returncode,
            "stdout": str(stdout.relative_to(ROOT)), "stdout_sha256": digest(stdout),
            "stderr": str(stderr.relative_to(ROOT)), "stderr_sha256": digest(stderr)
        })
        print(f"{label}: {'PASS' if p.returncode == 0 else 'FAIL'} — {' '.join(args)}", flush=True)
        if p.returncode != 0:
            ok = False
            break
    tree = EVIDENCE / "gate-04.stdout.txt"
    if tree.exists() and (tree.read_text().count("\n") > 1 or "blobin-ui-core" not in tree.read_text()):
        ok = False
        ledger["dependency_check"] = "FAIL (expected std-only one-line tree)"
    else:
        ledger["dependency_check"] = "PASS (std only)" if tree.exists() else "NOT_RUN"
    demo = EVIDENCE / "gate-05.stdout.txt"
    if demo.exists() and "BLOB_AC01_HEADLESS_OK previews=2 commits=1 undo=1" not in demo.read_text():
        ok = False
        ledger["demo_check"] = "FAIL"
    else:
        ledger["demo_check"] = "PASS" if demo.exists() else "NOT_RUN"
    ledger["result"] = "SCOPED_PASS" if ok else "HOLD"
    path = EVIDENCE / "qualification.json"
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"BLOB_AC01_{ledger['result']} receipt={path.relative_to(ROOT)}", flush=True)
    return 0 if ok else 1
if __name__ == "__main__":
    raise SystemExit(main())
