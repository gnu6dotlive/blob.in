# CP-JA7J-C — Authentic six-pass F4 GPU timestamps

Preregistered 2026-10-12. Parent `ea8ffc63717f1690bd2b8e2c77ee1244ce32cef6`.
Native CUDA/NVIDIA graphics operations are not reset. Private worktrees only.

## Source truth and mechanism
- Source snapshot cloned byte-identically from historical clean Git commit
  `5132cf59b3842e27dcacf89bfe7060e807706e90` in
  `/mnt/workbench/workspaces/gnu.in.labs/.worktrees/in-gnu6-qchain-cpf-persistent-20261010/experiments/blobin-next-01`.
- Original F1/F2/F3/F4 sources remain unchanged. Only private snapshot can
  receive timestamp instrumentation; save original source hash and patch script.
- Instrument 6 genuine Vulkan/WGSL compute passes individually via wgpu
  ComputePassTimestampWrites pairs: F2, F3, Shadow, Blur, Bloom, Echo.
- One 12-query Timestamp QuerySet per actual F4 frame, period sourced from GPU
  `queue.get_timestamp_period()`, resolved once in same command buffer.
- Read 96 raw query bytes per frame after the same GPU submission. Map
  alongside existing three full readbacks without intermediate host transfers.
- Preserve 1 device, 3 pipelines, 5 persistent output buffers, six dispatches
  and one queue submission per frame; query diagnostic buffers may be transient.
- Host `compute+readback` measured independently of the six GPU intervals.
  The original three GPU-to-host readbacks remain grouped, not per-copy GPU
  duration. Do not call CPU wait time the GPU copy duration.

## Experiments and gates
- Private 300-frame source probe: each frame must exactly byte-match its
  canonical F4 artifact and produce a strict 12-tick positive GPU query record.
- Qualified extension: 1200-source-frame full native private Weston E2E,
  2400 typed Vulkan ACKs, 2400 server-side Wayland presented, 8 compositor
  captures and 4800 independent viewer rendering GPU query timestamps.
- Pre-register source and binary SHA256, validate sample telemetry at 1Hz,
  <75C and <180W, no sample gap >3s, wall <=100s.
- Independent byte-level oracle replays the 1200×12 F4 query u64 records
  and compares them to each logged six-pass durations and period.
- Mutations must reject missing query record, forged GPU period/duration,
  corrupted F4 image hash, incorrect Vulkan ACK and compositor pixel.
- Rust cargo build/test and strict Clippy for experiment source and viewer.
- Produce clean local git commit with exact provenance, SHA256-sealed proof.

## Out of scope
Full per-readback GPU copy timestamps, GPU/CPU clock synchronization,
application-only GPU energy, render photons, 60FPS, CP03 HYBRID-60.
Do not push, merge, deploy or modify any live compositor or historical code.
