# CP-JA7E — Adaptive asynchronous WSI scheduler: scoped correctness and initial cost

Parent: CP-JA7D-B commit `95fc63f11061c6c166408c0c3d0f8117d95e53fe`.
Branch: `feat/qchain-adaptive-async-scheduler-20261011`.
Baseline: NVIDIA RTX 3070 with private Weston 15 headless GL, two 512×384 Wayland swapchains.
Decision: **SCOPED PASS** only for scheduler safety, bounded polling, idle blocking, and six end-to-end runs. **Performance qualification remains OPEN.**

## Change and invariants

The feature `cpja7e-adaptive-scheduler` implies CP-JA7D-B asynchronous retirement. It does not replace the pre-existing build choices unless enabled.

Before CP-JA7E the workers woke every 250 microseconds even without two queued presentations. In CP-JA7E a worker with fewer than two items and no flush waits in blocking `mpsc::recv()`, waking only upon a command or channel closure. When it has an actionable batch it probes real `vkWaitForPresentKHR` results (timeout=0), and sleeps through `recv_timeout()` using the selected bounded cadence: `latency` 250 microseconds, `balanced` 1000 microseconds, `eco` 4000 microseconds. Invalid profiles fall back to `balanced`; the `balanced` profile is also the implicit default.

All actual `VK_SUCCESS` observations still precede the two-result deliberately reordered deliveries; no delay, timeout, or feedback is converted into a Vulkan acknowledgement. Outstanding authority remains capped at two per swapchain and remains poisoned across the logical device after a failed present; workers are joined before swapchain destruction. An opt-in bounded `CPJA7E_IDLE_PROBE_MS` is used solely to insert a startup idle period inside the isolated viewer for repeatable idle observation.

CP-JA7E instruments each worker's `wait_calls`, `timeouts`, `polls`, `idle_wakes`, blocking idle time, timed active waits, successful Vulkan completions, delivered results, elapsed wall time, and Linux `RUSAGE_THREAD` CPU consumption; each metric is printed at worker exit. `RUSAGE_THREAD` measures only the individual worker thread, not the entire application or energy demand.

## First observed profile comparison

All three no-fault runs validated 120 canonical GPU frames, 240 genuine Vulkan wait successes, 240 typed ACKs (120 deliberately out-of-order), 240 Weston presentation feedbacks and eight qualifying compositor screenshots:

| Profile | Poll cadence | vkWaitForPresentKHR calls, both workers | Worker CPU time total | Result |
|---|---:|---:|---:|---|
| latency | 250 µs | 5,677 | 96.8 ms | PASS |
| balanced | 1,000 µs | 2,020 | 64.1 ms | PASS |
| eco | 4,000 µs | 793 | 52.8 ms | PASS |

Thus `eco` recorded approximately 86% fewer WSI polls and 45% less cumulative thread CPU than `latency` **in these individual exploratory observations**. These figures are not statistically representative of independent loads, FPS, wall-time performance, total system CPU, or power consumption. No production default is approved by this comparison.

All three fault/recovery runs were also PASS, each replaying 120 canonical frames with two new swapchains after a synthetic Vulkan-loader `VK_ERROR_DEVICE_LOST` at the first primary present ID 41. Each returned 238 trusted ACKs, intentionally preserved two unacknowledged old-secondary IDs, and observed 119 out-of-order acknowledgements and eight compositor screenshots. There are four worker metric receipts due to one device rebuild. No real driver-originated loss or GPU reset was performed.

An opt-in 400 ms viewer startup idle probe was executed for all six runs. Corresponding worker counters show command-wait blocking rather than a tight empty poll loop, but the counters do not constitute a calibrated idle-power test.

## Verification and independent attribution

Evidence: `/mnt/workbench/evidence/runs/qchain-cpja7e-20261011-01`.
The six scoped positive runs are `latency`, `balanced`, `eco`, `latency-loss`, `balanced-loss`, `eco-loss`. Each run has an unchanged E2E producer receipt and a separate CP-JA7D-B independent oracle verdict examining Vulkan ID ownership, pixel hashes and Wayland client/server traces.

The separate metrics table `bench/metrics-initial.json` reconciles the worker exit receipts against the expected profile and frame counts.

Three live fail-closed tests use the CP-JA7E binary: no recovery authorization (40 submitted, nonzero viewer exit), intentional second loss (44 submitted, nonzero), and a demanded recovery epoch with no injection (120 frames processed but no false qualification success).

Clippy `-Dwarnings` and `blob-frame` 31 tests passed on the new Cargo feature. Earlier CP-JA7D-B oracle adversaries and regression tests remain reference evidence; this qualification does not claim a new independent adversarial campaign or statistical benchmarking.

## Boundaries and next step

PASS: three bounded profiles; blocking when idle; verified real Vulkan success before ACK; dual-swapchain positive presentation; recovery with device-wide invalidation; separate worker counters; six independent visual/oracle E2Es; three fail-closed controls; Clippy and crate regression.

OPEN: repeated randomized benchmark with controlled external load, wall-time latency percentiles, scheduler-context-switch overhead, thermal and power instrumentation, longest continuous stress, swapchain churn under pressure, actual driver-emitted device loss, 60 FPS, CP03 HYBRID-60, zero-copy, AMD/Intel, second compositor.

**Do not promote this experimental worker policy to production yet.** Prefer a further CP-JA7E-B controlled workload characterization with repeated randomized interleaved trials and an explicit CPU/p95/idle acceptance envelope. No merge, push, deployment, compositor restart or GPU reset authorized.
