#!/usr/bin/env python3
"""CP-E negative oracle controls: mutate private temp symlinks, never original evidence."""
import tempfile
import unittest
from pathlib import Path
import qchain_cpe_oracle as oracle

ROOT=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01")
RAW=ROOT/"20261010-cpe-resident-01/raw"
CPU=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/raw")
PREVIOUS=ROOT/"20261010-cpd-gpu-mask-01/f4"
FIELDS=ROOT/"20261010-cpc-01/f3-fields"
RECEIPT=CPU.parent/"qchain-reconciliation.json"
LOG=ROOT/"20261010-cpe-resident-01/compute.log"

def links(target):
    target.mkdir()
    for file in RAW.iterdir():
        if file.is_file(): (target/file.name).symlink_to(file)
def corrupt(path,contents):
    path.unlink()
    path.write_bytes(contents)
class ResidentOracleTests(unittest.TestCase):
    def test_reference_stays_accepted(self):
        report=oracle.verify(RAW,CPU,PREVIOUS,FIELDS,RECEIPT,LOG)
        self.assertEqual((len(report["frames"]),len(report["fields"])),(40,5))
    def test_corrupt_gpu_mask_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"raw";links(source)
            path=source/"scene-00.gpu-f2-mask.bin"
            data=bytearray(path.read_bytes());data[12000]^=1;corrupt(path,data)
            with self.assertRaisesRegex(ValueError,"RESIDENT_GPU_F2_MASK_DIFFERENCE"):
                oracle.verify(source,CPU,PREVIOUS,FIELDS,RECEIPT,LOG)
    def test_multi_submit_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"raw";links(source)
            path=source/"resident-ledger.tsv";data=path.read_text().splitlines()
            row=data[1].split("\t");row[9]="2";data[1]="\t".join(row)
            corrupt(path,("\n".join(data)+"\n").encode())
            with self.assertRaisesRegex(ValueError,"MULTI_SUBMIT_DRIFT"):
                oracle.verify(source,CPU,PREVIOUS,FIELDS,RECEIPT,LOG)

    def test_hidden_host_bridge_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"raw";links(source)
            path=source/"resident-ledger.tsv";data=path.read_text().splitlines()
            row=data[1].split("\t");row[10]="1";data[1]="\t".join(row)
            corrupt(path,("\n".join(data)+"\n").encode())
            with self.assertRaisesRegex(ValueError,"INTERMEDIATE_CPU_BRIDGE"):
                oracle.verify(source,CPU,PREVIOUS,FIELDS,RECEIPT,LOG)
    def test_reused_pixel_scene_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"raw";links(source)
            path=source/"resident-ledger.tsv";data=path.read_text().splitlines()
            first=data[1].split("\t");last=data[-1].split("\t")
            last[3]=first[3];data[-1]="\t".join(last)
            corrupt(path,("\n".join(data)+"\n").encode())
            with self.assertRaisesRegex(ValueError,"SCENE_IDENTITY_SPOOF"):
                oracle.verify(source,CPU,PREVIOUS,FIELDS,RECEIPT,LOG)
    def test_f4_byte_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"raw";links(source)
            path=source/"state0-ceramic-frame0-dpr2.gpu-rgba.bin"
            data=bytearray(path.read_bytes());data[70000]^=1;corrupt(path,data)
            with self.assertRaisesRegex(ValueError,"RESIDENT_GPU_FRAME_REGRESSION"):
                oracle.verify(source,CPU,PREVIOUS,FIELDS,RECEIPT,LOG)
if __name__=="__main__":unittest.main(verbosity=2)
