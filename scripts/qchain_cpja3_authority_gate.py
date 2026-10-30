#!/usr/bin/env python3
"""Bounded CP-JA3 Vulkan present-wait authority gate.

Runtime probe proves physical capabilities only. The exact experimental
wgpu-hal device-extension log proves configured device extensions.
No unsupported vkWaitForPresentKHR call may be issued.
"""
import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

def require(cond, message):
    if not cond:
        raise ValueError(message)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def inspect(probe, runtime, swapchain):
    physical = probe.read_text()
    actual = runtime.read_text()
    backend = swapchain.read_text()
    line = next((x for x in physical.splitlines()
        if x.startswith('CPJA3_VK_DEVICE name="NVIDIA GeForce RTX 3070"')), None)
    require(line is not None, "PHYSICAL_DEVICE_NOT_QUALIFIED")
    fields = dict(re.findall(r'(present_id_supported|present_wait_supported|present_id_feature|present_wait_feature)=(true|false)', line))
    require(len(fields)==4, "FEATURES_NOT_RECORDED")
    match = re.search(r'Supported extensions: (\[[^\n]+\])',actual)
    require(match is not None, "WGPU_DEVICE_EXTENSION_LOG_MISSING")
    enabled = ast.literal_eval(match.group(1))
    require(isinstance(enabled,list) and all(isinstance(x,str) for x in enabled),
            "ENABLED_EXTENSIONS_INVALID")
    require("VK_KHR_swapchain" in enabled, "VK_SWAPCHAIN_NOT_ENABLED")
    require('let vk_info = vk::PresentInfoKHR::default()' in backend,
            "WSI_IMPLEMENTATION_DRIFT")
    block = backend.split('let vk_info = vk::PresentInfoKHR::default()',1)[1]
    block = block.split('self.functor.queue_present(queue.raw, &vk_info)',1)[0]
    require('let suboptimal =' in block,"SWAPCHAIN_PRESENT_PATH_DRIFT")
    id_attached = ('PresentIdKHR' in block or 'present_ids(' in block)
    device_id="VK_KHR_present_id" in enabled
    device_wait="VK_KHR_present_wait" in enabled
    # Present wait cannot be authorized until *all three* requirements hold.
    candidate = device_id and device_wait and id_attached
    # Diagnostic logs and copied source can be forged. Only typed runtime
    # device state + present IDs + a successful bounded wait may authorize use.
    allowed = False
    return {"physical_device":"NVIDIA GeForce RTX 3070",
      "physical_support":{k:v=="true" for k,v in fields.items()},
      "wgpu_enabled_extensions":enabled,
      "wgpu_device_present_id_enabled":device_id,
      "wgpu_device_present_wait_enabled":device_wait,
      "vk_queue_present_typed_id_attached":id_attached,
      "textual_preflight_candidate":candidate,
      "typed_runtime_device_attestation":False,
      "actual_present_id_assigned_to_each_frame":False,
      "successful_vk_wait_for_present":False,
      "typed_vk_wait_for_present_authorized":allowed,
      "verdict":"CPJA3_TYPED_PRESENT_WAIT_GATE_READY" if allowed else
                "CPJA3_TYPED_PRESENT_WAIT_NOT_ENABLED_HOLD",
      "probe_sha256":sha(probe),
      "viewer_runtime_trace_sha256":sha(runtime),
      "wgpu_hal_swapchain_source_sha256":sha(swapchain),
      "limits":"Observational evidence and source verification, not device-handle attestation"}


def main():
    p=argparse.ArgumentParser()
    for name in ('probe','runtime','swapchain','out'):
        p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args()
    require(not a.out.exists(),'REFUSE_OVERWRITE')
    result=inspect(a.probe,a.runtime,a.swapchain)
    a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(result['verdict'], 'physical_available',result['physical_support'],
          'device_enabled',result['wgpu_device_present_wait_enabled'],
          'ids_attached',result['vk_queue_present_typed_id_attached'])
    if not result['typed_vk_wait_for_present_authorized']:
        raise SystemExit(2)
if __name__=='__main__':main()
