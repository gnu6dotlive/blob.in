#!/usr/bin/env python3
"""Adversarial negatives: textual evidence never authorizes Vulkan present-wait."""
import tempfile
import unittest
from pathlib import Path
import qchain_cpja3_authority_gate as gate

R=Path("/mnt/workbench/evidence/runs/qchain-cpja3-20261010-01")
PROBE=R/"probes/vulkan-runtime.txt"
RUNTIME=R/"probes/runtime-viewer-01/viewer.stderr"
NATIVE=R/"source-snapshot/wgpu-hal-30-native.rs"

class GateTests(unittest.TestCase):
    def test_runtime_physical_supported_but_logical_disabled(self):
        r=gate.inspect(PROBE,RUNTIME,NATIVE)
        self.assertTrue(all(r["physical_support"].values()))
        self.assertFalse(r["wgpu_device_present_wait_enabled"])
        self.assertFalse(r["wgpu_device_present_id_enabled"])
        self.assertFalse(r["vk_queue_present_typed_id_attached"])
        self.assertFalse(r["typed_vk_wait_for_present_authorized"])
    def test_no_device_extension_log_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"trace";p.write_text("GPU surface success\n")
            with self.assertRaisesRegex(ValueError,"WGPU_DEVICE_EXTENSION_LOG_MISSING"):
                gate.inspect(PROBE,p,NATIVE)
    def test_mutated_driver_identity_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"probe"
            p.write_text(PROBE.read_text().replace("RTX 3070","RTX 5080"))
            with self.assertRaisesRegex(ValueError,"PHYSICAL_DEVICE_NOT_QUALIFIED"):
                gate.inspect(p,RUNTIME,NATIVE)
    def test_phony_extension_log_still_not_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"trace"
            raw=RUNTIME.read_text()
            raw=raw.replace('"VK_KHR_swapchain",','"VK_KHR_swapchain", "VK_KHR_present_wait", "VK_KHR_present_id",',1)
            p.write_text(raw)
            r=gate.inspect(PROBE,p,NATIVE)
            self.assertTrue(r["wgpu_device_present_id_enabled"])
            self.assertFalse(r["vk_queue_present_typed_id_attached"])
            self.assertFalse(r["typed_vk_wait_for_present_authorized"])

    def test_forged_extensions_and_source_remain_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'trace'
            text=RUNTIME.read_text().replace('"VK_KHR_swapchain",',
                '"VK_KHR_swapchain", "VK_KHR_present_wait", "VK_KHR_present_id",',1)
            p.write_text(text)
            src=Path(tmp)/'swapchain.rs'
            code=NATIVE.read_text().replace(
                'let suboptimal = {',
                'let _fake_present_ids = "PresentIdKHR";\n        let suboptimal = {',1)
            src.write_text(code)
            outcome=gate.inspect(PROBE,p,src)
            self.assertTrue(outcome['textual_preflight_candidate'])
            self.assertFalse(outcome['typed_vk_wait_for_present_authorized'])
            self.assertFalse(outcome['actual_present_id_assigned_to_each_frame'])
if __name__=='__main__':unittest.main(verbosity=2)
