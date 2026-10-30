# CP-JA4 — Native Vulkan WSI Present-Wait Bridge

**Date:** 2026-10-10. **Parent:** CP-JA3 `0d04c49820dd450c119fccc4947776c315a7a237`.
**Branch:** `feat/qchain-vulkan-wsi-present-wait-20261010`.
**Scope:** isolated experimental Ash Vulkan viewer on NVIDIA RTX 3070; private Weston 15 headless.

## Goal and implemented boundary

The pinned `wgpu-hal 30.0.1` does not enable `VK_KHR_present_id` or
`VK_KHR_present_wait` on its logical device and does not attach
`VkPresentIdKHR` to queue presentations. Instead of forging an ACK
or mutating the global Cargo registry, CP-JA4 creates a **separate,
native Ash Vulkan WSI presenter**. It uses the same canonical CP-F GPU
compute stream, CPU semantic receipt, exact SHA-validated sealed-memfd
SEQPACKET protocol and the private Weston compositor.

This **does not modify** wgpu-hal and **is not a production promotion**.

Implementation: `crates/showcase/src/bin/qchain_cpja4_vk_present_wait.rs`.

- Creates a Wayland native Vulkan surface directly using
  `VK_KHR_wayland_surface`, with winit's window handles; no unavailable
  ash-window package required.
- Selects the physical NVIDIA GeForce RTX 3070, checks physical support
  of both extensions and both feature bits, and creates the logical
  device with `VK_KHR_swapchain`, `VK_KHR_present_id`, `VK_KHR_present_wait`
  plus `VkPhysicalDevicePresentIdFeaturesKHR` and
  `VkPhysicalDevicePresentWaitFeaturesKHR` enabled.
- Creates one FIFO swapchain and host-visible coherent staging buffer.
  The canonical CPU-delivered RGBA frame was **originally computed by
  the real persistent Vulkan F2/F3/F4 GPU engine**. The presenter uploads
  those bytes via `vkCmdCopyBufferToImage` to a swapchain image.
- Associates exactly `presentId = frame.seq + 1` for seq 0..119,
  chains `VkPresentIdKHR` into `vkQueuePresentKHR`, and calls typed
  `vkWaitForPresentKHR` with a **5-second bound** for that same swapchain
  and ID. On Vulkan failure, timeout, surface loss, suboptimal presentation
  or malformed source, the client exits nonzero; no silent CPU fallback.
- Waits for one typed ACK before accepting the next frame, intentionally
  limiting concurrency to one. Zero sentinel frames.


## Evidence — three complete physical-device experiments

| Gate | Run 01 | Run 02 | Run 03 |
|---|---:|---:|---:|
| Fresh GPU compute, frames | 120/120 | 120/120 | 120/120 |
| Sealed IPC, canonical hashes | 120/120 | 120/120 | 120/120 |
| Vulkan present IDs | 1..120 | 1..120 | 1..120 |
| Typed `vkWaitForPresentKHR` success | **120/120** | **120/120** | **120/120** |
| Wayland server `presented` | **120/120** | **120/120** | **120/120** |
| Wayland client `presented` | **120/120** | **120/120** | **120/120** |
| Weston compositor PNGs | 8 exact | 8 exact | 8 exact |
| Terminal sentinel | 0 | 0 | 0 |

Across the three campaigns: **360 typed Vulkan success acknowledgments,
360 compositor-side events, 360 client-received events, 24 captured PNGs,
4,718,592 exact comparison pixels and zero pixel mismatch** after the
Weston-declared vertical flip. All 120 IDs in each run are unique, ordered,
and tied to source frame sequence and semantic scene SHA.

The independent oracle,
`scripts/qchain_cpja4_independent_oracle.py`, revalidates the previous
CP-I02 byte/pixel oracle and cross-checks all 120 per-frame typed
acknowledgment records, real source GPU frame hashes, Wayland server and
client protocol event streams and fixed CPU scene identities.

Six adversarial cases (one positive and five negative) PASS:
missing final typed ACK, duplicated present ID, falsified wait success,
missing Weston presentation and center-pixel corruption. Fixtures use
unlink-before-write; canonical evidence and sources remain immutable.

**Constrained verdict:**
`CPJA4_VULKAN_PRESENT_WAIT_120_OF_120_EXACT_PASS`.

## Still NOT proven

- No integration into `wgpu-hal 30.0.1` or the original wgpu renderer.
  The new native Ash presenter is the qualified experimental implementation.
- FIFO + a blocking per-frame `vkWaitForPresentKHR` plus an application
  pacing pause provide correctness, **not a 60 FPS performance gate**.
- Weston headless compositor feedback is not independent physical
  display-photon evidence. RTX 3070/NVIDIA only; AMD/Intel NOT_RUN.
- GPU↔CPU readback, sealed memfd and host↔GPU upload remain.
  No zero-copy, GPU hardware timestamps, driver-level function trace,
  suspend/resume or hot swapchain recreation qualification.
- The five-second timeout code exists but negative timeout/device-lost
  injection still requires a separate controlled campaign.
- No CP03 HYBRID-60, full CP-L G06, merge, push or deployment.

## Private evidence

`/mnt/workbench/evidence/runs/qchain-cpja4-20261010-01/`

- `runs/ash-native-01`, `ash-native-02`, `ash-native-03`: compute/source/viewer/Weston
  logs, 8 PNGs and CP-I02 source timeline per run.
- `oracle/ash-native-01.json`.. `ash-native-03.json`: independent typed ID,
  semantic, compositor and screenshot witness.
- `negative/adversarial.log`: isolated fault injections.
- `preflight/`: offline build, Clippy, Rust tests and archived rebuild.
- `qualification.json`: scoped final receipt with hashes.

**Next CP-JA5:** integrate `VkPresentIdKHR`/typed waits behind a
bounded capability into an isolated `wgpu-hal` fork, while preserving the
direct-Ash CP-JA4 oracle as the independent comparator. CP-JB should assess
latency, frame overlap and 60 Hz via compositor/hardware timestamps before
any performance claim.
