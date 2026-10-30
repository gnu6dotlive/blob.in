# CP-JA7D — Two Vulkan Presentations In Flight & Device-Wide Loss Recovery

Date: 2026-10-11 (late evening, Montréal)
Parent: CP-JA7C-B commit 1a586ef77f3ab69755c79adeacf4187910854892
Branch: feat/qchain-multi-inflight-present-20261011

**Qualification: SCOPED PASS — two outstanding Vulkan WSI presentations per swapchain with typed FIFO retirement, bounded drain, and device-wide invalidation during loader-injected loss.**

## Boundary of the claim

A Vulkan presentation is in flight here only after vkQueuePresentKHR has returned without error and before vkWaitForPresentKHR has yielded typed success for that presentation ID. This is host-side WSI completion authority, not proof of simultaneous GPU rendering, parallel CPU present calls, independent hardware scan-out, physical photons, or 60 FPS.

The implementation maintains **up to two pending IDs on each of the two native Wayland swapchains** of one logical Vulkan device. New WSI submissions do not immediately wait for their own present ID. Before issuing a third ID on one swapchain, the implementation waits up to five seconds for the oldest outstanding ID, verifies its typed success, and frees one slot. At bounded teardown, it waits explicitly for the remaining two IDs. All acknowledged IDs remain strictly monotonic per generation.

**Not qualified:** real hardware acknowledgements arriving or being processed out of order. CP-JA7D deliberately enforces FIFO retirement; its oracle rejects reordered ACK evidence. That must not be represented as out-of-order delivery support.

## Native HAL changes

The opt-in feature cpja7d-multi-inflight in crates/showcase/Cargo.toml enables gnu6-cpja7d-multi-inflight in vendored wgpu-hal-30.0.1 and the original cpja5-present-wait capability. With the new flag disabled, CP-JA6 still compiles its original single-outstanding lifecycle.

The vendored file vulkan/swapchain/cpja6_lifecycle.rs replaces outstanding Option<u64> with a VecDeque<u64> only under this feature. The two-entry cap, oldest() and pending(), monotonic issue, FIFO acknowledgement, no-ID-reuse and poison-on-invariant-failure are separately tested.

The native WSI path in vulkan/swapchain/native.rs implements three transitions:

1. CPJA7D_TYPED_RETIRE — vkWaitForPresentKHR succeeds for the oldest pending ID before a new issue would exceed the depth-two cap.
2. CPJA7D_INFLIGHT_ISSUED — VkPresentIdKHR was accepted by vkQueuePresentKHR, pending depth 1 or 2. This event is **not an ACK**.
3. CPJA7D_DRAIN_TYPED_ACK — successful bounded wait during release_resources, never a synthetic success on teardown.

Failed native present emits CPJA7D_LOSS_INVALIDATES_UNACKED and poisons its own ledger. The feature-gated DeviceShared AtomicBool cpja7d_device_lost also marks the **entire logical device** lost. Both swapchains check that flag before later submissions and before final drain. A drain on a lost logical device is refused with CPJA7D_DEVICE_WIDE_DRAIN_DENIED; pending IDs are invalidated rather than credited as successes.

This device-wide fence is critical because the private layer returns a synthetic Vulkan device-loss result even while the physical NVIDIA ICD keeps operating normally. Without this fence, the old secondary swapchain could produce late success values on an already invalidated logical device.

## Four qualified positive E2E executions

Evidence root: /mnt/workbench/evidence/runs/qchain-cpja7d-20261011-01

| Run | Fault | WSI issues | Valid typed ACK | Unacknowledged IDs | Weston presented | Captures |
|---|---|---:|---:|---|---:|---:|
| two-inflight-01 | None | 240 | 240 (236 retire + 4 drain) | None | 240 | 8 |
| two-inflight-02 | None | 240 | 240 (236 + 4) | None | 240 | 8 |
| loader-loss-inflight-02 | Synthetic loader loss | 240 | 237 (233 + 4) | g1:40, g2:39, g2:40 | 240 | 8 |
| loader-loss-inflight-03 | Synthetic loader loss | 240 | 237 (233 + 4) | g1:40, g2:39, g2:40 | 240 | 8 |

Each run authenticates 120 distinct source-frame sequences, preserving GPU source hashes and scene semantics, and visually presents canonical F4 frames on two compositor-distinguishable 512 × 384 surfaces within a private Weston 15 headless GL compositor (RTX 3070). The eight 1536 × 1024 screenshots per run satisfy per-channel RGB difference at most 3 and exact alpha after Y-flip. Neither screen fidelity nor frame hashes imply zero-copy.

