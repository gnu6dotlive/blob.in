# CP-JA7E-B — Statistical scheduler qualification, baseline-bound

Date: 2026-10-12.
Parent: CP-JA7E `05d72e501910d82e4c5b1eb4a0e4bb7e9d356808`.
Evidence: `/mnt/workbench/evidence/runs/qchain-cpja7eb-20261012-01`.
Decision: **SCOPED PASS for the preregistered experimental workload, NOT production scheduler promotion.**

## Preregistration and attribution

The complete pre-run contract is `docs/QCHAIN-CP-JA7E-B-STATISTICAL-CONTRACT-20261012.md`, preserved by SHA-256 in `bench/plan.json`. Fifteen *no-fault* 120-frame runs were executed as five balanced rounds, with profile order randomized using fixed seed `20261012`. The immutable plan also hashes the exact compiled viewer. There were **no invisible retries**, no dropped results, and no changes to preregistered latency thresholds after measurement.

Every positive run used the same workstation RTX 3070 and a separately launched private Weston 15 headless GL compositor with two native 512×384 swapchains. The CP-JA7D-B independent oracle independently rechecked canonical source frame digests, both compositor-visible surfaces, screenshot RGBA fidelity, Vulkan wait and ACK ownership, old-generation invalidation, and server/client Wayland feedback. Each run yielded eight qualifying screenshots.

The build adds the opt-in `cpja7eb-benchmark` feature, preserving CP-JA7E compatibility when absent. The worker now reports its own Linux `/proc/thread-self/status` **voluntary and involuntary context switch counts**, complementing CP-JA7E's existing `getrusage(RUSAGE_THREAD)` CPU time. These are per-thread counters, not global system-level demand. The original idle blocking and finite polling policy remain unchanged.

## Fifteen randomized regular-load runs

The following are **medians over five 120-frame trials per profile**, not isolated cherry-picked points:

| Profile | Cadence | Vulkan polls | Worker CPU sum | Voluntary context switches | Source received-to-submit p95 |
|---|---:|---:|---:|---:|---:|
| latency | 250 µs | 5,573 | 93.697 ms | 11,335 | 50.407 ms |
| balanced | 1,000 µs | 2,061 | 65.342 ms | 4,214 | 50.458 ms |
| eco | 4,000 µs | 787 | 51.766 ms | 1,520 | 50.284 ms |

All 15 producer receipts passed, independently confirmed with **15/15 independent oracles**. Each run produced exactly 120 canonical frames, 240 Vulkan present ID issues, 240 genuine Vulkan wait successes, 240 typed ACKs, 120 deliberate out-of-order accepted ACKs, 240 Weston `presented` feedbacks and eight compositor captures.

The preregistered warm-frame (source frames 5–119) p95 ≤100 ms and p99 ≤200 ms gates passed in every trial. The worker sum under `eco` had 0.5525× the median CPU use of `latency`, with 0.1412× median Vulkan wait calls, while its median p95 was 0.9976× the latency profile. Thus the three preregistered cost-comparison thresholds were met, **for this F4 workload on this host only**.

The five per-round paired eco-minus-latency worker CPU differences in microseconds are `[-36724, -39438, -48323, -43160, -44891]` (observed mean −42,507 µs). A 3,000-resample deterministic *exploratory* paired bootstrap of these five differences returned the sampled mean 5th–95th percentile interval `[-45,513, -39,443]` µs. Because only five rounds on one host are available, **this must not be presented as strong population-level statistical confidence or a universal efficiency claim**. The source-to-submit p95 paired differences are mixed, and no statistically robust improvement in latency is claimed.

## Recovery and CPU-pressure diagnostics

Three additional loader-injected device-loss runs (one/profile) passed their producer gates and independent Vulkan/Wayland/image oracle. Each restarted the logical Vulkan device and both swapchains after a synthetic loader `VK_ERROR_DEVICE_LOST`, completed 120 frames, accepted 238/240 typed ACKs and left exactly two invalidated old-generation secondary IDs unacknowledged. **No actual NVIDIA driver loss or GPU reset was induced**.

Three bounded CPU-pressure runs (one/profile) also passed, with the private experimental Weston, producer, and viewer pinned to cores 18–19 and one `stress-ng` worker producing 45% target CPU load on core 18. Their `received_to_submit_us` distribution is **not directly comparable to the main trials**, because CPU pinning, scheduling and external contention changed. They are supplemental functional diagnostics, not evidence that load improves latency.

Three live negative controls (no recovery permission, second loss after one recovery, and nonexistent loss with recovery demanded) terminated nonzero with no false positive receipts. The statistical-analysis falsification suite rejects/holds 12/12 manipulated inputs, including source-plan reordering, oracle result forgery, missing idle observations, and manufactured CPU advantages. Clippy with `-Dwarnings`, legacy CP-JA7E feature check, and the 31 `blob-frame` tests pass.

## Actual gates and nonclaims

| Preregistered gate | Verdict |
|---|---|
| A1: 15 normal E2Es, 3 loss E2Es, 3 fail-closed negatives | PASS |
| A2: 240 valid Vulkan ACKs and 8 verified screenshots for each normal trial | PASS |
| A3: cancellation and worker cleanup under loss | PASS |
| A4: all p95 ≤100ms and p99 ≤200ms warm-frame latencies | PASS |
| A5: truthful per-thread CPU / context / idle counters | PASS |
| A6: bounded eco cost and no large p95 regression | PASS |
| A7: exact plan, binary and evidence immutably hashed | PASS once final seal generated |
| Supplemental three constrained CPU-pressure diagnostics | PASS, limited scope |
| Controlled GPU load, power draw, watts/frame, thermal analysis | NOT RUN |
| Long-duration operation, robust population CI, broad workload coverage | NOT RUN |
| Real driver-originated loss, cross-vendor, second compositor | NOT RUN |
| CP03 HYBRID-60, steady-state 60 FPS, zero-copy, photons | NOT RUN |

The achieved scoped PASS **does not authorize a new production default**. The current implicit profile remains `balanced` until a product-level rollout and full-workload evaluation are separately approved. For the next engineering gate, qualify longer sustained multi-workload scenarios, thermal/power instrumentation and CPU/GPU contention before proposing a default change or expanding CP03 HYBRID-60.

No merge, push, release, production deployment, resident Hyprland modification or physical GPU reset was performed.
