#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
from cp03_i01_source_audit import inventory, witness

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cp03-scene-")
        r = Path(self.tmp.name)
        self.history = r / "history"
        self.experiment = r / "experiment"
        self.cuda = r / "cuda"
        self.receipts = r / "receipts"
        (self.history / "blobin-core/src").mkdir(parents=True)
        (self.experiment / "F4/src").mkdir(parents=True)
        self.cuda.mkdir()
        self.receipts.mkdir()
        fixtures = {
            self.history / "blobin-core/src/path.rs": "cubic Contour Path",
            self.history / "blobin-core/src/tessellate.rs": "pub struct Mesh pub x: f32 pub y: f32 lyon",
            self.history / "blobin-core/src/blob.rs": "pub trait Blob wobble Path",
            self.history / "blobin-core/src/solve.rs": "pub struct Spring pub fn tick",
            self.experiment / "F4/src/gpu_session.rs": "pub struct PersistentSession render_next",
            self.cuda / "csg.cu": "struct Primitive float x, y, radius compose(",
            self.cuda / "README.md": "not a general arbitrary synthetic Private research",
            self.receipts / "cp03-numeric-gate.json": json.dumps(
                {"cp03_pass": False, "metrics_pass": False,
                 "input_samples_count": 0, "verdict": "NOT_QUALIFIED"})
        }
        for f, content in fixtures.items():
            f.write_text(content)

    def tearDown(self):
        self.tmp.cleanup()

    def audit(self):
        return inventory(self.history, self.experiment, self.cuda, self.receipts)
    def test_donor_sources_do_not_prove_scene(self):
        r = self.audit()
        self.assertEqual(r["status"], "DONOR_INVENTORY_PASS")
        self.assertFalse(r["cp03_hybrid60_pass"])
        self.assertEqual(set(r["cp03_gates"].values()), {"HOLD"})
        self.assertFalse(r["integrated_scene"]["mixed_boolean_3d"])

    def test_missing_donor_is_hold(self):
        (self.cuda / "csg.cu").unlink()
        r = self.audit()
        self.assertEqual(r["status"], "DONOR_INVENTORY_HOLD")

    def test_invalid_prior_receipt_is_rejected(self):
        (self.receipts / "cp03-numeric-gate.json").write_text(json.dumps({
            "cp03_pass": True, "metrics_pass": True,
            "input_samples_count": 0, "verdict": "PASS"}))
        with self.assertRaises(ValueError):
            self.audit()
    def test_filename_cannot_substitute_geometry(self):
        path = Path(self.tmp.name) / "closed_mesh.rs"
        path.write_text("filename only")
        r = witness(path, ["pub struct Mesh", "pub x: f32"])
        self.assertEqual(r["status"], "SOURCE_UNCONFIRMED")

    def test_real_scene_not_inferred_from_old_receipt(self):
        r = self.audit()
        self.assertFalse(r["integrated_scene"]["actual_native_1280x720_scene_executed"])
        self.assertFalse(r["integrated_scene"]["closed_mesh_3d"])
        self.assertFalse(r["integrated_scene"]["open_mesh_3d"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
