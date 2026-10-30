#!/usr/bin/env python3
"""CP-JA6 source-immutable adversarial generation oracle."""
import tempfile,unittest,hashlib
from pathlib import Path
from PIL import Image
import qchain_cpja6_independent_oracle as oracle
R=Path("/mnt/workbench/evidence/runs/qchain-cpja6-20261010-01/runs/reconfigure-01")
BASE=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
CPU=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-reconciliation.json")
V=Path("/home/tension_atoi/Projects/.worktrees/blobin-showcase-qcja6-20261010/vendor/wgpu-hal-30.0.1")
def clone(root):
    d=Path(root)/"run";d.mkdir()
    for p in R.iterdir():
        if p.name=="engine-ledger":
            e=d/p.name;e.mkdir()
            for q in p.iterdir():(e/q.name).symlink_to(q)
        elif p.is_file():(d/p.name).symlink_to(p)
    return d
def replace(root,name,fn):
    p=root/name;orig=p.read_bytes();new=fn(orig)
    assert orig!=new
    p.unlink()
    p.write_bytes(new)
def verify(root):
    return oracle.verify(root,BASE,CPU,V)
class GenerationCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hashes={p:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [R/"viewer.stderr",R/"viewer.stdout",
                      R/"weston-timeline-proto.log",R/"sample-03.png"]}
    @classmethod
    def tearDownClass(cls):
        assert all(hashlib.sha256(p.read_bytes()).hexdigest()==v
            for p,v in cls.hashes.items()),"SOURCE_EVIDENCE_MUTATED"
    def test_01_real_reconfigure(self):
        self.assertEqual(verify(R)["generation_frame_counts"],[60,60])

    def test_02_missing_last_ack(self):
        with tempfile.TemporaryDirectory() as temp:
            d=clone(temp)
            def remove(b):
                lines=b.splitlines(keepends=True)
                ix=max(i for i,x in enumerate(lines)
                       if b"CPJA6_TYPED_ACK generation=2 present_id=60" in x)
                lines.pop(ix)
                return b"".join(lines)
            replace(d,"viewer.stderr",remove)
            with self.assertRaisesRegex(ValueError,"TYPED_ACK_COUNT"):
                verify(d)
    def test_03_old_generation_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            d=clone(temp)
            replace(d,"viewer.stderr",lambda b:b.replace(
                b"CPJA6_TYPED_ACK generation=2 present_id=1 ",
                b"CPJA6_TYPED_ACK generation=1 present_id=1 ",1))
            with self.assertRaisesRegex(ValueError,"GENERATION_MIXED"):
                verify(d)
    def test_04_id_reused_in_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            d=clone(temp)
            replace(d,"viewer.stderr",lambda b:b.replace(
                b"CPJA6_TYPED_ACK generation=2 present_id=35 ",
                b"CPJA6_TYPED_ACK generation=2 present_id=34 ",1))
            with self.assertRaisesRegex(ValueError,"PRESENT_ID_SCOPE_INCONSISTENT"):
                verify(d)
    def test_05_no_reconfigure_witness(self):
        with tempfile.TemporaryDirectory() as temp:
            d=clone(temp)
            replace(d,"viewer.stdout",lambda b:b.replace(
                b"CPJA6_RECONFIGURE_COMPLETE before_seq=60",
                b"CPJA6_RECONFIGURE_MISSING before_seq=60",1))
            with self.assertRaisesRegex(ValueError,"ONE_RECONFIGURE_MUST_BE_WITNESSED"):
                verify(d)

    def test_06_missing_weston_event(self):
        with tempfile.TemporaryDirectory() as temp:
            d=clone(temp)
            def drop(b):
                a=b.splitlines(keepends=True)
                i=max(i for i,line in enumerate(a)
                      if b"ev wp_presentation_feedback@" in line and b".presented(" in line)
                a.pop(i);return b"".join(a)
            replace(d,"weston-timeline-proto.log",drop)
            with self.assertRaisesRegex(ValueError,"WAYLAND_CLIENT_SERVER_FEEDBACK_DIVERGENCE"):
                verify(d)
if __name__=="__main__":unittest.main(verbosity=2)
