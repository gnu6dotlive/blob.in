#!/usr/bin/env python3
"""Negative and positive oracle checks for BLOB-RENDER-RECONCILE-01.
Tests write only to temporary scratch space; donor sources are read-only.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("blob_render_reconcile01_audit.py")
SPEC = importlib.util.spec_from_file_location("blob_render_reconcile01_audit", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ReconciliationEvidenceTests(unittest.TestCase):
    def test_source_checksum_diff_detects_mutation(self):
        with tempfile.TemporaryDirectory(prefix="blob-reconcile-test-") as d:
            root = Path(d)
            first = root / "a"
            second = root / "b"
            first.mkdir()
            second.mkdir()
            for p in (first, second):
                (p / "lib.rs").write_text("pub fn boundary() {}\n")
                (p / "Cargo.toml").write_text("[package]\nname=\"sample\"\n")
                (p / "pixels.png").write_bytes(b"\0" * 20)
            self.assertEqual(AUDIT.source_snapshot(first), AUDIT.source_snapshot(second))
            (second / "lib.rs").write_text("pub fn boundary_changed() {}\n")
            self.assertNotEqual(AUDIT.source_snapshot(first), AUDIT.source_snapshot(second))
            self.assertEqual(len(AUDIT.source_snapshot(first)), 2)

    def test_failure_marker_is_not_accepted(self):
        with tempfile.TemporaryDirectory(prefix="blob-reconcile-test-") as d:
            target = Path(d) / "cargo-test.log"
            target.write_text("Finished test\n"
                              "test result: ok. 7 passed; 0 failed;\n"
                              "test result: FAILED. 0 passed; 1 failed;\n")
            result = AUDIT.test_summary(target)
            self.assertEqual(result["tests_passed"], 7)
            self.assertTrue(result["any_failed_suite"])

    def test_sealed_manifest_rejects_corruption(self):
        original = AUDIT.HERE / "evidence/runs/blob-render-reconcile-01-20261012/source-reconciliation.json"
        with tempfile.TemporaryDirectory(prefix="blob-reconcile-seal-") as d:
            destination = Path(d) / "source-reconciliation.json"
            data = json.loads(original.read_text())
            data["worktree_source_recovery"]["F2"]["source_manifest"]["src/lib.rs"] = "0" * 64
            destination.write_text(json.dumps(data))
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--verify", "--out", d],
                capture_output=True, text=True, timeout=20,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("HOLD_MANIFEST_DIFFERENCE", proc.stderr)


if __name__ == "__main__":
    unittest.main()
