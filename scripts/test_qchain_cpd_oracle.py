#!/usr/bin/env python3
"""CP-D adversarial oracle tests; only temporary symlinks are detached and mutated."""
from pathlib import Path
import tempfile
import unittest
import qchain_cpd_oracle as audit

ROOT=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpd-gpu-mask-01")
CPU=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/raw")
FIELDS=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpc-01/f3-fields")
BASE=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpc-01/f4")

def isolated(root):
    d=Path(root)
    d.mkdir(parents=True,exist_ok=True)
    for part in ("f2-mask","f4"):
        (d/part).mkdir()
        for f in (ROOT/part).iterdir():
            if f.is_file(): (d/part/f.name).symlink_to(f)
    (d/"f4-run.log").symlink_to(ROOT/"f4-run.log")
    return d
def overwrite_link(path,blob):
    path.unlink()
    path.write_bytes(blob)
class CPDOracleTests(unittest.TestCase):
    def test_positive_5_signed_masks_40_f4(self):
        r=audit.evaluate(ROOT,CPU,FIELDS,BASE)
        self.assertEqual((len(r["f2"]),len(r["f4"])),(5,40))
        self.assertFalse(r["device_resident_zero_copy"])

    def test_mask_bit_flip_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            r=isolated(Path(p)/"copy")
            f=r/"f2-mask/scene-00.gpu-f2-mask.bin"
            b=bytearray(f.read_bytes()); b[6500]^=1; overwrite_link(f,b)
            with self.assertRaisesRegex(ValueError,"GPU_SIGNED_MASK_MISMATCH"):
                audit.evaluate(r,CPU,FIELDS,BASE)

    def test_corrupt_mask_format_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            r=isolated(Path(p)/"copy")
            f=r/"f2-mask/scene-00.gpu-f2-mask.bin"
            b=bytearray(f.read_bytes()); b[6500]=2; overwrite_link(f,b)
            with self.assertRaisesRegex(ValueError,"GPU_SIGNED_MASK_FORMAT"):
                audit.evaluate(r,CPU,FIELDS,BASE)

    def test_fake_gpu_mask_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            r=isolated(Path(p)/"copy")
            f=r/"f4-run.log"
            text=f.read_text().replace("F2_GPU_SIGNED_MASK_VULKAN_READBACK_REUPLOAD","CPU_MASK")
            overwrite_link(f,text.encode())
            with self.assertRaisesRegex(ValueError,"GPU_PROVENANCE_NOT_OBSERVED"):
                audit.evaluate(r,CPU,FIELDS,BASE)

    def test_scene_identity_substitution_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            r=isolated(Path(p)/"copy")
            f=r/"f2-mask/gpu-f2-mask-ledger.tsv"
            records=f.read_text().splitlines()
            first=records[1].split("\t")
            final=records[5].split("\t")
            final[2]=first[2]
            records[5]="\t".join(final)
            overwrite_link(f,("\n".join(records)+"\n").encode())
            with self.assertRaisesRegex(ValueError,"F2_GPU_MASK_IDENTITY"):
                audit.evaluate(r,CPU,FIELDS,BASE)

    def test_f4_dispatch_omission_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            r=isolated(Path(p)/"copy")
            f=r/"f4/ledger-dpr2-reducedtrue.tsv"
            records=f.read_text().splitlines()
            first=records[1].split("\t")
            first[9]="3"
            records[1]="\t".join(first)
            overwrite_link(f,("\n".join(records)+"\n").encode())
            with self.assertRaisesRegex(ValueError,"F4_GPU_DISPATCH_MISSING"):
                audit.evaluate(r,CPU,FIELDS,BASE)

if __name__=="__main__":
    unittest.main(verbosity=2)
