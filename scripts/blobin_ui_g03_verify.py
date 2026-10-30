#!/usr/bin/env python3
"""BLOB UI-G03: reproducible, local-only headless layout qualification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/runs/blob-ui-g03-20261012"
OUT.mkdir(parents=True, exist_ok=True)
CHECKS = (
    ("rustfmt", ("cargo", "fmt", "-p", "blobin-ui-core", "--", "--check")),
    ("core-all-targets", ("cargo", "test", "--offline", "-p", "blobin-ui-core", "--all-targets")),
    ("clippy-strict", ("cargo", "clippy", "--offline", "-p", "blobin-ui-core", "--all-targets", "--", "-D", "warnings")),
    ("std-only-deps", ("cargo", "tree", "--offline", "-p", "blobin-ui-core")),
    ("headless-layout-example", ("cargo", "run", "--offline", "-p", "blobin-ui-core", "--example", "layout_workbench")),
    ("workspace-lib-regression", ("cargo", "test", "--offline", "--workspace", "--lib")),
)
result = {}
for label, command in CHECKS:
    try:
        run = subprocess.run(command, cwd=ROOT, capture_output=True,
                             text=True, timeout=120, check=False)
        output = (run.stdout.rstrip("\n")+"\n"+run.stderr.rstrip("\n")).rstrip("\n")+"\n"
        code = run.returncode
    except subprocess.TimeoutExpired as exc:
        output = f"TIMEOUT {exc}\n"
        code = 124
    (OUT / f"{label}.log").write_text(output)
    passing = sum(int(v) for v in re.findall(r"test result: ok\. (\d+) passed;", output))
    if label == "core-all-targets":
        oracles = (
            "layout_is_deterministic_across_resolution_and_dpr_matrix ... ok",
            "independent_analytic_oracle_for_fixed_plus_one_growing_child_512_cases ... ok",
            "nested_clip_applies_to_overflow_but_does_not_clip_unrelated_sibling ... ok",
            "overdeep_tree_rejected_before_painting ... ok",
            "excessive_offscreen_coordinate_fails_closed_not_integer_overflow ... ok",
        )
        if passing < 46 or not all(name in output for name in oracles):
            code = 4
    if label == "std-only-deps" and (
        len(output.strip().splitlines()) != 1
        or "blobin-ui-core" not in output
    ):
        code = 5
    if label == "headless-layout-example" and "BLOBIN_UI_G03_HEADLESS_OK" not in output:
        code = 6
    if label == "workspace-lib-regression" and passing < 51:
        code = 7
    result[label] = {
        "exit": code,
        "passing_tests": passing,
        "sha256": hashlib.sha256(output.encode()).hexdigest(),
    }
    print(f"{label}: exit={code} passed={passing}",flush=True)
sources = (
    "crates/blobin-ui-core/src/layout.rs",
    "crates/blobin-ui-core/src/lib.rs",
    "crates/blobin-ui-core/tests/layout_matrix.rs",
    "crates/blobin-ui-core/examples/layout_workbench.rs",
    "crates/blobin-ui-core/README.md",
    "docs/BLOB-UI-G03-DETERMINISTIC-LAYOUT-20261012.md",
    "docs/PROGRAM-INTEGRATION-SPINE-20261012.md",
    "scripts/blobin_ui_g03_verify.py",
)
hashes = {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in sources}
good = all(c["exit"] == 0 for c in result.values())
report = {
    "schema": "blob.in.ui_g03_headless_layout.v1",
    "date": "2026-10-12",
    "gate": "UI-G03",
    "verdict": "SCOPED_PASS" if good else "FAIL",
    "baseline_main": "de4ff5e1d500551ad9b6783d0199801eea2c8aa3",
    "integration_branch": "main",
    "check_results": result,
    "source_sha256": hashes,
    "g03_new_tests": 14,
    "resolution_dpr_matrix_cases": 120,
    "independent_analytic_oracle_cases": 512,
    "prior_reconcile_oracle_steps": 400,
    "prior_transaction_replay_steps": 600,
    "geometry_only": True,
    "actual_wayland_input_verified": False,
    "independent_wgpu_renderer_verified": False,
    "compositor_presentation_verified": False,
    "cp03_hybrid60_pass": False,
}
(OUT / "qualification.json").write_text(json.dumps(report, indent=2) + "\n")
print("UI_G03_"+report["verdict"],flush=True)
sys.exit(0 if good else 1)
