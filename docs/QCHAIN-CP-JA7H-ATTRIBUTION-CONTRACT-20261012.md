# CP-JA7H — Causal frame-time decomposition / HYBRID-60 prequalification
2026-10-12 · Parent `ae728e6ef1a5e342f437295ac2ab40b990579c25`.
Branch `feat/qchain-frame-attribution-20261012`. Status **PREREGISTERED / NO PASS**.

## Goal and proof ceiling
Provide frame-indexed, **host-clock wall time** attribution for actual Vulkan F4 computation, producer stdout, broker verification / sealed memfd, client IPC and integrity, texture upload API, drawing and queue submission, Vulkan WSI present calls, independently observed typed wait successes and Weston compositor feedback. Use two 1200-frame full native E2Es on one RTX3070: `balanced-33ms` and `balanced-16ms`, both with the same sources/surfaces/worker policy. A short unscored 300-frame pilot must qualify code paths first.

**No GPU timestamps are claimed** for shader invocation or readback. `PersistentSession::render_next()` includes GPU compute submission, any GPU synchronisation and readback; its wall time remains a **combined host-visible blocking span**. Queue submit/present API duration is **not** GPU execution duration; Weston `presented` feedback is **not** photon/display scanout. Python and Rust emit stage elapsed intervals, not unsynchronised absolute-clock deltas. No simple sum of independently measured stage durations is end-to-end latency if frames overlap.

## Fixed experimental admission
- Experiment-only `cpja7h-timing` feature keeps CPJA7G trusted 1200-frame Vulkan producer, sealed memfd, 2 wgpu swapchains and private Weston desktop with 512×384 surfaces (1536×1024 desktop).
- Profiles: balanced at **33 ms** requested interval; balanced at **16 ms** requested interval; 1200 frames each. One device and 2 swapchains per run. Each raw output frame must byte-match canonical F4; 6 GPU compute dispatches + one queue submission per frame; no GPU/Wayland loss.
- Eight compositor captures per run at frame targets [9,165,333,501,669,837,1005,1173], aligned to canonical variant windows; independent RGB <=3 / alpha exact. Separately validate all 1200 frame hashes, 2400 Vulkan issued/wait success/typed ACK, 1200 deliberate out-of-order ACK and 2400 Weston server `presented` per run; zero false ACKs.
- Host-stage traces keyed by sequence, exact cardinality 1200 each: `render_next` inclusive, write/flush stdout, broker receive-parse, canonical comparison, memfd seal/send, viewer packet request→recv→hash→queue-ready, wgpu texture upload API, primary and secondary encode/submit/present calls. Per-stage durations strictly >=0, monotonic source ordering. Confirm no missing samples or retroactively invented timing lines.
- The **33ms baseline** should span at least 35 seconds between first/last viewer submissions and the **16ms target** at least 17 seconds, both with >=90% inter-frame gaps 10–100ms, p99 <=250ms, and runtime <100 seconds. The target establishes attempted faster cadence only, **not 60 FPS qualification**; report measured throughput, budget shares and tail distributions.
- NVIDIA preflight baseline temp <65°C and board power <180W; guard entire E2E with ~1s nvidia-smi samples, reject gap >3s, any temp >=75°C, board power >=180W, invalid sample or wall >100s. Minimum 15 sensor samples per run; shared GPU power and utilization never attributed to application. CPU affinity 18–19, no stress-ng by default, never change driver fan/clock/power or Hyprland.
- Two independent oracles: (1) source/Vulkan/Weston/capture proof reading raw files not runner PASS; (2) timing-specific counter / negative-duration / bogus stage / spoofed frame / fabricated faster-FPS proof rejection. Enforce immutable pre-run hash anchors of viewer, producer, contract.
- Three inherited synthetic Vulkan loader negative controls may be run using the same viewer: unauthorized recovery, double injection and fault expected but absent. They must fail closed, without physical GPU reset.
- Clean local Git commit and final SHA-256 evidence seal. No merge, push, deployment or production policy changes.

## Explicit gates remaining open
Without device GPU timestamp queries, cannot partition shader execution vs GPU readback; without independent display timebase, cannot assert photons, vsync lock or sustained 60 FPS; sampled GPU utilization cannot determine sole application GPU occupancy. CP03 HYBRID-60 remains **OPEN**, even if 16ms pacing looks favorable. All absent, interrupted or falsified evidence is HOLD.

