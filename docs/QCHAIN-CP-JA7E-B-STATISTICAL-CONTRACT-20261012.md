# CP-JA7E-B — Controlled Scheduler Characterization (preregistered)

Parent: `05d72e501910d82e4c5b1eb4a0e4bb7e9d356808`.
Date: 2026-10-12. Branch: `feat/qchain-scheduler-statistical-20261012`.
Status at preregistration: **NOT RUN / no promotion authorized**.

## Protocol

- Isolated Weston 15 headless GL, RTX 3070, two 512×384 WSI swapchains, 120 canonical F4 source frames per run.
- Three feature-on scheduler modes: latency (250 us), balanced (1000 us), eco (4000 us); no physical GPU reset or global layer installation.
- Fifteen no-fault E2Es: five rounds of three profiles, profile order shuffled by fixed seed `20261012`; exactly eight compositor captures per run. No silent retry of failed runs.
- Additional opt-in control: three loader-device-loss E2Es, one per profile, with old-generation ACK cancellation.
- Three fail-closed cases on the exact qualified binary; no-recovery, double-loss, no injection.
- Measurement: native per-worker `RUSAGE_THREAD` CPU microseconds, Vulkan wait invocations / timeouts / idle-block time, frame-level `received_to_submit_us`, and Linux `/proc/thread-self/status` context-switch deltas if observed.
- Baseline comparisons are **within the 15 repeated randomized no-fault runs**, not the earlier CP-JA7E pilot; quote medians, ranges, and all runs. Worker CPU != whole-host CPU; no power instrumentation.
- All positive E2E receipts must pass the independently developed CP-JA7D-B source/pixel/Vulkan/Wayland oracle, not merely the producer gate.
- No production-readiness claim from this small sample; cross-vendor, sustained 60 FPS, hybrid-60, zero-copy, hardware loss remain OPEN.

## Acceptance criteria declared before executions

A1: 15/15 normal E2Es, three profiles represented exactly five times; 3/3 loader-recovery E2Es; 3/3 fail-closed controls; no missing or duplicated sources.
A2: all 120 frames, 240 issued/validated Vulkan waits and 240 typed ACKs per normal E2E; 8/8 compositor captures, dual-surface signature, independent oracle PASS.
A3: no late old-generation success under loader loss, two workers per normal run/four with rebuild, private Weston process cleanup and clean Git worktree on seal.
A4: each normal run's warm `received_to_submit_us` (source frames 5–119) p95 <= 100,000 us and p99 <= 200,000 us. If any trial fails, mark scheduler latency gate HOLD without dropping the run.
A5: all workers report finite nonnegative counters with actual wait successes; idle channel blocking witnessed, no worker thread remains on completion. Idle-energy **not claimed**.
A6: any claim that eco improves CPU requires paired five-round comparison: median(eco CPU) <= 0.90*median(latency CPU), median(eco calls) <= 0.75*median(latency calls), and median(eco p95) <= 1.25*median(latency p95). Otherwise report neutral/inconclusive, not improvement.
A7: run order, profiles, original binary hash, raw traces, version of acceptance contract, and metric extraction code must be sealed SHA-256; no editing thresholds post hoc.

These are *scoped pass criteria* for this experimental workload, not blanket statistical confidence across machines, variable workloads, or applications.

