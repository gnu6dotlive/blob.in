#!/usr/bin/env python3
"""Adversarial tests of dual swapchain exact ID authority; donors immutable."""
import hashlib,tempfile,unittest
from pathlib import Path
import qchain_cpja7_independent_oracle as o
R=Path("/mnt/workbench/evidence/runs/qchain-cpja7-20261010-01/runs/dual-02")
D=Path("/mnt/workbench/evidence/runs/qchain-cpja7-20261010-01/runs/drop-01")
B=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
C=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-reconciliation.json")
def copy(root,src):
    dest=Path(root)/"run";dest.mkdir()
    for p in src.iterdir():
        if p.name=="engine-ledger":
            path=dest/p.name;path.mkdir()
            for item in p.iterdir():(path/item.name).symlink_to(item)
        elif p.is_file():(dest/p.name).symlink_to(p)
    return dest
def change(root,name,fn):
    p=root/name;before=p.read_bytes();after=fn(before)
    assert before!=after
    p.unlink();p.write_bytes(after)
class MultiSwapchainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.witness={p:hashlib.sha256(p.read_bytes()).hexdigest()
            for r in (R,D) for p in (r/"viewer.stdout",r/"viewer.stderr",
                                      r/"weston-timeline-proto.log",r/"sample-03.png")}
    @classmethod
    def tearDownClass(cls):
        assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h
                   for p,h in cls.witness.items()),"ORIGINAL_EVIDENCE_MUTATED"
    def test_01_dual_positive(self):
        x=o.analyze(R,B,C,"dual")
        self.assertEqual((x["primary_vk_wait_success"],x["secondary_vk_wait_success"]),(120,120))
    def test_02_drop_holds_compositor(self):
        x=o.analyze(D,B,C,"drop")
        self.assertFalse(x["visible_window_samples_exact"])
        self.assertEqual(x["secondary_vk_wait_success"],60)
    def test_03_missing_final_secondary_ack(self):
        with tempfile.TemporaryDirectory() as t:
            d=copy(t,R)
            def drop(raw):
                lines=raw.splitlines(keepends=True)
                ix=max(i for i,x in enumerate(lines)
                    if b"CPJA6_TYPED_ACK generation=2 present_id=120 " in x)
                lines.pop(ix)
                return b"".join(lines)
            change(d,"viewer.stderr",drop)
            with self.assertRaisesRegex(ValueError,"SECONDARY_SWAPCHAIN_TYPED_ACK_DRIFT"):
                o.analyze(d,B,C,"dual")
    def test_04_replayed_secondary_id(self):
        with tempfile.TemporaryDirectory() as t:
            d=copy(t,R)
            change(d,"viewer.stderr",lambda b:b.replace(
                b"CPJA6_TYPED_ACK generation=2 present_id=75 ",
                b"CPJA6_TYPED_ACK generation=2 present_id=74 ",1))
            with self.assertRaisesRegex(ValueError,"SECONDARY_SWAPCHAIN_TYPED_ACK_DRIFT"):
                o.analyze(d,B,C,"dual")
    def test_05_cross_generation_relabel(self):
        with tempfile.TemporaryDirectory() as t:
            d=copy(t,R)
            change(d,"viewer.stderr",lambda b:b.replace(
                b"CPJA6_TYPED_ACK generation=2 present_id=75 ",
                b"CPJA6_TYPED_ACK generation=1 present_id=75 ",1))
            with self.assertRaisesRegex(ValueError,"PRIMARY_SWAPCHAIN_TYPED_ACK_DRIFT"):
                o.analyze(d,B,C,"dual")
    def test_06_server_presentation_missing(self):
        with tempfile.TemporaryDirectory() as t:
            d=copy(t,R)
            def remove(raw):
                lines=raw.splitlines(keepends=True)
                ix=max(i for i,x in enumerate(lines)
                    if b"ev wp_presentation_feedback@" in x and b".presented(" in x)
                lines.pop(ix)
                return b"".join(lines)
            change(d,"weston-timeline-proto.log",remove)
            with self.assertRaisesRegex(ValueError,"WAYLAND_CLIENT_SERVER_DISAGREEMENT"):
                o.analyze(d,B,C,"dual")
if __name__=="__main__":unittest.main(verbosity=2)
