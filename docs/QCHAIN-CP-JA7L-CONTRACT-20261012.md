# CP-JA7L — Matched-build throughput and host readback

Parent: `54c2daca0fb11e40a60554458c1a6b6808529a5d`.
Four 1200-frame E2Es, A-B-B-A order, interval 16ms.
A: 65536-byte pipe; B: 1048576-byte pipe.
Cache disabled; identical GPU source, viewer and broker binaries.
This is a bounded, sequential crossover: no randomized population inference.
One physical NVIDIA RTX 3070 and private Weston compositor; resident desktop unchanged.
Each run: 1200 canonical F4 frames, 7200 GPU compute dispatches,
21600 hardware timestamps (six kernels and three GPU copies),
2400 native Vulkan typed acknowledgements and 2400 Weston presented feedbacks.
Eight independently validated compositor screenshot witnesses per run.
Linux pipe capacity must be measured using F_GETPIPE_SZ: an unavailable
capacity disqualifies the treatment rather than becoming a placebo condition.
Native source, viewer, GPU readback and client-code SHA256 must remain identical
across all four runs; only CPJA7J_PIPE_BYTES differs.
A1 and A2 request 65536 bytes; B1 and B2 request 1048576 bytes.
Both CPJA7JC_F4_TIMESTAMPS and CPJA7K_COPY_TIMESTAMPS enabled.
All canonical comparisons run on every frame with cache disabled.
Primary endpoint: 1199/submit-span-seconds, per-run application FPS.
Compare within blocks (B1 minus A1; B2 minus A2), not pooled frames.
Secondary: medians and p99 of host readback wait, GPU copy durations,
producer pipe_write, broker pipe_read/verification and client integrity-copy.
Safety: preflight below 65C, abort at measured >=75C or >=180W;
maximum runtime 100s per run, >=15 telemetry samples, gaps <=3 seconds.
No GPU reset, resident compositor changes, push, merge or public deployment.
Strict source hash, typed Vulkan receipt, Wayland feedback and RGB pixel oracles.
Independent adversarial controls must reject incorrect pipe, source or WSI proofs.
The GPU copy commands are NOT host mapping or PCIe transfer timings.
The host and GPU intervals overlap and must not be added as end-to-end latency.
If effect signs diverge, report inconsistent directional effect.
Four runs are not proof of population significance or stable 60 FPS.
CP03 HYBRID-60 remains OPEN regardless of this scoped benchmark.
