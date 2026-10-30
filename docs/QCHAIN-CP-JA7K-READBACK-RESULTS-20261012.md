# CP-JA7K — GPU readback copy timestamps / pipeline throughput

Date: 2026-10-12. Parent: `46d217ce9f1dce6d3cc95e2eb0d2dc4a2f841e62`.
Branch: `feat/qchain-f4-readback-timestamps-20261012`.

**Decision: SCOPED PASS for individual real GPU copy commands and one bounded native E2E.**
**Not qualified: copy-to-CPU/PCIe transfer attribution, sustained 60 FPS, CP03 HYBRID-60.**

## What was actually measured

From the pinned CP-JA7J-C source snapshot, enable both
`TIMESTAMP_QUERY` and `TIMESTAMP_QUERY_INSIDE_ENCODERS`.
Preserve the original six Vulkan compute passes, then write GPU timestamps
around three separate `copy_buffer_to_buffer` commands in the same
command encoder, same GPU queue submission, no intermediate synchronization.
Each frame has 18 real GPU timestamp values (nine pairs).

| GPU command on physical RTX 3070 | Median | p99 |
|---|---:|---:|
| F2 compute | 16.832 µs | 18.304 µs |
| F3 compute | 72.896 µs | 77.952 µs |
| Shadow compute | 14.656 µs | 16.096 µs |
| Blur compute | 117.984 µs | 135.392 µs |
| Bloom compute | 289.472 µs | 307.744 µs |
| Echo compute | 12.000 µs | 16.896 µs |
| Final RGBA GPU copy | 43.008 µs | 53.248 µs |
| F2 mask GPU copy | 43.008 µs | 53.248 µs |
| F3 analytic GPU copy | 151.552 µs | 166.912 µs |

The three median copy-command times total approximately **0.238 ms**
(as an indicative sum only). This measures execution between Vulkan GPU
timestamp markers, not CPU `map_async` completion or transfers over PCIe.
Host-side `device.poll`/mapping wait had a median **1,216.5 µs**,
and entire release-build `render_next` a median **2,520 µs**.
These overlapping/aggregated quantities are not additive end-to-end latency.

## Independent E2E qualification

- 300-frame private pilot: 5,400 timestamp values, 43,200 raw bytes;
  canonical F4 source checks, two native Wayland surfaces, eight captures PASS
- Full private Weston run: 1,200 canonical GPU-rendered F4 frames,
  7,200 compute dispatches, 1,200 GPU queue submissions,
  **21,600 hardware GPU timestamps in 172,800 raw bytes**
- 2,400 native Vulkan WSI typed ACKs, 2,400 Weston server-side
  `presented` feedbacks, zero false-ACKs; eight 1536×1024
  compositor screenshots independently validated against F4 RGBA
- Effective **30.2023 FPS source submission**, across 39.699 seconds;
  does **not** establish 60 FPS physical display scanout
- NVIDIA safety guard: 43 readings, whole-board maximum **53 °C**
  and **58.12 W**; no thermal/power ceiling violation
- Independent oracle recomputed all 1,200×9 tick differences,
  checked original six kernel witnesses, three GPU copy witnesses,
  frame ordering, timestamps, byte count, native WSI and screenshots
- 12/12 adversarial evidence mutations rejected; strict F4 Clippy PASS,
  CP-JA7J-C legacy source builds, 31/31 Rust `blob-frame` tests pass

An initial adversarial pixel mutation targeted an area outside the observed
surfaces and correctly did not fail the visual oracle; it was archived as
test-development evidence. The corrected in-surface mutation was rejected.
No positive raw evidence was modified.

## Reproducibility and limitations

`tests/cpja7k/gpu-session-readback-query.patch` can be applied to the
pinned CP-JA7J-C source with the SHA-256 checked materializer script.
The freshly materialized source matched the qualified private snapshot
byte for byte; output executable and input hashes were pinned before
the long E2E. Parent CP-JA7J-C remains intact.

New producer compiled using **Cargo release optimizations**, unlike certain
earlier CP-JA7J-C reference builds. Cross-run differences in absolute FPS,
wall time or GPU compute durations are therefore descriptive, **not
controlled A/B evidence of an instrumentation effect**.
The inherited CP-JA7J factorial transport experiments remain separately
qualified, but this run does not isolate a new unique throughput bottleneck.

No driver-originated device loss, GPU reset, resident Hyprland disruption,
merge, push, deployment, production promotion, vendor interoperability
or CP03 HYBRID-60 claim. Next: paired matched-build transport interventions,
host copy/mapping profiler and independent display timing.
