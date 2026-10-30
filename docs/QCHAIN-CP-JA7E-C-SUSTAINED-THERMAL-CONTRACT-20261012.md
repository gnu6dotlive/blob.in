# CP-JA7E-C — Sustained runtime, thermal observation and bounded mixed-load contract

Parent: CP-JA7E-B commit `f6a7ec14363e09ee80b77b1a1fde63123af727dc`.
Branch: `feat/qchain-sustained-thermal-20261012`.
Status at admission: **unexecuted; this document is the preregistration**.

## Environmental authority and safety envelope

- Physical reference device: NVIDIA RTX 3070 on Arch/CachyOS. The resident Hyprland compositor and user processes stay untouched.
- Isolated Weston headless GL compositor, private Wayland socket, exactly two native wgpu/Vulkan swapchains, canonical 512×384 F4 source frames, NVIDIA runtime/loader. No global Vulkan layer install, no TDR/GPU reset, no clocks/fan/power-cap changes.
- Sensor: `nvidia-smi` reports board GPU temperature (°C), board power draw (W), GPU utilization (%), memory usage (MiB) and fan (%). All are **whole-device measurements, not attributable exclusively to this test**. Thermal/energy conclusions must not assume uncontended GPU access.
- Baseline observed before test: 51°C, ~40.65W, GPU utilization ~37%, ~1290MiB; dynamic baseline will be retaken. If sensor is missing, stale, invalid, or baseline GPU temp ≥65°C, deny active runs.
- Abort **immediately when sampled** GPU temperature ≥75°C or board power ≥180W. Treat monitor failure, test timeout (>60s per 300-frame run), lost/duplicated source or failed compositor oracle as FAIL-CLOSED. No claim of preventing excursions *between samples*.
- Sample nvidia-smi every ~1s and write JSONL with monotonic timestamps. Monitor runs concurrently with each test (including exit), never assert no thermal excursion when no valid samples.
- CPU background stimulus: at most one `stress-ng --cpu 1 --cpu-load 45` worker pinned to logical CPU 18. The test launcher/child processes are pinned to logical CPUs 18–19 only. Do not stress all CPU cores, system-wide memory, or GPU with noncanonical tasks.
- If the user GPU board is already over guard bounds, run no stress and place the gate on HOLD.

## Plan fixed before execution

S1 — One 300-frame no-fault preregistration pilot, profile balanced, verifying that the existing 300-frame native source broker and viewer can complete with no semantic drift and screenshot parity.

S2 — Six separately isolated 300-frame sessions interleaved balanced/eco (`balanced,eco,eco,balanced,balanced,eco`). Each run creates a fresh Weston compositor and Vulkan device, includes eight compositor screenshots at distinct source states, worker metrics and exact success ACK ledger for 600 WSI IDs. This is a **multi-cycle ~minutes-scale soak**, not a single uninterrupted 30+ minute runtime. No silent retry or cherry-picking.

S3 — Exactly session 3 (eco) and session 4 (balanced) have bounded 45% CPU stimulus on core 18. All seven 300-frame runs are confined to cores 18–19; the other four planned sessions and the separate pilot have no injected CPU load. Ordinary host workload remains uncontrolled.

S4 — Two independent 120-frame injected-loader-loss E2E trials, balanced and eco; require old-generation ACK revocation and in-process reconstruction with original oracle. Three inherited fail-closed negatives: unauthorized recovery, double loss and missing expected fault. No physical loss.

S5 — Per run capture CPU worker use, polling counts, context switches, live GPU power/temperature/utilization/fan/memory and frame-level submission latency. At least five valid GPU samples per 300-frame run including a pre-run reference sample. Report **whole-device board power**, not application energy consumption.

## Predeclared PASS/HOLD gates

G01 — Six planned 300-frame multi-cycle runs 6/6 PASS plus separate 300-frame pilot; each with 300/300 canonical frames, 600/600 Vulkan issue+wait+ACK, 300 out-of-order typed ACKs, and 600 Weston server `presented`, zero discarded.

G02 — 8/8 distinct compositor screenshots/run with primary and secondary signature, canonical source RGBA exact alpha and RGB deviation ≤3; independent, source-based oracle PASS. No stale/aliased composite claimed as proof.

G03 — At least five valid GPU samples per run, no observed temp ≥75°C, no observed board power ≥180W, no monitor errors, and no stale sensor window >3s within each bounded run.

G04 — All 300-frame run source-to-submit warm-frame p95 ≤100ms and p99 ≤200ms; max per-run wall time ≤60s. Every worker joins with no pending/ready abandoned IDs, no false ACK and no timeout promotion.

G05 — Bounded CPU stimulus actually active in exactly one balanced and one eco session, pinned to one CPU; fixed order / workload assignments recorded and hashed. All sandbox processes clean after each trial.

G06 — Two 120-frame loader-loss recoveries plus three fail-closed negative controls qualify. No actual device reset, no physical GPU loss.

G07 — All source code, exact binary, pre-run contract, measurement stream, compositor images, independent oracles, diagnosis and final verdict sealed SHA-256 under a clean local Git commit. No merge, push, deployment.

If any gate fails, record **HOLD** and the failing evidence without reinterpretation. A passing gate does not authorize production promotion.

## Nonclaims

Not guaranteed: statistical thermal design power, per-application watt-hour consumption, GPU energy efficiency, truly continuous multi-hour uptime, thermal equilibrium, cross-vendor, host hardware resets, 60 FPS, CP03 HYBRID-60, zero-copy or display photons.

