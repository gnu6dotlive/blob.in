#!/usr/bin/env python3
"""Adversarial software-compositor oracle tests; immutable originals stay untouched."""
import json,hashlib,tempfile,unittest
from pathlib import Path
from PIL import Image
import qchain_gpu_compositor_gate as audit
from qchain_compositor_gate import compare_rgba
ROOT=Path("/mnt/workbench/evidence/runs/qchain-gpu-ipc-wayland-20261010-01")
GOOD=Path("/mnt/workbench/evidence/runs/qchain-gpu-ipc-wayland-20261010-02/wayland")
BAD=ROOT/"wayland"
MANIFEST=ROOT/"compute/gpu-source-manifest.json"
CPU=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-reconciliation.json")
RAW=ROOT/"compute/raw"
RUNLOG=ROOT/"compute/compute.log"
def check(e=GOOD,m=MANIFEST,r=RAW):
 return audit.evaluate(e,m,CPU,r,RUNLOG)
def isolated(root):
 p=Path(root)/"capture";p.mkdir()
 for file in GOOD.iterdir():
  if file.is_file(): (p/file.name).symlink_to(file)
 return p
def changed(path,payload):
 path.unlink();path.write_bytes(payload)
class GpuCompositorTests(unittest.TestCase):
 def test_five_gpu_captures_pass_with_fixed_corner_mask(self):
  report=check()
  self.assertEqual(report["total_mismatches_outside_authorized_mask"],0)
  self.assertEqual(len(report["stages"]),5)
 def test_original_bad_stage_zero_is_rejected(self):
  with self.assertRaisesRegex(ValueError,"COMPOSITOR_OUTSIDE_MASK_MISMATCH_STAGE_0"):
   check(e=BAD)

 def test_version_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"manifest.json"
   doc=json.loads(MANIFEST.read_text())
   doc["transport_version"]="QCHAIN-FRAME-v1"
   path.write_text(json.dumps(doc))
   with self.assertRaisesRegex(ValueError,"GPU_WIRE_VERSION_INVALID"):
    check(m=path)
 def test_scene_binding_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"manifest.json"
   doc=json.loads(MANIFEST.read_text())
   doc["stages"][4]["scene_sha256"]=doc["stages"][0]["scene_sha256"]
   path.write_text(json.dumps(doc))
   with self.assertRaisesRegex(ValueError,"SEMANTIC_SCENE_COLLISION"):
    check(m=path)
 def test_fixed_corner_mask(self):
  pixels=bytes(512*384*4)
  with self.assertRaisesRegex(ValueError,"UNSUPPORTED_CORNER_MASK"):
   compare_rgba(pixels,pixels,radius=19)
if __name__=="__main__":unittest.main(verbosity=2)
