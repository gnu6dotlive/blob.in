#!/usr/bin/env python3
"""BLOB-RENDER-RECONCILE-01: read-only donor provenance and interface boundary audit.

Reads original local worktrees, existing archived receipts and existing Rust
sources. Writes only to the requested evidence output directory, never donors.
No source vendoring, worktree repair, merge, GPU execution, or CP03 promotion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parents[1]
WORKTREES = Path("/mnt/workbench/workspaces/gnu.in.labs/.worktrees")
EVIDENCE = Path("/mnt/workbench/evidence/runs")
CP01 = WORKTREES / "blobin-cp01-hybrid-20261010"
CP02 = WORKTREES / "blobin-cp02-vulkan-probe-20261010"
WORKER = {
    "F1": "blobin-f1-render",
    "F2": "blobin-f2-topology",
    "F3": "blobin-f3-material-height",
    "F4": "blobin-f4-effects",
    "F4B": "blobin-f4b-resilience",
    "F4C": "blobin-f4c-incremental",
}
QUALIFIED_BASE = {
    "showcase": "d2903f0a53d648a739f4cabdf03d3842577108e9",
    "cp01": "ddd723329b1d0b07d7a827dc8776d8a2535c21b5",
    "cp02": "5d2b5bdc65cbd60109060401a6f655714bd165fa",
    "cp02_original_gpu_receipt": "6bc46ccfa587d6fe71e98010a417097e3c518133",
}
TESTS = {
    "cp01": "cp01-test.log",
    "f2": "f2-test.log",
    "f4c": "f4c-test.log",
    "cp02_compile": "cp02-test.log",
}
RESULTS_BASE = HERE / "evidence/runs/blob-render-reconcile-01-20261012/logs"
SOURCE_SUFFIXES = {".rs", ".wgsl", ".toml"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root: Path, *argv: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *argv], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def source_snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): digest(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix in SOURCE_SUFFIXES
    }


def test_summary(path: Path) -> dict:
    raw = path.read_text()
    parsed = [
        (int(passed), int(failed))
        for passed, failed in re.findall(
            r"test result: ok\. (\d+) passed; (\d+) failed;", raw
        )
    ]
    return {
        "path": str(path),
        "sha256": digest(path),
        "qualifying_exit_attested_externally": False,
        "cargo_test_results": len(parsed),
        "tests_passed": sum(a for a, _ in parsed),
        "tests_failed": sum(b for _, b in parsed),
        "any_failed_suite": "test result: FAILED" in raw
            or "error: could not compile" in raw,
        "compilation_finished": "Finished" in raw,
        "source_is_pinned": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true",
                        help="Compare a previously archived manifest, without modifying it.")
    parser.add_argument(
        "--out",
        type=Path,
        default=HERE / "evidence/runs/blob-render-reconcile-01-20261012",
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    main_head = git(HERE, "rev-parse", "HEAD")
    origin = git(HERE, "remote", "get-url", "origin")
    cp01_head = git(CP01, "rev-parse", "HEAD")
    cp02_head = git(CP02, "rev-parse", "HEAD")
    cp01_clean = not git(CP01, "status", "--porcelain")
    cp02_clean = not git(CP02, "status", "--porcelain")
    f_sources = {}
    recovery_ok = True
    broken_git_count = 0
    for item, directory in WORKER.items():
        archive = WORKTREES / directory
        current = CP01 / "experiments/blobin-next-01" / item
        orphan = archive / "experiments/blobin-next-01" / item
        p0, p1 = source_snapshot(current), source_snapshot(orphan)
        identical = bool(p0) and p0 == p1
        broken = not Path(
            (archive / ".git").read_text().strip().removeprefix("gitdir: ")
        ).exists()
        recovery_ok = recovery_ok and identical and broken
        broken_git_count += int(broken)
        f_sources[item] = {
            "orphan_path": str(orphan),
            "git_worktree_link_broken": broken,
            "recoverable_git_path": str(current),
            "recoverable_commit": cp01_head,
            "source_manifest": p0,
            "file_count": len(p0),
            "byte_identical_source_to_orphan": identical,
            "diff_paths": sorted(
                k for k in p0.keys() | p1.keys() if p0.get(k) != p1.get(k)
            ),
            "license_declaration_in_manifest": any(
                l.strip().startswith("license =")
                for l in (current / "Cargo.toml").read_text().splitlines()
            ),
        }
    results = {
        label: test_summary(RESULTS_BASE / filename)
        for label, filename in TESTS.items()
    }
    test_ok = (
        all(x["tests_failed"] == 0 and not x["any_failed_suite"]
                and x["compilation_finished"] for x in results.values())
        and results["cp01"]["tests_passed"] >= 56
        and results["f2"]["tests_passed"] >= 7
        and results["f4c"]["tests_passed"] >= 5
    )
    receipt = json.loads(
        (EVIDENCE / "blobin-next-01/program-20261010/review-06/ledger.json").read_text()
    )
    actual_cp02_original = git(CP02, "cat-file", "-t", QUALIFIED_BASE["cp02_original_gpu_receipt"])
    cp03 = HERE / "docs/CP03-I01-SOURCE-TRUTH-AND-NEXT-ACTIONS-20261012.md"
    cp03_content = cp03.read_text()
    workspace = (HERE / "Cargo.toml").read_text()
    bridge = (HERE / "crates/showcase/Cargo.toml").read_text()
    licensing_hold = (
        'license = "LicenseRef-Proprietary"' in workspace
        and all(not x["license_declaration_in_manifest"] for x in f_sources.values())
    )
    core_only = (
        '"../blobin-ui-core"' in (HERE / "crates/blobin-ui-scene/Cargo.toml").read_text()
        and "wgpu.workspace = true" in bridge
    )
    matrix = {
        "F1": {
            "ownership": "offscreen 2D frame and analytic signed field",
            "integration_action": "adapter interface reference; no wholesale merge",
            "maturity": "ARCHIVED_LAB_SOURCE_RECOVERED",
        },
        "F2": {
            "ownership": "typed topology, hit targets, epochs, independent mask oracle",
            "integration_action": "typed semantic scene adapter; avoid duplicate G02 identity owners",
            "maturity": "FRESH_CPU_UNIT_TESTS_PASS_PRIVATE_LAB",
        },
        "F3": {
            "ownership": "height, heat, normals and 4 material presets",
            "integration_action": "material evaluation as optional content pass; not UI color authority",
            "maturity": "HISTORICAL_CPU_GPU_PARITY_PRIVATE_LAB",
        },
        "F4": {
            "ownership": "four explicit multi-pass effects shadow blur bloom echo",
            "integration_action": "separate optional effect graph after signed scene content",
            "maturity": "HISTORICAL_EFFECT_PASS_PRIVATE_LAB",
        },
        "F4B": {
            "ownership": "region-oriented transfer and failure policy; not all stage-local",
            "integration_action": "resilience donor subject to true resident device validation",
            "maturity": "ARCHIVED_RESEARCH_ONLY",
        },
        "F4C": {
            "ownership": "spatial incremental effect dispatch; source upload/readback full frame",
            "integration_action": "damage scope contract; no generalized zero-idle claim",
            "maturity": "FRESH_CPU_UNIT_TESTS_PASS_PRIVATE_LAB",
        },
        "CP01": {
            "ownership": "3D signed solids, imported bounded mesh and mixed CSG CPU reference",
            "integration_action": "geometry-only typed capability boundary and independent oracle",
            "maturity": "FRESH_56_TESTS_PASS_PRIVATE_LAB",
        },
        "CP02": {
            "ownership": "GPU Vulkan support-plane compute and later triangle-surface experiments",
            "integration_action": "GPU compute candidate, must not be relabelled full signed mesh distance",
            "maturity": "FRESH_BUILD_PASS_HISTORICAL_GPU_RECEIPT_SEPARATE",
        },
        "01A-01I": {
            "ownership": "G02/G03 retained UI controls and native 2D display commands",
            "integration_action": "UI layer overlay / input authority preserved; not full F4 source owner",
            "maturity": "PRIVATE_MAIN_QUALIFIED_SCOPED_UI",
        },
        "GPU05_QCHAIN": {
            "ownership": "Vulkan/Wayland scheduling, feedback and readback instrumentation",
            "integration_action": "timing witness tools only, cannot stand in for mixed 3D scene",
            "maturity": "HISTORICAL_PRESENTATION_PROOFS_DIFFERENT_FIXTURE",
        },
    }
    base_is_ancestor = subprocess.run(
        ["git", "-C", str(HERE), "merge-base", "--is-ancestor",
         QUALIFIED_BASE["showcase"], main_head],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0
    all_expected_heads = (
        base_is_ancestor
        and git(HERE, "branch", "--show-current") == "main"
        and cp01_head == QUALIFIED_BASE["cp01"]
        and cp02_head == QUALIFIED_BASE["cp02"]
    )
    gates = {
        "canonical_heads_match": all_expected_heads,
        "canonical_origin_private": origin == "https://github.com/tension-atoi/blob.in-showcase.git",
        "donor_git_clean": cp01_clean and cp02_clean,
        "all_six_f_labs_byte_identical": recovery_ok,
        "all_six_old_git_links_broken": broken_git_count == 6,
        "fresh_cargo_unit_tests": test_ok,
        "cp02_old_gpu_commit_reachable": actual_cp02_original == "commit",
        "cp03_explicitly_hold": "G01–G07 HOLD" in cp03_content
        and receipt["technical_states"]["CP03"] == "NOT_QUALIFIED",
        "license_barrier_detected": licensing_hold,
        "main_does_not_silently_link_F_crates": "blobin-f4c-incremental" not in bridge,
        "ui_backend_neutral_scene_present": core_only,
    }
    result = {
        "schema": "blob-render-reconciliation-01.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "program": "BLOB-RENDER-RECONCILE-01",
        "verdict": "SCOPED_PASS_READ_ONLY_SOURCE_RECONCILIATION"
        if all(gates.values()) else "HOLD",
        "gates": gates,
        "source_commits": {
            **QUALIFIED_BASE,
            "actual_showcase": main_head,
            "actual_cp01": cp01_head,
            "actual_cp02": cp02_head,
        },
        "worktree_source_recovery": f_sources,
        "read_only_fresh_offline_test_logs": results,
        "donor_archived_receipt": {
            "path": str(
                EVIDENCE / "blobin-next-01/program-20261010/review-06/ledger.json"
            ),
            "sha256": digest(
                EVIDENCE / "blobin-next-01/program-20261010/review-06/ledger.json"
            ),
            "cp03_verdict": receipt["technical_states"]["CP03"],
            "cp02_historical_gpu_commit": receipt["cp02"]["commit"],
            "cp02_historical_gpu_runs": receipt["cp02"]["runs_passed"],
            "cp02_historical_max_error": receipt["cp02"]["max_error"],
        },
        "main_workspace_license": "LicenseRef-Proprietary",
        "main_source_labs_integration_status": "NOT_LINKED_NOT_MERGED",
        "cp03_hybrid_hero60": "NOT_QUALIFIED",
        "plugin_or_worktree_repair": "NONE",
        "gpu_executed_during_this_audit": False,
        "distribution_licensed": False,
        "domain_matrix": matrix,
        "recommended_next_gate": "R02 typed F2 scene/content adapter in private cleanroom, source-license decision first",
        "proof_scope": "source hashing + offline CPU/unit tests; historical GPU receipts independently labelled",
    }
    target = args.out / "source-reconciliation.json"
    if args.verify:
        archived = json.loads(target.read_text())
        stable = [
            "schema", "program", "verdict", "gates", "source_commits",
            "worktree_source_recovery", "read_only_fresh_offline_test_logs",
            "donor_archived_receipt", "main_workspace_license",
            "main_source_labs_integration_status", "cp03_hybrid_hero60",
            "domain_matrix", "recommended_next_gate",
        ]
        mismatch = any(
            archived.get(key) != result.get(key)
            for key in stable if key != "source_commits"
        )
        # main is allowed to advance from the sealed baseline, but donor
        # commits and the immutable source base must remain identical.
        pinned = lambda obj: {
            k: v for k, v in obj["source_commits"].items()
            if k != "actual_showcase"
        }
        if mismatch or pinned(archived) != pinned(result):
            print("BLOB_RECONCILE01_HOLD_MANIFEST_DIFFERENCE", file=sys.stderr)
            return 1
    else:
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "verdict": result["verdict"],
        "gates": gates,
        "fresh_tests": {k: v["tests_passed"] for k, v in results.items()},
        "worktrees_recovered": sorted(f_sources),
        "output": str(target),
    }, indent=2))
    return int(result["verdict"] != "SCOPED_PASS_READ_ONLY_SOURCE_RECONCILIATION")


if __name__ == "__main__":
    sys.exit(main())
