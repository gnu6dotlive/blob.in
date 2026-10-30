# CP-JA7D-B — Asynchronous Vulkan Present-Wait and Out-of-Order Delivery Authority

Date: 2026-10-11, Montréal (the UTC tool logs cross into 2026-10-12).
Parent: CP-JA7D commit 58cb27803bf0007743212a13f04061333cc79dde
Branch: feat/qchain-async-out-of-order-20261011

**Scoped verdict:** CP-JA7D-B can qualify independent asynchronous Vulkan present-wait polling, completion *delivery* in a different order from submission, per-generation acknowledgement ownership, and safe cancellation after an injected device-loss result. It does **not** demonstrate that hardware presentations or Vulkan completion times physically occur out of order.

## Architecture and safety boundary

A feature-gated worker is attached to each native Wayland Vulkan swapchain, created as a Rust std::thread and owned by a collector. Each worker owns a retained Arc<DeviceShared> and an ash VK_KHR_present_wait Device wrapper, preventing device destruction before the worker is joined.

The viewer thread continues submitting actual VkPresentIdKHR IDs through vkQueuePresentKHR. Successful returns register IDs through an mpsc command channel. The worker performs repeated actual vkWaitForPresentKHR(handle, present_id, timeout=0) probes with 250 microseconds between passes, recording only VK_SUCCESS as wait success. This is **asynchronous polling**, not blocking the viewer until each presented frame completes, and not a kernel-event-driven collector.

The worker deliberately withholds completed-result delivery until a two-ID batch has independently received two real VkWaitForPresentKHR successes. It then sends the newer validated ID first and the older second through its result channel. A final Flush command permits a one-ID remainder to be processed at teardown. Therefore the *delivery order* can be (2,1),(4,3),... even when physical display order and actual Vulkan wait-success observation order are unchanged.

The PresentLifecycle under gnu6-cpja7db-async-retire supports bounded pending IDs using VecDeque. It now accepts an exact, previously issued but still unacknowledged ID even if it is not the oldest. The acknowledgement method validates the generation and rejects an unknown or duplicate ID by poisoning its authority. The previous CP-JA7D FIFO behavior remains enabled when CP-JA7D-B is not selected.

The HAL checks DeviceShared.cpja7d_device_lost before accepting queued results. If the private Loader returns a synthetic VK_ERROR_DEVICE_LOST during a newer submission, all existing pending IDs across both old swapchains become untrusted, including successes the worker observed but which were not yet accepted by the application. Late results cannot resurrect that logical device; no forged ACK is recorded. Workers are stopped and joined before swapchain destruction. In-process reconstruction creates two fresh workers, swapchains and present-ID generation identities.

A native timeout, collector disconnection or Vulkan wait fault poisons outstanding authority. A timeout is not promoted to success.

## Qualification evidence

Root: /mnt/workbench/evidence/runs/qchain-cpja7db-20261011-01

The production runner scripts/qchain_cpja7db_run.py captures private Weston 15 headless GL screens, separate Vulkan worker/hal logs, Wayland client protocol and compositor server traces, while authenticating the 120 F4 source frames and their canonical SHA-256 payloads.

| Positive run | Source frames | WSI issues | Real wait successes | Trusted ACKs | Deliberately reversed batches | Out-of-order ACKs | Captures |
|---|---:|---:|---:|---:|---:|---:|---:|
| final-normal-01 | 120 | 240 | 240 | 240 | 120 | 120 | 8 |
| final-normal-02 | 120 | 240 | 240 | 240 | 120 | 120 | 8 |
| final-loss-01 | 120 | 240 | 240 | 238 | 120 | 119 | 8 |
| final-loss-02 | 120 | 240 | 240 | 238 | 120 | 119 | 8 |

All runs use two 512 × 384 compositor distinguishable images, in a private Weston 1536 × 1024 compositor, with exact alpha and per-channel RGB difference no greater than 3 after reversing the screenshot Y axis. Canonical F4 source frame hashes and semantic stage receipts are independently checked.

