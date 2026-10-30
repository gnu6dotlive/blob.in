#!/usr/bin/env python3
"""Adversarial CP-JA5 typed WGPU-HAL oracle, donors strictly read-only."""
import hashlib,tempfile,unittest
from pathlib import Path
from PIL import Image
import qchain_cpja5_independent_oracle as oracle
ROOT=Path("/mnt/workbench/evidence/runs/qchain-cpja5-20261010-01/runs/hal-01")
BASE=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
CPU=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-reconciliation.json")
PATCH=Path("/home/tension_atoi/Projects/.worktrees/blobin-showcase-qcja5-20261010/vendor/wgpu-hal-30.0.1")
def clone(where):
    root=Path(where)/"run";root.mkdir()
    for f in ROOT.iterdir():
        if f.name=="engine-ledger":
            e=root/f.name;e.mkdir()
            for child in f.iterdir():(e/child.name).symlink_to(child)
        elif f.is_file():(root/f.name).symlink_to(f)
    return root
def mutate(root,name,transform):
    p=root/name
    source=p.read_bytes()
    changed=transform(source)
    assert source!=changed
    p.unlink()
    p.write_bytes(changed)
def qualify(r=ROOT):
    return oracle.verify(r,BASE,CPU,PATCH)
class TypedHalNegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        files=[ROOT/"viewer.stderr",ROOT/"viewer.stdout",
               ROOT/"weston-timeline-proto.log",ROOT/"sample-03.png",
               PATCH/"src/vulkan/swapchain/native.rs"]
        cls.original={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    @classmethod
    def tearDownClass(cls):
        assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h
                   for p,h in cls.original.items()),"SOURCE_EVIDENCE_WAS_MUTATED"
    def test_positive_native_hal_120(self):
        self.assertEqual(qualify()["native_vulkan_wait_success"],120)

    def test_missing_terminal_typed_ack(self):
        with tempfile.TemporaryDirectory() as t:
            r=clone(t)
            def drop(x):
                lines=x.splitlines(keepends=True)
                i=max(i for i,line in enumerate(lines)
                      if b"CPJA5_HAL_TYPED_PRESENT_ACK present_id=120 " in line)
                lines.pop(i);return b"".join(lines)
            mutate(r,"viewer.stderr",drop)
            with self.assertRaisesRegex(ValueError,"TYPED_PRESENT_ID_SEQUENCE_MISMATCH"):
                qualify(r)
    def test_duplicate_present_id(self):
        with tempfile.TemporaryDirectory() as t:
            r=clone(t)
            mutate(r,"viewer.stderr",lambda x:x.replace(
                b"CPJA5_HAL_TYPED_PRESENT_ACK present_id=65 ",
                b"CPJA5_HAL_TYPED_PRESENT_ACK present_id=64 ",1))
            with self.assertRaisesRegex(ValueError,"TYPED_PRESENT_ID_SEQUENCE_MISMATCH"):
                qualify(r)
    def test_unsupported_device_extension(self):
        with tempfile.TemporaryDirectory() as t:
            r=clone(t)
            mutate(r,"viewer.stderr",lambda x:x.replace(
                b"CPJA5_HAL_DEVICE_EXTENSIONS_ENABLE VK_KHR_present_id VK_KHR_present_wait",
                b"CPJA5_HAL_PRESENT_WAIT_EXTENSION_MISSING",1))
            with self.assertRaisesRegex(ValueError,"LOGICAL_DEVICE_FEATURES_NOT_ENABLED"):
                qualify(r)
    def test_server_feedback_missing(self):
        with tempfile.TemporaryDirectory() as t:
            r=clone(t)
            def drop(x):
                lines=x.splitlines(keepends=True)
                i=max(i for i,line in enumerate(lines)
                      if b"ev wp_presentation_feedback@" in line and b".presented(" in line)
                lines.pop(i);return b"".join(lines)
            mutate(r,"weston-timeline-proto.log",drop)
            with self.assertRaisesRegex(ValueError,"WAYLAND_FEEDBACK_CLIENT_SERVER_COUNT_DRIFT"):
                qualify(r)

    def test_source_image_pixel_mutation(self):
        with tempfile.TemporaryDirectory() as t:
            r=clone(t);p=r/"sample-03.png"
            im=Image.open(p).convert("RGBA")
            old=im.getpixel((256,192))
            im.putpixel((256,192),((old[0]+19)%256,old[1],old[2],old[3]))
            p.unlink()
            im.save(p)
            with self.assertRaisesRegex(ValueError,"COMPOSITOR_PIXEL_MISMATCH_3"):
                qualify(r)
if __name__=="__main__":unittest.main(verbosity=2)
