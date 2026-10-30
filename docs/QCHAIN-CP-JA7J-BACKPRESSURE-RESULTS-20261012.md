# CP-JA7J — Backpressure and sealed-memfd client ownership

2026-10-12. Parent 267f03c63c0e6c1b7b26cf965387e35dd7e9fcd2.
Decision: **SCOPED PASS for 8 controlled source + 4 client experiments**.
No claim of 60 FPS, thermally saturated GPU, or independent display scanout.

## A: preregistered 2x2 mirror with one unchanged viewer + engine

Each result is a full 1200-frame private Weston E2E, physical RTX 3070,
16ms requested interval, balanced Vulkan polling; same exact binaries.
Pipe is confirmed using Linux F_GETPIPE_SZ. Canonical full-byte equality
remains checked every frame in all configurations; optional in-memory
reference preload never caches or bypasses the equality verdict.

| Pipe | Reference policy | First FPS | Mirrored FPS |
|---|---|---:|---:|
| 64 KiB | Read baseline each frame | 29.0801 | 29.3161 |
| 1 MiB | Read baseline each frame | 29.6305 | 29.8133 |
| 64 KiB | Cache reference bytes | 29.4957 | 29.5641 |
| 1 MiB | Cache reference bytes | 29.6423 | 29.8824 |

Pipe expansion with reference cache OFF: paired submit-throughput
differences +0.5504 and +0.4972 FPS (median +0.5238 FPS), with
source stdout write median reduced 454.5 and 812.5 microseconds.
Pipe expansion with cache ON: +0.1466 and +0.3183 FPS.
Cache with small pipe: +0.4156 and +0.2480 FPS, canonical
byte-compare median reduced 400.0 and 273.5 microseconds.
Cache with large pipe: +0.0118 and +0.0691 FPS; very small.
Only two replicates per cell, fixed mirrored rather than randomized:
effects are reproducible in sign in this sample, NOT conclusive significance
or reliable estimates for external hardware/workloads.

Every run: 1200 canonical compute frames, 2400 Vulkan typed ACKs,
2400 Weston presented, 4800 authentic GPU query timestamps, eight
pixel-qualified private compositor captures. Across A: 9600 frames,
19200 ACKs, 38400 queries and 64 captures. All safety guards PASS.
12/12 deliberate falsifications of reference, intervention, timestamp,
Vulkan, Weston and pixels were rejected by the independent oracle.

## B: sealed mapping ownership vs explicit client copy

Experimental feature `cpja7j-mmap-consumer` enables two modes in exactly
one compiled viewer executable: `copy` materializes mapped bytes into
Vec<u8>; `mmap` retains the immutable, read-only `MappedFrame` directly.
Both still SHA256 hash all pixels before drawing and use
`wgpu::Queue::write_texture`; this is NOT end-to-end GPU zero-copy.
Broker: fixed 64 KiB pipe, no reference cache, exact same GPU engine.

| Client mode | Trial A FPS | Trial B FPS |
|---|---:|---:|
| Explicit CPU Vec copy | 29.0076 | 29.0385 |
| Retained sealed mmap | 27.7984 | 28.2810 |

Paired mmap-minus-copy throughput: -1.2092 and -0.7575 FPS.
Measured combined client SHA256/copy host medians are **higher** for
mmap by 319.5 and 146.0 microseconds; p99 worse by 1421 and 2073 us.
Thus client copy elision is **NOT a throughput optimization** here.
Possible memory paging, layout and wgpu staging effects remain hypotheses
without hardware memory-fault attribution. Keep Vec copy as default.

Four E2E: 4800 frames, 9600 Vulkan typed ACKs, 19200 GPU timestamp
queries and 32 compositor captures, all independently qualified.
8/8 client-specific false witnesses rejected; loader synthetic fault
negative controls 3/3 fail-closed on the mmap-capable viewer binary.

## Provenance and limitations

One exact source tree matching engine metadata `5132cf59` was found at:
`/mnt/workbench/workspaces/gnu.in.labs/.worktrees/in-gnu6-qchain-cpf-persistent-20261010/experiments/blobin-next-01/F4/src/gpu_session.rs`.
It contains six real Vulkan compute passes F2/F3/F4 and three final GPU
buffer readbacks. CP-JA7J A/B used the prebuilt original binary; we
did NOT add compute-pass GPU timestamps to this source in A/B.
This source can be copied into a separate lab, with exact Git+SHA evidence,
for per-dispatch Vulkan timestamp experiments. The original remained clean.

The 75 C / 180 W abort ceilings were never reached. Board sensors describe
the whole shared GPU and do not attribute power to this experiment.
Actual display photons, kernel timestamps, client energy, steady 60 FPS,
CP03 HYBRID-60, non-NVIDIA/second OS and production promotion remain OPEN.
Local worktree and Git only; no device reset, merge, push or deployment.
