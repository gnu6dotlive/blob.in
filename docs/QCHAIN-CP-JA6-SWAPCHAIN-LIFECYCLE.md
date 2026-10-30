# CP-JA6 — Vulkan Swapchain Lifecycle and Failure Authority

Date: 2026-10-10. Parent CP-JA5 `10add0e48446c2ff47dd59ad9025c3474b3c445e`.
Branch: `feat/qchain-wgpu-hal-lifecycle-20261010`.
Scope: opt-in **vendored** `wgpu-hal 30.0.1` on RTX 3070 / isolated Weston 15 headless. Not production.

## Engineering change

CP-JA5 exposed a precise failure-state risk: on a successful
`vkQueuePresentKHR` followed by `vkWaitForPresentKHR(VK_TIMEOUT)`,
the original implementation advanced `presentId` **only on successful
wait**. It could therefore reuse an ID that Vulkan had already
accepted, if presentation was attempted again on the same swapchain.

CP-JA6 replaces `cpja5_next_present_id` with
`PresentLifecycle` in
`vendor/wgpu-hal-30.0.1/src/vulkan/swapchain/cpja6_lifecycle.rs`.
Its invariants are: reserve the monotonic ID **before** queue
presentation; one outstanding ID; acknowledge only the exact pending
ID; poison the generation on an uncertain or failed queue/present/wait;
fail closed on mismatched ACK and checked ID exhaustion. A new
`NativeSwapchain` receives an independent process-unique generation
token and restarts its own Vulkan present ID sequence at 1.

This state machine is executed directly from the real vendored
`NativeSwapchain::present()`, not only by the offline oracle.
All waiting still calls the Vulkan driver, 5 s bounded normally,
and maps real timeout/surface/device errors to failures. The
feature-disabled upstream behavior remains outside this code path.

## Positive: real swapchain reconfiguration

A separate `qchain_cpja6_reconfigure_viewer` is a wgpu
Wayland viewer using the same sealed-memfd, SHA-bound F2/F3/F4
GPU compute stream as CP-JA5. After genuine source frame seq=59
has been submitted and typographically acknowledged, it calls
`surface.configure(&device,&config)` on the live compositor
surface. This invokes destruction/recreation of the underlying Vulkan
swapchain. The remaining 60 frames are presented on the new
generation with fresh Vulkan IDs.

Three real engine+IPC+patched wgpu+Weston runs succeeded:
- 120/120 freshly computed source frames and exact SHA-bound receipts
  in each run;
- generation 1: 60 Vulkan wait-success IDs 1..60;
- generation 2: 60 Vulkan wait-success IDs 1..60; generation identity
  differs and strictly advances from the earlier generation;
- 120/120 Wayland `presented` messages both on client and Weston;
- eight exact 512×384 Weston compositor captures per run.

The independent oracle
`scripts/qchain_cpja6_independent_oracle.py` checks source-frame
oracle parity, actual reconfiguration witness, all 120 scoped typed
acknowledgments, source order, and both server/client Wayland traces.
Six adversarial tests verify missing terminal ACK, old-generation
replay, duplicated ID in the new generation, missing reconfigure
witness and dropped server feedback. Fixtures never write into the
canonical run files.

The pure Rust state machine has six tests compiled via `rustc --test`
directly from the actual vendored source. This isolates it from
Cargo's unavailable offline optional macOS dependency
`mach-dxcompiler-rs`; the full patched application *does* compile
under the pinned workspace lock.

## Negative: real driver timeout (zero-nanosecond wait)

An additional test-only Cargo feature,
`cpja6-zero-timeout-test`, enables vendored
`gnu6-cpja6-zero-timeout-test`. This makes **a real call to the
driver's** `vkWaitForPresentKHR(swapchain,presentId,0)`,
rather than synthetically returning an error.

On the physical RTX 3070, Weston headless, the first present returned
actual `VK_TIMEOUT` at generation=1, ID=1. The HAL logged the
timeout, poisoned that generation and the viewer exited nonzero.
The existing E2E runner emitted no complete-run PASS receipt, and
no typed ACK was emitted. This proves timeout handling on a real
driver under zero deadline; it does **not** prove recovery from a
stalled driver or a naturally occurring 5-second timeout.

Never enable the zero-timeout feature in production.
Build it into a separately isolated Cargo target only.

## Still open

- Device loss under sustained load, hot-plug/unplug and compositor
  disconnect/recovery; no physically injected `VK_ERROR_DEVICE_LOST`.
- Two concurrently active windows/swapchains. Independent generation
  counter helps, but concurrency has not been integration tested.
- Multiple outstanding Vulkan presents. The current correctness path
  intentionally remains **one in-flight present** and waits before
  proceeding, so no 60 FPS or VRR qualification.
- Physical display photons, independent second host, AMD/Intel,
  second compositor, full CP03 HYBRID-60 and CP-L G06.

No merge, push or deployment. Pinned vendor licenses preserved.
Private evidence:
`/mnt/workbench/evidence/runs/qchain-cpja6-20261010-01/`.
Next CP-JA7 should address controlled multi-swapchain and device-loss
recovery; CP-JB addresses bounded latency/pacing before performance claims.
