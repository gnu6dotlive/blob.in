# CP-JA7L — Matched-build throughput and host readback results

Date 2026-10-12. Parent `54c2daca0fb11e40a60554458c1a6b6808529a5d`.
**SCOPED PASS:** four identical-binary native E2Es, two applied Linux pipe sizes.
**OPEN:** unique causal bottleneck, robust population effect, CP03 HYBRID-60.

## Authenticated matched intervention

Four chronological 1,200-frame runs `A-B-B-A`, balanced profile,
16-ms requested interval. The F4 GPU engine, native wgpu viewer, broker
source and runner are byte-identical and preregistered by SHA256.
Linux `fcntl(F_GETPIPE_SZ)` independently confirmed **65,536 bytes**
for A and **1,048,576 bytes** for B. Canonical cache disabled in both
conditions; every actual F4 GPU output compared for full byte equality
with canonical reference. Private Weston 1536x1024 dual-swapchain compositor.

| Run | Pipe | Source submit rate | Median source pipe write | Median broker pipe read | GPU temp max | Card power max |
|---|---:|---:|---:|---:|---:|---:|
| A1 | 64 KiB | 31.1550 FPS | 29.166 ms | 0.954 ms | 52 C | 60.90 W |
| B1 | 1 MiB | 31.6217 FPS | 28.626 ms | 0.323 ms | 52 C | 59.18 W |
| B2 | 1 MiB | 31.2842 FPS | 28.876 ms | 0.323 ms | 52 C | 58.90 W |
| A2 | 64 KiB | 31.0292 FPS | 29.147 ms | 0.931 ms | 52 C | 58.55 W |

Pair effects B1−A1: **+0.4667 FPS**; B2−A2: **+0.2550 FPS**.
Median paired effect: **+0.36085 FPS (~1.16% of the A-run mean)**.
Both effects have the same positive sign, but four sequential trials
on a shared GPU do not confer statistical significance, randomization,
hardware isolation or a generally valid throughput gain.

## Host readback and end-to-end pipeline boundary

GPU producer `PersistentSession::render_next` inclusive host medians:
A1 2.640 ms, B1 2.661 ms, B2 2.642 ms, A2 2.715 ms.
GPU submission/readback completion wait host medians:
A1 1.2265 ms, B1 1.3275 ms, B2 1.2600 ms, A2 1.3305 ms.
The latter includes blocking device poll and is NOT measured GPU copy duration.
All nine GPU query pairs (six true kernels plus three copy commands)
were independently verified from 172,800 raw query bytes per run.
The separate RGBA/mask/fields GPU copies retain real hardware timestamps,
but PCIe bus time and OS host-map/copy time are not uniquely identified.

Broker full canonical comparison medians: 11.186, 11.300, 11.367,
11.208 ms (A1, B1, B2, A2); client integrity-copy medians:
18.577, 18.576, 18.649, 18.602 ms. These stages may overlap
and cannot be summed into a user-visible frame latency.

## Complete proof and guard

Each of four runs: 1,200 exact F4 GPU frames, 7,200 GPU compute
dispatches, 21,600 authentic GPU timestamps, 2,400 real Vulkan
typed present ACKs, 2,400 Weston server-side presented feedbacks
and 8 compositor screenshots matching original RGBA (RGB <=3, alpha exact).
Totals: 4,800 frames; 28,800 compute dispatches; 86,400 GPU queries;
9,600 typed Vulkan ACK; 9,600 Wayland presented; 32 screenshots.
NVIDIA sensors: 41,41,41,42 readings by run; temperatures <75 C and
card power <180 W; 100s wall limit never breached.
Shared-system GPU watts are NOT attributed to the experiment.
Twelve independent evidence falsifications were rejected. Legacy source
F4 Clippy -Dwarnings and 31/31 `blob-frame` tests PASS.

## Qualifying interpretation

A larger pipe produces a small local, direction-consistent improvement
in this bounded four-run crossover, as well as lower pipe-read time.
The 16ms requested interval nevertheless remains ~31 app submissions/s.
Source verification and client-copy work remain substantial.
Further experiments must isolate copies, frame scheduler behavior and
real scanout; they must use randomized/repeated matched runs before
declaring a stable intervention benefit. No photon timing, power per
frame, driver reset, cross-vendor evidence or CP03 HYBRID-60 PASS.

No merge, push, deployment, production promotion or modification of
resident Hyprland. Parent CP-JA7K qualification remains intact.
