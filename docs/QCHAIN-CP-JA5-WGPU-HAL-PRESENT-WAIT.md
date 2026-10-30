# CP-JA5 — Vendored wgpu-hal 30.0.1 Vulkan Present-Wait

**Date:** 2026-10-10. **Parent:** CP-JA4 `6b1a454ef68f0faab03af4d745aca679f3ea416f`.
**Branch:** `feat/qchain-wgpu-hal-present-wait-20261010`.
**Authority:** private local, same physical RTX 3070, Weston 15 headless.
No merge, push, runtime deployment, production promotion, or public FPS claim.

## Implementation

CP-JA4 proved `VkPresentIdKHR + vkWaitForPresentKHR` on a separate
native Ash presenter. CP-JA5 qualifies the equivalent path in the
**real wgpu 30.0.1 renderer**, while preserving the Ash reference.

A pinned `wgpu-hal 30.0.1` fork is vendored in
`vendor/wgpu-hal-30.0.1`, resolved **only in this Git worktree**
with `[patch.crates-io]`. The original global Cargo registry cache
was not edited. Upstream licensing remains MIT OR Apache-2.0;
retain original copyright, README and LICENSE notices and identify
the local modifications separately.

The showcase has a strictly opt-in Cargo feature:
`--features cpja5-present-wait`. Its transitive dependency enables
`wgpu-hal/gnu6-cpja5-present-wait`.

Within the fork:
- `vulkan/adapter.rs`: verifies physical extension availability and
  `VkPhysicalDevicePresentIdFeaturesKHR` /
  `VkPhysicalDevicePresentWaitFeaturesKHR` bits; enables both extensions
  on the actual logical device and appends both feature structures to
  the `VkDeviceCreateInfo` pNext chain. Missing capability refuses
  device creation, not silent fallback.
- `vulkan/swapchain/native.rs`: allocates a monotonic ID per swapchain
  generation, chains `VkPresentIdKHR` into `vkQueuePresentKHR`, and
  waits for the same swapchain/ID using `vkWaitForPresentKHR` with a
  5-second bound. Logs a typed success only after the Vulkan wait returns
  `VK_SUCCESS`. Timeout, surface loss, out-of-date and other driver
  errors return errors; no invented acknowledgment.
- The new `qchain_cpja5_wgpu_viewer` is a normal wgpu Wayland renderer,
  not the Ash presenter. Its deterministic frame hashes, sealed memfd
  handoff, source identity and 512×384 pixel oracle remain unchanged.

## Experiment and evidence

Three fresh full GPU→sealed IPC→**wgpu-hal**→Wayland executions
demonstrated, per run:
- 120 real GPU-generated F2/F3/F4 frames;
- 120 wgpu frame submissions, 120 monotonically ordered `presentId`
  typed `VK_SUCCESS` waits in the HAL fork;
- 120 `wp_presentation_feedback.presented` events in the client and
  120 matched server Weston events;
- eight independently captured Weston images, byte-exact after its
  declared Y-flip, with no masking or color tolerance.

The independent oracle `scripts/qchain_cpja5_independent_oracle.py`
re-runs the CP-I02 GPU SHA/capture oracle and checks the typed HAL
receipts against frame sequence, client/server Wayland event count
and exact compositor pixels. Six adversarial cases pass (one positive
and five tampered evidence negatives), including terminal ACK removal,
duplicated IDs, disabled-extension fiction, missing server event and
modified compositor pixel. The tests never mutate the source evidence.

**Bounded verdict:**
`QCHAIN_CPJA5_WGPU_HAL_TYPED_120_OF_120_WESTON_EXACT_PASS`.
Three development runs succeeded. After commit `2c4983502c17890f57a95c7a7f83e17eea041369`, a clean Git archive was rebuilt **offline**, and another three complete runs from that archived binary independently passed: 360/360 typed Vulkan waits, 360/360 client and server Wayland feedback events, and 24/24 exact captures (4,718,592 pixels). The archived build also failed closed with the Vulkan ICD deliberately unavailable.

The feature-OFF control compiles the same vendored crate without the
extra code and continues to display eight exact samples; it emits no
`CPJA5_HAL_TYPED_PRESENT_ACK`. This observed baseline finished with
119 client/119 server feedback entries, not the typed 120/120 guarantee.
With Vulkan ICD deliberately unavailable, source and viewer fail
without a PASS receipt.

## Limitations and engineering safeguards

These `wgpu-hal` changes are **not upstream**. The pinned fork is scoped
to one worktree and feature, and has not been qualified on AMD, Intel,
other window systems, physical displays, swapchain recreation or
multi-window use. The monotonic ID starts at 1 for each new swapchain
and is stored on that swapchain; the current experiment uses one
window, one swapchain and one GPU device. An out-of-date/lost
swapchain currently refuses to continue and requires a new generation
and fresh qualification. IDs are never reused in one generation.

Typed Vulkan WSI success confirms the presentation operation through
the driver and is cross-checked with Weston compositor events, but
not physical photons. The existing GPU→CPU readback, memfd transfer,
and host→GPU upload remain: **not zero-copy**. A synchronous, bounded
wait in the HAL `present()` path intentionally serializes observation,
but may reduce throughput on another compositor. No CP03 HYBRID-60,
frame-pacing p99, VRR or hardware display 60 FPS claim is authorized.

Driver-injected `VK_TIMEOUT`, device-loss under load, swapchain
recreation with old IDs, presentation out-of-order and multi-vendor
are not independently exercised yet. These remain follow-up gates;
synthetic text edits in an oracle are not substitutes for injecting
real Vulkan faults. Real-world deployment would require API design
to avoid blocking a general-purpose wgpu presentation thread.

## Follow-up — CP-JA6

Qualify robust typed generation scopes, driver-level timeouts,
out-of-date/recreated swapchains, and multiple in-flight frames.
Then CP-JB can measure presentation cadence and queue pressure
without conflating Vulkan completion with display photons.

Private receipts:
`/mnt/workbench/evidence/runs/qchain-cpja5-20261010-01/`.
