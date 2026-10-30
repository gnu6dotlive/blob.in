#!/usr/bin/env python3
"""Negative controls for independent Weston screenshot and source identity oracle."""
import json, tempfile, unittest
from pathlib import Path
import qchain_cpi01_independent_oracle as oracle

E=Path("/mnt/workbench/evidence/runs/qchain-cpi01-20261010-01/headless")
C=Path("/mnt/workbench/evidence/runs/qchain-gpu-endurance-20261010-01/test-cycles-soak20/cycle-20")
CPU=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-reconciliation.json")
def verify(cap=E/"run-01",log=E/"weston-debug.log",manifest=C/"gpu-source-manifest.json"):
    return oracle.verify(cap,log,C/"raw",manifest,C/"compute.log",CPU)
def copy_refs(root):
    root.mkdir()
    for f in (E/"run-01").iterdir():
        if f.is_file():(root/f.name).symlink_to(f)
    return root
class WestonNegativeTests(unittest.TestCase):
    def test_positive_five_exact_after_declared_vertical_flip(self):
        self.assertEqual(verify()["total_pixels_exact"],983040)
    def test_missing_compositor_yflip_claim_refused_as_pixel_drift(self):
        with tempfile.TemporaryDirectory() as d:
            log=Path(d)/"weston.log"
            log.write_text((E/"weston-debug.log").read_text().replace(
                "screen capture uses y-flip: yes","screen capture uses y-flip: no"))
            with self.assertRaisesRegex(ValueError,"WAYLAND_PIXEL_PARITY_RED_STAGE_0"):
                verify(log=log)
    def test_mutated_central_pixel_in_captured_png_is_rejected(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            root=copy_refs(Path(d)/"captures")
            target=root/"stage-02.png"
            image=Image.open(target).convert("RGBA")
            old=image.getpixel((200,160))
            image.putpixel((200,160),((old[0]+67)%256,old[1],old[2],old[3]))
            target.unlink();image.save(target)
            with self.assertRaisesRegex(ValueError,"WAYLAND_PIXEL_PARITY_RED_STAGE_2"):
                verify(cap=root)
    def test_equal_pixel_scene_identity_substitution_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            m=json.loads((C/"gpu-source-manifest.json").read_text())
            m["stages"][4]["scene_sha256"]=m["stages"][0]["scene_sha256"]
            path=Path(d)/"manifest.json";path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,"SEMANTIC_SCENE_BINDING_MISMATCH"):
                verify(manifest=path)
    def test_garbage_gpu_compute_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            m=json.loads((C/"gpu-source-manifest.json").read_text())
            m["compute_run_log_sha256"]="0"*64
            path=Path(d)/"manifest.json";path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,"COMPUTE_RECEIPT_MISMATCH"):
                verify(manifest=path)
if __name__=="__main__":unittest.main(verbosity=2)
