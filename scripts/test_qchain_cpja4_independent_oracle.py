#!/usr/bin/env python3
"""CP-JA4 adversarial oracle inputs on isolated symlink fixtures only.

Never write through symlinks to original CP-JA4 evidence.
"""
import hashlib,tempfile,unittest
from pathlib import Path
from PIL import Image
import qchain_cpja4_independent_oracle as oracle
R=Path("/mnt/workbench/evidence/runs/qchain-cpja4-20261010-01/runs/ash-native-01")
BASE=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
CPU=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-reconciliation.json")
SRC=Path("/home/tension_atoi/Projects/.worktrees/blobin-showcase-qcja4-20261010/crates/showcase/src/bin/qchain_cpja4_vk_present_wait.rs")
def copy_refs(d):
    root=Path(d)/"run";root.mkdir()
    for f in R.iterdir():
        if f.name=="engine-ledger":
            sub=root/f.name;sub.mkdir()
            for child in f.iterdir():(sub/child.name).symlink_to(child)
        elif f.is_file():(root/f.name).symlink_to(f)
    return root
def mutate(root,name,fn):
    p=root/name
    src=p.read_bytes()
    changed=fn(src)
    assert changed!=src
    p.unlink() # cannot mutate donor
    p.write_bytes(changed)
def verify(run=R,src=SRC):
    return oracle.verify(run,BASE,CPU,src)
class TypedWaitAdversarial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baselines={p:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (R/"viewer.stdout",R/"viewer.stderr",
                      R/"weston-timeline-proto.log",R/"sample-03.png",SRC)}
    @classmethod
    def tearDownClass(cls):
        assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h
                   for p,h in cls.baselines.items()),"IMMUTABLE_DONOR_ALTERED"
    def test_positive_120_true_waits(self):
        self.assertEqual(verify()["per_frame_vk_wait_for_present_success"],120)

    def test_missing_terminal_typed_ack_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            run=copy_refs(d)
            def remove_tail(x):
                lines=x.decode().splitlines(keepends=True)
                i=max(i for i,line in enumerate(lines)
                      if line.startswith("CPJA4_TYPED_PRESENT_ACK seq=119 "))
                lines.pop(i)
                return "".join(lines).encode()
            mutate(run,"viewer.stdout",remove_tail)
            with self.assertRaisesRegex(ValueError,"TYPED_ACK_COUNT"):
                verify(run)
    def test_duplicate_present_id_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            run=copy_refs(d)
            mutate(run,"viewer.stdout",lambda b:b.replace(
                b"seq=65 present_id=66 ",b"seq=65 present_id=65 ",1))
            with self.assertRaisesRegex(ValueError,"PRESENT_ID_SEQUENCE_DRIFT"):
                verify(run)
    def test_tampered_gpu_frame_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            run=copy_refs(d)
            # Source transport receipts and native presenter SHA must agree.
            mutate(run,"viewer.stdout",lambda b:b.replace(
                b"seq=65 present_id=66 scene_sha256=",
                b"seq=65 present_id=66 scene_sha256=",0).replace(
                b"wait_result=VK_SUCCESS",b"wait_result=VK_TIMEOUT",1))
            with self.assertRaisesRegex(ValueError,"TYPED_ACK_COUNT"):
                verify(run)
    def test_missing_server_feedback_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            run=copy_refs(d)
            def remove(x):
                lines=x.decode().splitlines(keepends=True)
                i=max(i for i,line in enumerate(lines)
                      if "ev wp_presentation_feedback@" in line and ".presented(" in line)
                lines.pop(i)
                return "".join(lines).encode()
            mutate(run,"weston-timeline-proto.log",remove)
            with self.assertRaisesRegex(ValueError,"WAYLAND_CLIENT_SERVER_PRESENTATION_MISMATCH"):
                verify(run)

    def test_compositor_centre_pixel_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            run=copy_refs(d)
            png=run/"sample-03.png"
            image=Image.open(png).convert("RGBA")
            old=image.getpixel((256,192))
            image.putpixel((256,192),((old[0]+37)%256,old[1],old[2],old[3]))
            png.unlink()
            image.save(png)
            with self.assertRaisesRegex(ValueError,"COMPOSITOR_PIXEL_MISMATCH_3"):
                verify(run)
if __name__=="__main__":unittest.main(verbosity=2)
