# CP-JA7J — F4 source transport backpressure, controlled intervention

12 October 2026 · Parent commit `267f03c63c0e6c1b7b26cf965387e35dd7e9fcd2`.
Experiment remains isolated in private Weston, not Hyprland production.

## Preregistered experiment
- A 2×2 factorial intervention on existing CP-JA7I viewer with identical binary and GPU F4 engine:
  producer stdout pipe **65,536** vs **1,048,576** bytes, and canonical reference
  bytes loaded **on each frame** vs **preloaded once** at broker initialization.
- Keep *full-byte equality*, opacity check, sealed memfd, peer UID, metadata
  canonical stage+hash, client SHA256, two Vulkan WSI presentations and GPU timestamps.
- Eight full 1200-frame active runs: `control-a`, `pipe-a`, `cache-a`, `both-a`,
  `both-b`, `cache-b`, `pipe-b`, `control-b`. Every run 16ms target, balanced
  Vulkan profile; this ABCCBA-style mirrored order is fixed before measurement.
- An optional copy-elision third factor is separately proposed, not authorized
  as a PASS until tested with lifetime-safe MappedFrame ownership and same oracles.
- Control of pipe buffer confirmed by Linux F_GETPIPE_SZ, with startup witness
  inside the broker. Every canonical equality verified, never memoize the result.
- Timing tracked per frame for Rust compute+readback, Rust stdout write,
  broker canonical comparison, broker IPC, client mapped bytes SHA256/copy,
  host draw, hardware GPU render-pass timestamps, Wayland feedback and RGBA captures.
- Minimum 90% of interframe submit intervals 10–100ms, p99 <=250ms, 1200
  source frames + 2400 genuine Vulkan ACKs, 2400 Weston presented, eight
  differentiated compositor captures, 4800 real Vulkan timestamp queries per run.
- Wall <=100s, temp <75C, whole-board power <180W and sensor time gaps <=3s.
  Baseline temp <65C. At least 15 valid NVIDIA samples/run.
- Exact original GPU engine + viewer hashes frozen and sealed before any full
  experiment. Only broker startup flags vary in the eight paired runs.
- Independent oracle reads raw logs/images/timestamps and compares against
  per-run intervention manifest: reject false pipe size, missing full byte comparison,
  incorrect reference digest, altered source hash or time, Vulkan ACK or pixel.
- Do not infer unique causality from a single uncontrolled historical comparison.
  Compare paired medians / p99 with both mirrored replicates; if effects are small
  or inconsistent, report INCONCLUSIVE. Shared NVIDIA GPU is a confounder.
- Three existing loader synthetic negative controls and Rust/Clippy regressions
  must pass. No real NVIDIA device reset or production deployment.

## Source provenance
- Precompiled `blobin_f4_effects` rlibs and relative `.d` dependencies do
  not establish reproducibly restored source code. Do not claim per-kernel
  timestamps or edit opaque GPU library; source recovery is a separate HOLD.
- CP03 HYBRID-60 requires independently confirmed sustained 60 FPS and
  scanout, and remains OPEN even if an optimization improves submit FPS.

## Safety and delivery
Worktree-local changes; no alteration of canonical CP-JA7I artifacts.
Archive failed probes. No false success; bounded workloads.
Commit locally, SHA256 seal only on independently qualified evidence.
External publishing/merging or production rollout is prohibited until
its separate qualification is ratified.
