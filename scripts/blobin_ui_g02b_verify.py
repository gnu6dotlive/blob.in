#!/usr/bin/env python3
"""Local, deterministic UI-G02/B qualification; no GPU or GitHub Actions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/runs/blob-ui-g02b-20261012"
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
        completed = subprocess.run(command, cwd=ROOT, capture_output=True,
                                   text=True, timeout=120, check=False)
        log = (completed.stdout.rstrip("\n") + "\n" + completed.stderr.rstrip("\n")).rstrip("\n") + "\n"
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as e:
        log = f"TIMEOUT: {e}\n"
        exit_code = 124
    (OUT / f"{label}.log").write_text(log)
    pass_counts = [int(v) for v in re.findall(r"test result: ok\. (\d+) passed;", log)]
    total_pass = sum(pass_counts)
    if label == "core-all-targets" and (
        total_pass < 32
        or "keyed_reconciliation_matches_independent_full_rebuild_oracle_400_steps ... ok" not in log
        or "independent_cow_pages_are_shared_between_snapshots ... ok" not in log
    ):
        exit_code = 4
    if label == "workspace-lib-regression" and total_pass < 51:
        exit_code = 5
    if label == "no-external-dependencies" and (
        log.strip().splitlines() != [line for line in log.splitlines() if "blobin-ui-core v0.1.0" in line]
        or len(log.strip().splitlines()) != 1
    ):
        exit_code = 6
    if label == "headless-example" and "BLOBIN_UI_CORE_HEADLESS_OK" not in log:
        exit_code = 7
    results[label] = {
        "exit": exit_code,
        "passed": total_pass,
        "log_sha256": hashlib.sha256(log.encode()).hexdigest(),
    }
    print(f"{label}: exit={exit_code} passed={total_pass}", flush=True)

sources = (
    "Cargo.toml",
    "Cargo.lock",
    "crates/blobin-ui-core/Cargo.toml",
    "crates/blobin-ui-core/src/lib.rs",
    "crates/blobin-ui-core/tests/component_tree.rs",
    "crates/blobin-ui-core/tests/transaction_adversarial.rs",
    "crates/blobin-ui-core/tests/incremental_reconciliation.rs",
    "crates/blobin-ui-core/examples/tree_transaction.rs",
    "crates/blobin-ui-core/README.md",
    "docs/BLOB-UI-G02B-INCREMENTAL-RECONCILIATION-20261012.md",
    "scripts/blobin_ui_g02b_verify.py",
)
source_hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in sources}
success = all(check["exit"] == 0 for check in results.values())
report = {
    "schema": "blob.in.ui_g02b_incremental_reconciliation.v1",
    "date": "2026-10-12",
    "gate": "UI-G02/B",
    "verdict": "SCOPED_PASS" if success else "FAIL",
    "baseline_remote_commit": "489cb9f3db1052e3868ea412bcebffd67d414120",
    "canonical_integration_branch": "main",
    "scope": "headless keyed reconciliation, bounded-page COW and typed damage",
    "checks": results,
    "source_sha256": source_hashes,
    "direct_tests_required": 32,
    "independent_reconciliation_oracle_steps": 400,
    "preexisting_adversarial_transaction_steps": 600,
    "cow_page_size": 64,
    "crate_non_std_dependencies": 0,
    "archived_donor_source_imported": False,
    "production_renderer_verified": False,
    "real_pointer_or_keyboard_e2e": False,
    "steady_60fps": False,
    "cp03_hybrid60_pass": False,
    "ui_g03_qualified": False,
}
(OUT / "qualification.json").write_text(json.dumps(report, indent=2) + "\n")
print(f"UI_G02B_{report['verdict']}", flush=True)
sys.exit(0 if success else 1)
