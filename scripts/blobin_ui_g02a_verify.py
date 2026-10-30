#!/usr/bin/env python3
"""UI-G02/A reproducible, scoped headless qualification; never launches Wayland."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/runs/blob-ui-g02a-20261012"
OUT.mkdir(parents=True, exist_ok=True)

CHECKS = (
    ("rustfmt", ("cargo", "fmt", "-p", "blobin-ui-core", "--", "--check")),
    ("core-all-targets", ("cargo", "test", "--offline", "-p", "blobin-ui-core", "--all-targets")),
    ("clippy-strict", ("cargo", "clippy", "--offline", "-p", "blobin-ui-core", "--all-targets", "--", "-D", "warnings")),
    ("no-external-dependencies", ("cargo", "tree", "--offline", "-p", "blobin-ui-core")),
    ("headless-example", ("cargo", "run", "--offline", "-p", "blobin-ui-core", "--example", "tree_transaction")),
    ("workspace-lib-regression", ("cargo", "test", "--offline", "--workspace", "--lib")),
)

results = {}
for label, command in CHECKS:
    try:
        outcome = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=110, check=False)
        full = (outcome.stdout.rstrip("\n") + "\n" + outcome.stderr.rstrip("\n")).rstrip("\n") + "\n"
        exit_code = outcome.returncode
    except subprocess.TimeoutExpired as exc:
        full = f"TIMEOUT {exc}\n"
        exit_code = 124
    (OUT / f"{label}.log").write_text(full)
    pass_counts = [int(n) for n in re.findall(r"test result: ok\. (\d+) passed;", full)]
    if label == "no-external-dependencies" and len(full.strip().splitlines()) != 1:
        exit_code = 2
    if label == "headless-example" and "BLOBIN_UI_CORE_HEADLESS_OK" not in full:
        exit_code = 3
    if label == "core-all-targets" and sum(pass_counts) < 21:
        exit_code = 4
    if label == "workspace-lib-regression" and sum(pass_counts) < 51:
        exit_code = 5
    results[label] = {
        "exit": exit_code,
        "passing_tests": sum(pass_counts),
        "log_sha256": hashlib.sha256(full.encode()).hexdigest(),
    }
    print(f"{label}: exit={exit_code}; tests={sum(pass_counts)}", flush=True)

files = [
    "Cargo.toml", "Cargo.lock",
    "crates/blobin-ui-core/Cargo.toml",
    "crates/blobin-ui-core/src/lib.rs",
    "crates/blobin-ui-core/tests/component_tree.rs",
    "crates/blobin-ui-core/tests/transaction_adversarial.rs",
    "crates/blobin-ui-core/examples/tree_transaction.rs",
    "crates/blobin-ui-core/README.md",
    "docs/BLOB-UI-G02A-PORTABLE-COMPONENT-SUBSTRATE-20261012.md",
    "scripts/blobin_ui_g02a_verify.py",
]
hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files}

qualified = all(c["exit"] == 0 for c in results.values())
report = {
    "schema": "blob.in.ui_g02a_headless_core.v1",
    "date": "2026-10-12",
    "gate": "UI-G02/A",
    "verdict": "SCOPED_PASS" if qualified else "FAIL",
    "baseline_commit": "e425232bca939cce58662b1c95e99af71e68b5ef",
    "branch": "feat/blobin-ui-g02a-core-20261012",
    "scope": "headless component identity, state transactions and invalidation; no renderer",
    "checks": results,
    "sources_sha256": hashes,
    "runtime_crate_non_std_dependencies": 0,
    "historical_donor_code_imported": False,
    "external_native_consumer_qualified": False,
    "real_pointer_or_keyboard_input_qualified": False,
    "sustained_60fps_qualified": False,
    "ui_g02b_qualified": False,
    "cp03_hybrid60_pass": False,
    "merge_push_deploy": False,
}
(OUT / "qualification.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
print(f"UI_G02A_{report['verdict']}", flush=True)
sys.exit(0 if qualified else 1)
