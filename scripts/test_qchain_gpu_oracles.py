#!/usr/bin/env python3
"""Negative controls mutate temporary copies only; canonical evidence stays untouched."""
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
import qchain_f3_fields_oracle as f3o
import qchain_independent_oracle as full

CPU=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/raw")
RECEIPT=CPU.parent/"qchain-reconciliation.json"
BASE=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01")
F2=BASE/"20261010-cpa-cpb-01/f2"
F3=BASE/"20261010-cpa-cpb-01/f3"
F4=BASE/"20261010-cpc-01/f4"
FIELDS=BASE/"20261010-cpc-01/f3-fields"

def links(source, target):
    target.mkdir()
    for f in source.iterdir():
        if f.is_file(): (target/f.name).symlink_to(f)

class NegativeLawTests(unittest.TestCase):
    def test_archive_readback_is_accepted(self):
        self.assertEqual(len(f3o.evaluate(FIELDS,CPU,RECEIPT)["stages"]),5)

    def test_corrupted_gpu_mask_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"probe"; links(FIELDS,root)
            dst=root/"scene-00.gpu-mask.bin"
            content=bytearray(dst.read_bytes()); content[15000]^=1
            dst.unlink(); dst.write_bytes(content)
            with self.assertRaisesRegex(ValueError,"F3_GPU_BINARY_MASK_MISMATCH"):
                f3o.evaluate(root,CPU,RECEIPT)

    def test_nonfinite_gpu_numeric_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"probe"; links(FIELDS,root)
            dst=root/"scene-00.gpu-height.f32"
            content=bytearray(dst.read_bytes()); content[:4]=struct.pack("<f",float("nan"))
            dst.unlink(); dst.write_bytes(content)
            with self.assertRaisesRegex(ValueError,"F3_NONFINITE"):
                f3o.evaluate(root,CPU,RECEIPT)

    def test_corrupted_gpu_rgba_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"probe"; links(FIELDS,root)
            dst=root/"scene-00.gpu-rgba.bin"
            content=bytearray(dst.read_bytes()); content[10]=255-content[10]
            dst.unlink(); dst.write_bytes(content)
            with self.assertRaisesRegex(ValueError,"F3_RGBA_OUT_OF_BUDGET"):
                f3o.evaluate(root,CPU,RECEIPT)

    def test_reused_pixel_identity_cannot_spoof_scene_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"f2"; links(F2,root)
            dst=root/"ledger-dpr2.tsv"
            data=dst.read_text()
            first=data.splitlines()[1].split("\t")[5]
            rows=data.splitlines()
            last=rows[5].split("\t"); last[5]=first; rows[5]="\t".join(last)
            dst.unlink(); dst.write_text("\n".join(rows)+"\n")
            with self.assertRaisesRegex(ValueError,"F2_SEMANTIC_DIGEST_WRONG"):
                full.verify(CPU,root,F3,F4,RECEIPT)

if __name__=="__main__": unittest.main(verbosity=2)
