# CP-JA7G — Sustained active F4 GPU compute and dual WSI presentation
Date: 2026-10-12 (Montréal). Parent: `1bde593ab0ffcfa4cd696d79a2d644c08835a973`.
Branch: `feat/qchain-active-gpu-soak-20261012`. Status: NOT YET QUALIFIED.
Experiment is on private Weston 15 GL, not resident Hyprland. RTX 3070 physical GPU.

## Claims and exact workload
- Extend the native CP-I02 Rust `PersistentSession` compute producer under a private experiment source and binary from a maximum 300 to a strictly bounded 4800 source frames. The original binary remains untouched.
- Two separate full E2E trials: 3600 source frames at a nominal 33ms viewer presentation interval, one `balanced` (1000us Vulkan wait poll) and one `eco` (4000us Vulkan wait poll). Expect approximately two minutes per run, not 20min and not continuous 60 FPS.
- Each source frame is *freshly computed* by the same GPU session: 6 Vulkan/WGSL compute dispatches and 1 GPU queue submission, 0 intermediate host transfers; emitted RGBA readback is cryptographically and byte-for-byte compared to one of eight authenticated CP-F F4 baselines. Final source stats must show 3600 frames, **one device**, three pipelines, five persistent buffers.
- Each source frame is individually transferred via one immutable sealed memfd, then drawn by wgpu to two distinct 512x384 Vulkan Wayland swapchains: 7200 native present IDs issued and real wait-success typed ACKs, 3600 deliberately reordered ACKs; cap 2 outstanding per swapchain.
- Eight 1536x1024 Weston compositor screenshots per run distributed across scene/variant states: frame targets [9,501,993,1485,1977,2469,2961,3453]; two surfaces must visually differ only by verified 16px secondary stripe, RGBA alpha exact and per-channel RGB delta <=3. Screenshots captured once target is reached; image must be independently compared to an authenticated frame from a narrow adjoining source window, to avoid falsely assigning an asynchronously captured compositor image to an older submitted ID.
- GPU reference device is shared with the resident desktop and user applications; `nvidia-smi` measures **whole board**, never attributable application-only watts, GPU saturation, or frame energy.

## Predeclared gates
- G01: both runs produce 3600 canonical frames, sequential IDs 0..3599, 6 actual compute dispatches + 1 GPU submission/frame validated in the engine source and per-frame output; single engine process/GPU device; 3 pipelines, 5 allocations. Expected combined compute dispatches = 43,200.
- G02: each run produces exactly 7200 typed Vulkan waits/ACKs, zero orphan/duplicate/fictitious ACKs; two WSI swapchains, 7200 compositor `presented`, zero `discarded`. No device recreation or loss; outstanding <=2 per swapchain.
- G03: screen RGBA conforms to canonical GPU F4 frames with two distinct windows and eight samples/run. Independent native oracle must read raw GPU/Wayland/pixel traces and recompute verdict; producer verdict is not sufficient.
- G04: duration between first and last source submissions >=95s, 90% consecutive inter-frame intervals in 20–100ms, p99 <=250ms, total run duration <240s. This is a qualification of near-30fps source-to-presentation pacing, **not** CP03 HYBRID-60 or photon/display scan-out FPS.
- G05: guard samples `nvidia-smi` at ~1s, requires at least 95 valid samples, no gap >3s, board temperature <75°C and power <180W for all samples; fail-closed if baseline temperature >=65°C, observed sensor failure or wall timeout 240s. Record CPU and GPU utilization, power, fan, VRAM; optional CPU18 45% load must be separately labeled if applied. No GPU reset or clock/fan/power overrides.
- G06: preserve existing 300-frame CP-JA7F feature via build/check; new extended count only enabled by `cpja7g-active-gpu`. Three live fail-closed controls on qualified exact viewer must reject unauthorized synthetic loss, second loss, and nonexistent loss; do not claim vendor-emitted device loss.
- G07: mutation-based independent oracle tests must reject forged source hash, Vulkan wait/ACK, compositor pixel/feedback, thermal sample and FPS count. Pre-run hashes of contract and binaries, source tree commit and immutable evidence manifest; local commit/clean worktree, no merge/push/deploy.

## Safety / limits
- Two tests rather than a speculative overnight stress; GPU temp abort >=75°C and board power abort >=180W; stop if sample gap >3s. No real NVIDIA driver-originated device loss or GPU reset.
- This is *compute-active* at a small 512x384 bounded workload, not guaranteed high GPU utilization or thermally saturated. A low nvidia-smi utilization reading does not invalidate the fact of real GPU compute; it limits saturation claims.
- No application-specific energy, 60fps, CP03 HYBRID-60, AMD/Intel, second OS, zero-copy, multi-hour endurance or production scheduler promotion.
- A failed run remains archived and excluded, without changing acceptance criteria after observation. Claims requiring absent direct proof remain HOLD.
