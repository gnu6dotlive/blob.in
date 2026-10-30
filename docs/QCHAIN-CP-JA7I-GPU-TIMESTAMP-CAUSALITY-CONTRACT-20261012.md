# CP-JA7I — GPU Timestamp Queries and Frame-Pacing Causality

Date: 2026-10-12. Parent: `f99eebaa2e253ad3b2abbc4c339bbcd7c9425027`.
Private opt-in worktree, RTX 3070 and isolated Weston 15; Hyprland must remain untouched.
Preregistered BEFORE tested long runs. Any unproven gate is HOLD, never promoted.

## Scope and measurements
- Two 1200-frame real Vulkan/WGSL F4 E2E runs on the same experimental viewer executable:
  `balanced-33` at 33ms and `balanced-16` at 16ms requested intervals.
- Require actual adapter support for wgpu `Features::TIMESTAMP_QUERY` on the
  Vulkan device; no synthetic GPU timestamp or substitution of CPU duration.
- Encode GPU timestamp pairs surrounding actual **primary and secondary wgpu render passes**.
  Resolve query set after the final submission and read back once with a bounded GPU poll.
  Report 1200 nanosecond-scale intervals per swapchain, their period (ns/tick),
  strictly positive reasonable values, and independent byte-decoding of raw query data.
- **GPU F4 compute kernel and readback are NOT individually timestamped here:**
  the separately precompiled `PersistentSession` source is outside this worktree.
  Existing CP-JA7H `render_next` remains combined compute+readback host time.
- For every source sequence, log frame-ready observation, wake schedule, chosen next
  deadline, event-loop activity, time spent drawing and actual submitted timestamp.
  Analyze lateness, event-loop scheduling, source availability and draw duration
  by seq, distinguishing correlation from an independently intervened causal result.

## Admission
- Both E2E complete 1200 canonical F4 frames, 2400 real Vulkan typed ACKs,
  2400 Weston server `presented` and eight differentiated screenshot samples,
  RGB per-channel <=3 alpha exact and 0 orphan ACK per run.
- GPU timing: one real nonzero positive pass interval per primary and secondary
  frame, no missing/duplicated indices, exact raw query byte size and SHA256.
- Raw independent oracle recomputes GPU ticks into ns and compares claimed aggregates.
- Event trace has exactly 1200 unique source IDs; source-to-submit monotonic.
- 33ms and 16ms cadence reported, not assumed; 16ms is NOT 60FPS qualification
  absent independent physical scanout/photons and full CP03 HYBRID-60 gates.
- Each session sampled NVIDIA whole-board temperature/power ~1s; abort on >=75C,
  >=180W, sensor unavailable/stale >3s, or wall >100s; baseline must be <65C.
- Opt-in only; preserve CPJA7H legacy build, 31 blob-frame tests, strict Clippy.
- Independent adversarial mutations of GPU query, timing, ACK, source and pixels
  all rejected; three synthetic private loader-fault scenarios fail closed.
- Git clean local commit, sealed SHA256 evidence; no push/merge/deployment/reset.

## Explicitly unqualified
GPU compute F4 timestamp attribution, CPU/GPU clock synchronization, energy per frame,
GPU saturation, scanout latency, photons, actual driver-originated device loss,
AMD/Intel and cross-OS behavior, continuous 60 FPS, CP03 HYBRID-60, production release.