On normal runs, both swapchains issue IDs 1 through 120, retire 1 through 118 once the two-entry queue fills, then drain 119 and 120. All 240 Vulkan typed acknowledgements are accounted for.

With an injected loss at primary present ID 41, previously issued primary ID 40 is unresolved. Secondary pending IDs 39 and 40 are invalidated by the device-global authority. The failed primary ID 41 is **attempted, not successfully issued and never ACKed**. Old-device ACKs total 39 primary + 38 secondary; new generations 3 and 4 each issue and ACK IDs 1–80. Overall: 240 issued, 237 typed successes, 3 deliberately unacknowledged. The viewer still completes all 120 distinct source frames following in-process device and swapchain reconstruction.

The Weston server records 240 presented events and zero discarded per run. Clients observe all 240 on normal runs but 238 per fault/recovery run. Two server-confirmed feedbacks are no longer delivered to the old client surfaces during their destruction. The oracle permits at most two such missing events, verifies each client event exists on the server, and **never substitutes server feedback for typed Vulkan acknowledgement**. In particular, it does not rehabilitate any of the three poisoned Vulkan IDs.

The early exploratory runs inflight-baseline-01 and loader-recovery-inflight-01 remain archived HOLD/diagnostic and are not counted. The former was judged with the previous synchronous-ACK oracle; the latter exposed incomplete device-wide poisoning and drove the AtomicBool correction.

## Failure source and independent falsification

Only the private viewer subprocess receives the CP-JA7C-B explicit Vulkan layer and the loader fault selector primary-id-41. The layer returns VK_ERROR_DEVICE_LOST from the real Vulkan-loader vkQueuePresentKHR dispatch without forwarding that particular failed call to the NVIDIA ICD. The resident Hyprland compositor and source broker are not configured with the layer.

The production runner qchain_cpja7d_run.py collects compositor PNGs, Vulkan typed WSI transitions, Wayland client protocol and private Weston server traces. qchain_cpja7d_gate.py gates the claimed result. Independently, qchain_cpja7d_independent_oracle.py and qchain_cpja7d_audit_tail.py reread original pixels and logs and recompute canonical source hashes, issue/retire/drain traces, device-loss ordering, surface generations and presentation feedback without accepting producer verdicts.

The independent test test_qchain_cpja7d_oracle.py creates temporary altered copies and rejects **19/19** falsifications: missing loader fault/callback, omitted device-wide secondary invalidation, forged old-device ACK, forged ACK for failed present, lost final drain, duplicate issues, depth overflow, reordered ACKs, missing recovery completion, duplicated source sequence, altered canonical source digest, corrupted compositor pixels, aliased secondary window, missing server feedback, missing loader negotiation, forged HAL-side injection, forged client feedback, and normal-run missing final drain.

Three live negative trials use the CP-JA7C-B fault harness but load this CP-JA7D binary. All exit nonzero with no success receipt: (a) no recovery allowed — stop after 40 frames; (b) a second injected loss after one rebuild — stop after 44; (c) a requested recovery epoch without any fault — submit 120 normal frames but deny an unearned recovery claim.

## Verification matrix

| Gate | Verdict |
|---|---|
| Two WSI presentations outstanding on each swapchain | PASS |
| Real vkWaitForPresentKHR typed success before each retired/drained ACK | PASS |
| Depth-two backpressure and bounded FIFO retirement | PASS |
| Device-wide secondary ID invalidation on loss | PASS |
| Three old-device IDs never falsely acknowledged after loss | PASS |
| Rebuild one device and both swapchains in same process | PASS |
| Four private E2Es, source/pixel/Wayland/Vulkan independent oracle | PASS |
| 19 falsifications rejected and three live fail-closed tests | PASS |
| 8 feature-on lifecycle tests, 6 feature-off CP-JA6 regressions | PASS |
| 31 blob-frame unit tests, Clippy -Dwarnings and legacy feature check | PASS |
| Out-of-order completion acceptance | OPEN — FIFO by design |
| Concurrent CPU calls into WSI / asynchronous completion collectors | NOT TESTED |
| Real physical GPU reset or driver-reported device loss | NOT TESTED |
| CP03 HYBRID-60, sustained 60 FPS, zero-copy, photons | NOT TESTED |
| Cross-vendor AMD/Intel or second compositor/OS | NOT TESTED |

No global Vulkan layer installation, host GPU reset, resident Hyprland mutation, live-service restart, merge, push or production deployment occurs in this scope.

**Next:** CP-JA7D-B should qualify out-of-order completion ownership and a nonblocking/event-driven completion collector with per-generation cancellation and independently verified feedback reconciliation. CP03 HYBRID-60 remains an independent gate.
