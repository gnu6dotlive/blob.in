# CP-JA3 — Typed Presentation Authority / WSI Boundary

Date: 2026-10-10. Parent: CP-JA2 `9cc4d636ee8d52c6cd5be6431a58763a15c843cd`.
Branch: `feat/qchain-wsi-typed-authority-20261010`.
Scope: private local NVIDIA RTX 3070, wgpu 30.0.1 / wgpu-hal 30.0.1 / winit 0.30.13, Weston 15 headless.

## Goal

Resolve the actual owner of presentation feedback and prove whether Vulkan present-wait is available **and activated** on the live wgpu device. Do not infer a typed ACK from diagnostic text. Keep CP03 HYBRID-60 and the final client-feedback drain gate OPEN until evidence exists.

## Causal findings

- The native GPU viewer computes **120 frames in a single persistent CP-F Vulkan session** and hands them through authenticated sealed-memfd IPC to a wgpu Vulkan swapchain. On Weston 15 headless, compositor-side `wp_presentation_feedback.presented` events total 120, client-dispatched events total 119. Eight captured material variants retain byte-level parity after the Weston-declared Y flip.
- Source inspection: `winit 0.30.13` contains no direct use of `wp_presentation` within its Wayland implementation; `wgpu-hal 30.0.1` also contains no direct `wp_presentation` requests. The Vulkan WSI stack handling `vkQueuePresentKHR` is the probable creator of these objects (strong architectural attribution, no call-stack trace proving the exact library function).
- Physical NVIDIA 3070 probe (ash 0.38): `VK_KHR_present_id` supported and feature `presentId=true`; `VK_KHR_present_wait` supported and feature `presentWait=true`.
- A fresh real **wgpu viewer run** with `wgpu_hal::vulkan=debug` lists active device extensions as `VK_KHR_swapchain`, `VK_KHR_swapchain_mutable_format`, `VK_EXT_robustness2`, `VK_KHR_external_memory_fd`, `VK_EXT_external_memory_dma_buf`, `VK_EXT_image_drm_format_modifier`, and `VK_EXT_memory_budget`. **Neither `VK_KHR_present_id` nor `VK_KHR_present_wait` is enabled.**
- In the actual `wgpu-hal 30.0.1` swapchain `NativeSwapchain::present` path, `vk::PresentInfoKHR` is built without a `VkPresentIdKHR` chain. Thus current application frames have no Vulkan `presentId` attributable to the 120 canonical frame seq values.

## Executable truth gates

The isolated Rust `tools/cpja3-vulkan-probe` queries **the live physical device** for extension availability and feature bits via `vkGetPhysicalDeviceFeatures2`. The separate instrumented native Wayland viewer logs **the actual wgpu-hal device extension list** for this process. `scripts/qchain_cpja3_authority_gate.py` reconciles these with an immutable copy of the exact `wgpu-hal` swapchain source. The five negative tests include forged physical identity, missing device-extension evidence, fabricated enabled extensions, and fabricated present-ID source. Even if all textual inputs are forged to look eligible, the gate refuses invocation without typed runtime evidence.

Observed verdict: `CPJA3_TYPED_PRESENT_WAIT_NOT_ENABLED_HOLD`.

Do **not** call `vkWaitForPresentKHR` on this `wgpu` device: the physical GPU supporting an extension does **not** enable it on a logical device, and the existing Vulkan presentation path does not assign IDs.

The runtime debug log is not a signed hardware attestation. The gate only authorizes continued engineering investigation; it cannot promote production based on text logs alone.

## CP-JA4 implementation contract — Vulkan WSI bridge

Implement in a *separate vendored/isolated* fork of the pinned wgpu-hal, **not** by mutating Cargo's global registry or the CPU donor:

1. **Device negotiation** — opt in `VK_KHR_present_id` and `VK_KHR_present_wait` together on supported physical devices, with corresponding `VkPhysicalDevicePresentIdFeaturesKHR` and `VkPhysicalDevicePresentWaitFeaturesKHR` enabled through the actual logical device creation chain. Explicitly refuse absent feature bits. Retain a baseline fallback where present-wait is not claimed.
2. **WSI attribution** — in the `vkQueuePresentKHR` path attach `VkPresentIdKHR` via `pNext`, allocate monotonic IDs scoped to a specific swapchain generation, and associate each returned frame seq/epoch/scene digest with the ID. Surface-loss and swapchain recreation must invalidate old IDs fail-closed.
3. **Typed wait** — expose a bounded wait function owned by the same Vulkan device/swapchain, calling `vkWaitForPresentKHR(swapchain, presentId, timeout)` after successful presentation submission. Handle timeout, device lost and out-of-date explicitly. It is not sufficient to wait on a GPU queue fence or GPU `Device::poll`.
4. **Application lifecycle** — after exactly 120 genuine frames, stop producing and wait for their 120 typed IDs. Exit 0 only on actual 120/120 confirmations. No 121st sentinel. On missing ACK: exit nonzero and retain full evidence.
5. **Independent evidence** — run in private Weston headless. Compare typed ID receipts against Weston `wp_presentation_feedback` trace and pixel captures. Verify adverse delay, missing extension, reordered IDs, destroyed/recreated swapchain, canceled or timed-out waits; preserve CP-F GPU byte oracle and IPC identity gates.

**Acceptance gate:** 120/120 typed present-wait completions in >=3 repeated live runs **and** independent compositor confirmation, no sentinel, no unhandled timeout, no source regression. This still does not prove physical photons or CP03 HYBRID-60 on Hyprland.

## Evidence and limitations

Private evidence: `/mnt/workbench/evidence/runs/qchain-cpja3-20261010-01/`.
- `probes/vulkan-runtime.txt`: NVIDIA physical extension/feature availability.
- `probes/runtime-viewer-01/`: live Vulkan GPU→sealed IPC→Weston run (120 submissions, 8 exact compositor samples), wgpu-hal DEBUG device list, Wayland traces (119 client / 120 server).
- `probes/authority-gate.json`: fail-closed logical-device vs physical-device authority.
- `source-snapshot/`: exact local upstream `wgpu-hal 30.0.1` WSI and device-extension source, with hashes.
- `negative/`: adversarial gate tests.

**Gate CP-JA3:** physical capability PASS; activation, ID attribution, typed wait and clean viewer closure **HOLD**. No merge, push or production deployment. CP-L G06 and CP03 HYBRID-60 remain OPEN.