In the loader-fault runs, the first Vulkan swapchain's attempted present ID 41 receives synthetic VK_ERROR_DEVICE_LOST returned by the private CP-JA7C-B explicit Vulkan loader layer. The call is not forwarded to the NVIDIA ICD. The old secondary swapchain's IDs 39 and 40 remain **unacknowledged** on the invalidated logical device, even if the worker obtained real VK_SUCCESS from the still functional physical ICD before the application revoked the generation. All 80 new IDs in generations 3 and 4 are fully acknowledged and both reconstructed Wayland surfaces become visible.

Per positive run there are 240 compositor server-side presented feedbacks and zero discarded. The oracle separately compares the client-received feedback multiset with the Weston server trace; a bounded difference on destroyed old surfaces is recorded but never substituted for Vulkan typed ACKs.

## Test and falsification protocol

scripts/qchain_cpja7db_gate.py performs production admission; scripts/qchain_cpja7db_independent_oracle.py plus scripts/qchain_cpja7db_oracle_tail.py separately recompute authenticated frame identity, exact Vulkan ID sets, worker wait results, reverse delivery order, non-FIFO ACK acceptance, device-loss revocation, compositor resource identity, pixel fidelity, and Wayland client/server reconciliation. The independent oracle does not import or trust the runner gate or its stored verdict.

The test scripts/test_qchain_cpja7db_oracle.py mutates isolated temporary copies of reference evidence. Twenty-five out of twenty-five altered proofs are rejected, including false ACK for failed ID 41, ghost wait success, duplication of issue or completion, missing actual wait result, loss of secondary device-wide cancellation, false generation assignment, spoofed Vulkan Loader negotiation, forged Wayland feedback, corrupted GPU hashes, altered pixels and aliasing both surfaces.

Three live negative runs reuse the previously sealed CP-JA7C-B isolated fault harness, but load the new CP-JA7D-B viewer binary: no recovery authorization (40 source frames then nonzero exit), two synthetic losses (44 then nonzero), and a false recovery requirement with no injected fault (120 normally processed frames but no unearned success receipt). None may generate a positive receipt.

Direct Rust ledger tests: 10 feature-on, 8 CP-JA7D FIFO feature-only, 6 CP-JA6 legacy. blob-frame tests: 31. Clean offline cargo clippy with -Dwarnings for the new feature, and successful checks of the older CP-JA7D and CP-JA5 feature paths.

## Limits and handoff

| Gate | Result |
|---|---|
| Two simultaneous unacknowledged WSI presentations per swapchain | PASS |
| Two independent actual Vulkan timeout-zero completion polling workers | PASS |
| Two distinct real VkWaitForPresentKHR success results before reversal | PASS |
| Out-of-order *delivery and validated acknowledgement* | PASS |
| Verified generation-aware poisoning on duplicate, unknown or stale IDs | PASS |
| All old device completions revoked and workers joined before teardown | PASS |
| Fresh device and dual Wayland surface reconstruction after injected loss | PASS |
| Four independent 120-frame E2Es and private Weston screenshots | PASS |
| Three live fail-closed controls, 25 adversarial oracle rejections | PASS |
| Rust regressions, cargo checks and Clippy -Dwarnings | PASS |
| Actual VkWait success observed out of temporal order without buffering | NOT CLAIMED |
| Actual GPU scan-out or present order reversed | NOT CLAIMED |
| True NVIDIA driver-emitted device loss or physical GPU reset | NOT TESTED |
| Low overhead, CPU efficiency, sustained 60 FPS or HYBRID-60 | NOT TESTED |
| Zero-copy, physical photons, AMD/Intel and multi-compositor coverage | NOT TESTED |

This collector is a scoped experimental backend, not production-promotion authority. It polls at a short interval and has not been performance- or power-budget qualified. No merge, push, deployment, user compositor restart, GPU reset or global Vulkan-layer installation.

Recommended next: **CP-JA7E — asynchronous retirement scheduling/overhead/pressure qualification**, including bounded scheduler CPU cost, configurable polling cadence, idle behavior, stress under swapchain recreation and device loss, followed by a separate CP03 HYBRID-60 performance gate.
