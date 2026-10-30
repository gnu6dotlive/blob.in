# CP-JA7F — Continuous native Vulkan residency and bounded thermal observation

Date: 2026-10-12, Montreal; parent commit `d2085e7be6a98e646b653c2493e8ce23b313f68c`.
Branch: `feat/qchain-continuous-residency-20261012`.
Gate preregistered **before** full-duration execution. No PASS until exact source, native WSI and thermal traces pass independent qualification.

## Exact claim
One viewer PID, one `wgpu::Device` lifetime, two Wayland swapchains of 512x384, and the same private Weston compositor must stay alive across all 300 actual GPU-source frames, spaced by 4,100 milliseconds. The intended span is 299 intervals, about 1,225.9 seconds (20 min 25.9 sec). This is **continuous Vulkan residency with a low-duty-cycle periodic rendering workload**, not continuous 60FPS or GPU saturation.

The opt-in Cargo feature `cpja7f-resident` implements a configurable presentation interval without altering the default feature's 33ms cadence. `CPJA7F_FRAME_INTERVAL_MS=4100`, 300-frame source, profile `balanced`, and 400ms initial idle probe are fixed for the main run. Bounded 100ms pilot precedes the main run and does not count as 20-minute proof.

## Hardware control and fail-closed monitors
Private Weston 15 headless GL on NVIDIA RTX 3070; resident Hyprland untouched. Single isolated viewer with VK_KHR_present_id + present_wait typed ACK, collector workers on one logical device. A private guest experiment is pinned to Linux logical CPUs 18–19. Monitoring never changes hardware settings or installs a global Vulkan layer.

Before start: `nvidia-smi` must report exactly one valid GPU row, temperature <65°C, board power <180W. During the run, sample sensor temperature, board power, utilization, VRAM and fan once per second. Abort and terminate the entire isolated process group if any observed temperature >=75°C, board power >=180W, GPU sample gap >3 seconds, command failure or elapsed wall time >=1,500 seconds. Sampling only bounds **observed** values, not peaks occurring between observations. Resident GPU and user applications remain in the board-level readings; these are not application-attributable measurements.

At wall-clock time +300 seconds, spawn **one** bounded `stress-ng --cpu 1 --cpu-load 45` worker pinned to CPU18 for at most 120 seconds, then terminate and collect CPU tick and affinity witnesses. No system-wide CPU or GPU stress. An absent or unverified stimulus is reported as a separate HOLD, not silently promoted.

## Contractual gates
- R01: exactly one live viewer PID throughout 300 frames, one Weston lifetime, zero device-loss callback/rebuild, and the original two Wayland resource identities (300 feedback requests each); identities captured from raw process and protocol evidence.
- R02: 300 source sequences 0..299 with SHA-256 equality to canonical F4 bytes and semantic stage receipts. Viewer emits 300 frame-submitted events with timestamps over a continuous interval >=1,200s. At least 270 consecutive inter-frame deltas 3.0–6.0s; strictly increasing source timestamp. No duplicate or omitted source ID.
- R03: exactly 600 native `vkQueuePresentKHR` successful issued IDs and 600 actual `vkWaitForPresentKHR` typed successes, 300 accepted out-of-order acknowledgments, bound outstanding <=2 per swapchain, and 600 Weston server presented events, zero discarded. Zero falsely credited IDs.
- R04: eight compositor screenshots on distributed source targets [9,45,81,117,153,189,225,261], compared against original GPU RGBA, RGB per-channel <=3 and exact alpha, with two distinct windows and no alias.
- R05: monotonic sensor samples covering entire run with >=1,150 valid records and no gap >3s; maximum observed temp <75°C and board power <180W; no sensor errors. Report first/last 300-second temperature windows separately; **do not** claim thermal steady state from insufficient evidence.
- R06: CPU18 stress applied for a 120s bounded middle window, with process PID, affinity, increasing /proc CPU ticks; **otherwise stress gate HOLD**.
- R07: final viewer/source clean exit, no resident experimental child process, workers joined with no unacknowledged present IDs; fail-closed scenarios rechecked on unchanged binary after resident run (no recovery, double-loss, no injected loss).
- R08: independent oracle recomputes full source hash/pixel/Vulkan/Wayland truth without trusting producer receipts; adversarial falsifications are rejected; immutable SHA-256 report bound to local clean Git commit.

## Hard boundaries
No Vulkan physical device reset, no real ICD-originated loss, no new power/fan/clock settings, no Hyprland restart, no merge/push/deploy. A successful 20-minute low-duty-cycle residence is **not** proof of sustained 60FPS, CP03 HYBRID-60, thermal equilibrium under GPU load, GPU-only watts/frame, continuous multi-hour operation, AMD/Intel parity or production readiness. Absence of sufficient evidence yields HOLD, not SCOPED PASS.

