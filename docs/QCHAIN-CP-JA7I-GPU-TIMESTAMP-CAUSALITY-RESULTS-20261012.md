# CP-JA7I — Real GPU Timestamp Queries & Frame-Pacing Causality

2026-10-12 · Parent f99eebaa2e253ad3b2abbc4c339bbcd7c9425027.
**Verdict: SCOPED PASS — real Vulkan/wgpu render-pass timestamps + event-loop timing.**
**Not qualified: CP03 HYBRID-60, individual F4 kernel timestamps, or a proven causal bottleneck.**

## Qualified execution
Two separate 1,200-frame native E2Es, balanced polling on physical NVIDIA RTX 3070,
private Weston GL compositor on Wayland, two independent 512x384 swapchains.
Each E2E has 2,400 real Vulkan typed wait ACKs, 2,400 server-side Weston presented
feedbacks, eight verified compositor captures, and all canonical F4 source hashes.
Two actual wgpu timestamp QuerySets, 2,400 queries each, were resolved after rendering;
each E2E produced exactly 4,800 positive hardware timestamps in 38,400 raw bytes.
GPU timestamp period reported by wgpu on this Vulkan device: 1.0 ns per tick.

| Metric | Requested 33 ms | Requested 16 ms |
|---|---:|---:|
| Actual submission rate | 29.7925 FPS | 29.6474 FPS |
| Primary render-pass GPU duration p99 | 13.312 microseconds | 13.312 microseconds |
| Secondary render-pass GPU duration p99 | 13.312 microseconds | 12.288 microseconds |
| Wake lateness p99 | 1.007 ms | 1.007 ms |
| Draw API median | 4.352 ms | 4.626 ms |
| Host F4 compute + readback median | 12.065 ms | 12.288 ms |
| Source stdout write median | 21.380 ms | 21.256 ms |
| Viewer integrity + CPU copy median | 18.615 ms | 18.492 ms |
| Peak observed GPU temperature | 52 Celsius | 52 Celsius |
| Peak observed whole-board power | 66.49 W | 57.61 W |
| NVIDIA telemetry samples | 43 | 43 |

Measured GPU pass timing spans **presentation fragment/vertex rendering only**.
It excludes F4 compute shaders, source GPU readback, host memcpy, texture upload,
Vulkan queue wait, Wayland compositor and photon/display scanout.
Timestamp intervals are computed independently from little-endian unsigned 64-bit
query bytes and the Vulkan queue timestamp period, and checked against producer sums.

## What the causal observations show
At a 16ms requested interval the pipeline still submits fewer than 30 frames/s.
Each window's GPU render pass completes within a few dozen microseconds;
the event-loop wake itself is typically on time (p99 near 1ms late), and
host draw-call spans are much smaller than an entire 33ms frame period.
The serial source chain exhibits much larger host stages: combined F4 compute/readback,
stdout pipe backpressure, canonical reference verification, and client CPU copy.
These are plausible pipeline throughput constraints, **not a proven unique bottleneck**.
Measurements from separately overlapping stages cannot simply be summed to form
end-to-end frame latency. One controlled intervention on an individual transport
or validation component is still needed before causal attribution.

One proposed counter, empty_source_polls, was never incremented in the tested
viewer implementation and is explicitly **NOT INSTRUMENTED**, notwithstanding
the zero values in existing raw viewer lines. Do not infer an absence of source
starvation from this field. Per-frame ready-dwell and wake-deadline spans are valid.

## Safety, failures, and nonclaims
The initial 300-frame single-QuerySet pilot succeeded, but a 1200-frame
preflight was rejected before rendering because one 4800-query set exceeded
wgpu's 4096-query hard limit. Replacing it with two independent query sets
(2400 each) passed a separately attributed 300-frame pilot and both full runs.
A first no-injection negative harness failed because it omitted the required
timestamp raw output path; the new isolated harness passed on a fresh run.
Both failures remain in the immutable evidence ledger, excluded from successes.

Three synthetic Vulkan loader negative controls passed fail-closed;
11/11 independent evidence falsifications were rejected.
Clippy -Dwarnings on the actual CP-JA7I feature, inherited CP-JA7H
build and all 31 blob-frame tests passed.
Observed temperatures stayed below 75 Celsius and whole-board power
below 180W. GPU utilization and power include user/resident GPU activity;
no experiment-specific energy attribution is asserted.

No GPU reset, Hyprland intervention, merged branch, remote push, deployment
or promotion of the experimental runtime into production.

**NEXT: CP-JA7J — Source Transport Backpressure Interventions & F4 GPU Timestamp Probe.**
Run randomized A/B/C interventions on source pipe, canonical comparison and
client copy while keeping exact F4 source trust. Independently restore or
vendor F4 GPU-session sources and introduce compute/readback timestamps.
Only after an independently observed scanout/feedback gate consider CP03 HYBRID-60.
