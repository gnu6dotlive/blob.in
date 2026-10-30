#!/usr/bin/env python3
"""CP-F negative mutation suite: never modify original reference evidence."""
from pathlib import Path
import tempfile
import unittest
import qchain_cpf_oracle as audit

R=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01")
RAW=R/"20261010-cpf-persistent-01/raw"
BASE=R/"20261010-cpe-resident-01/raw"
CPU=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/raw")
RECEIPT=CPU.parent/"qchain-reconciliation.json"
LOG=R/"20261010-cpf-persistent-01/compute.log"
OLD=R/"20261010-cpe-resident-01/independent-oracle.json"
def isolated(root):
    p=Path(root)/"raw";p.mkdir()
    for item in RAW.iterdir():
        if item.is_file(): (p/item.name).symlink_to(item)
    return p
def write_modified(path,content):
    path.unlink()
    path.write_bytes(content)
def check(raw):
    return audit.verify(raw,BASE,CPU,RECEIPT,LOG,OLD)
class SessionOracleTests(unittest.TestCase):
    def test_original_is_accepted(self):
        v=check(RAW)
        self.assertEqual(v["baseline_files_exact"],51)
    def test_corrupt_frame_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=isolated(tmp);p=raw/"state0-ceramic-frame0-dpr2.gpu-rgba.bin"
            b=bytearray(p.read_bytes());b[6000]^=1;write_modified(p,b)
            with self.assertRaisesRegex(ValueError,"BASELINE_BYTES_MISMATCH"):
                check(raw)
    def test_device_recreation_forgery_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=isolated(tmp);p=raw/"session-stats.tsv"
            lines=p.read_text().splitlines()
            fields=lines[1].split("\t");fields[0]="40"
            write_modified(p,(lines[0]+"\n"+"\t".join(fields)+"\n").encode())
            with self.assertRaisesRegex(ValueError,"SESSION_REUSE_CONTRACT"):
                check(raw)

    def test_scene_four_identity_cannot_spoof_scene_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=isolated(tmp);p=raw/"resident-ledger.tsv"
            lines=p.read_text().splitlines()
            source=lines[1].split("\t")[3]
            fields=lines[-1].split("\t")
            fields[3]=source
            lines[-1]="\t".join(fields)
            write_modified(p,("\n".join(lines)+"\n").encode())
            with self.assertRaisesRegex(ValueError,"SCENE_SEMANTIC_BINDING"):
                check(raw)
    def test_intermediate_host_bridge_claim_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=isolated(tmp);p=raw/"resident-ledger.tsv"
            lines=p.read_text().splitlines()
            fields=lines[1].split("\t");fields[10]="1"
            lines[1]="\t".join(fields)
            write_modified(p,("\n".join(lines)+"\n").encode())
            with self.assertRaisesRegex(ValueError,"RENDER_PATH_COUNTER_MISMATCH"):
                check(raw)
    def test_missing_mask_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=isolated(tmp)
            (raw/"scene-02.gpu-f2-mask.bin").unlink()
            with self.assertRaisesRegex(ValueError,"UNEXPECTED_OR_MISSING_OUTPUT"):
                check(raw)
if __name__=="__main__":
    unittest.main(verbosity=2)
