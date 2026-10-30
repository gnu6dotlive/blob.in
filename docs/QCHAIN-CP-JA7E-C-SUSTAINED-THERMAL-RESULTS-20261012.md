# CP-JA7E-C — Scoped sustained Vulkan/Wayland runtime and monitored thermal envelope

Date: 2026-10-12. Parent commit: `f6a7ec14363e09ee80b77b1a1fde63123af727dc`.
Feature baseline: experimental `cpja7e-adaptive-scheduler`, no product default changed.
Worktree: `feat/qchain-sustained-thermal-20261012`.
Qualification: **SCOPED PASS** for bounded repeated 300-frame sessions and monitored whole-device GPU thermal/power limits. **NOT** production endurance, long-duration thermal equilibrium, GPU-specific power measurement, or CP03 HYBRID-60.

## Execution and failures disclosed

The first two pilot attempts were fail-closed before beginning GPU rendering: `pilot-balanced` had no copied viewer binary and `pilot-balanced-02` found an omitted runner CLI argument. They remain recorded under the evidence root, explicitly **excluded** from the qualified positives. The corrected, exactly identified binary was built from this worktree and passed `pilot-balanced-03` (300 canonical frames, 600 authentic Vulkan typed ACKs, independent RGB/alpha confirmation).

The six predeclared multi-cycle sessions ran separately with fresh Weston and native Vulkan device lifetimes in the fixed order: balanced, eco, eco with CPU stimulus, balanced with CPU stimulus, balanced, eco. Each completed 300 canonical frames and all 600 typed `vkWaitForPresentKHR` successes. Independent evidence authenticated eight compositor captures per run against distinct source variants and the two differently marked Wayland surfaces. They are consecutive *sessions*, not a continuous single device-resident multi-hour run.

| Run | Profile | CPU workload requested | Max GPU temperature | Max GPU board power | Monitor samples |
|---|---|---|---:|---:|---:|
| pilot-balanced-03 | balanced | none | 53°C | 74.72 W | 13 |
| c01-balanced | balanced | none | 52°C | 59.28 W | 13 |
| c02-eco | eco | none | 52°C | 57.08 W | 13 |
| c03-eco-cpu | eco | 45% one core | 52°C | 57.00 W | 14 |
| c04-balanced-cpu | balanced | 45% one core | 52°C | 57.79 W | 14 |
| c05-balanced | balanced | none | 54°C | 73.61 W | 13 |
| c06-eco | eco | none | 54°C | 70.36 W | 13 |
| pressure-proof-eco | eco | live CPU18 witness | 53°C | 60.39 W | 14 |
| pressure-proof-balanced | balanced | live CPU18 witness | 53°C | 65.76 W | 14 |

All nine qualified 300-frame executions complied with the predeclared GPU stop limits (sampled temperature <75°C, board power <180W), baseline <65°C and sample staleness ≤3s. Session lengths were about 11–13 seconds, with **81–82 seconds of the seven pilot+core session durations in total**; two additional CPU-proof sessions lasted ~12 seconds each. These finite durations are **not** thermal equilibrium or long-running uptime.

GPU `nvidia-smi` sensor readings are host-wide and include unrelated user/compositor/GPU activity. Observed board power is **not attributable to the application**, and no energy-per-frame, thermal design power or electricity saving is claimed. The runner observed only discrete approximately 1s samples: excursions between samples cannot be excluded by these results.

## CPU stimulus evidence and qualification honesty

The c03/c04 supervisors requested one `stress-ng --cpu 1 --cpu-load 45` worker on CPU18 while all tested child processes were pinned to CPUs18–19. The initial campaign's safety receipts record requests and guarded completion, but **do not independently record the stress process's active CPU ticks in those original two sessions**.

To distinguish intent from observation, `pressure-proof-eco` and `pressure-proof-balanced` ran in separately attributed supplemental trials, with a direct independent `/proc/PID/stat` and `sched_getaffinity` sampler active from launch. The CPU18 workers accumulated respectively **522 and 540 CPU ticks** between sampled measurements, with both 300-frame graphical/Vulkan oracles PASS. This establishes that bounded real CPU contention can coexist with canonical F4 rendering in those supplemental trials; it does **not** prove an exact 45% average utilization over the planned original sessions or general workload diversity.

No unbounded `stress-ng` resource stress, global CPU affinity modifications, fan or GPU power cap controls were applied. The independent observer launched late for the original campaign and its empty samples are preserved as diagnostic rather than falsely promoted to stress evidence.

## Recovery, source authority and adversarial controls

Two additional 120-frame loader-injected device-loss runs, one balanced and one eco, each survived a **synthetic** Vulkan Loader `VK_ERROR_DEVICE_LOST` at primary present ID41. Both rebuilt the logical device and two Wayland swapchains, completed 120 frames, accepted 238 of 240 issued Vulkan IDs and left the two invalidated old secondary IDs permanently unacknowledged. Their separate CP-JA7D-B independent source/pixel/Vulkan/Wayland oracles passed. No NVIDIA hardware-originated loss or GPU reset was performed.

Three private live negative executions closed fail-closed: no authorized recovery, second injected loss, and false expected-loss claim. All terminated nonzero with no positive receipt. Twenty out of twenty adversarial evidence modifications were rejected, covering thermal ceilings and sensor staleness, tampered summary, timestamp inversion, false CPU activity, false profile/affinity, failed viewer exit, missing Vulkan wait witness, forged ACK, altered source digest, missing Wayland feedback and pixel corruption.

Source validation independently recalculates **all nine original image-and-frame oracles** and reconciles original JSONL nvidia-smi sample streams with the summary receipts, without trusting producer PASS. Original sources and screenshots remain immutable; falsifications operate on temporary copies.

## Verifiable scope gates

| Gate | Verdict |
|---|---|
| S1 300-frame pilot, 600 real native Vulkan wait ACKs | PASS |
| S2 six isolated 300-frame cycles, canonical source/independent pixel oracle | PASS |
| S3 bounded stimulus requested on two planned cycles | PASS — execution request proven |
| S3 exact live CPU activity on original two planned cycles | NOT DIRECTLY INSTRUMENTED |
| Supplemental direct CPU18 process activity with two F4 E2Es | PASS |
| S4 two independent device rebuild/recovery runs, three fail-closed negatives | PASS |
| S5 whole-device thermal/power telemetry, guarded limits, source/pixel reconciliation | PASS |
| G01–G04/G06/G07 in contract for the scoped finite workload | PASS |
| Continuous multi-hour endurance and equilibrium temperature | NOT QUALIFIED |
| Physical GPU reset, true NVIDIA ICD device loss, AMD/Intel and second OS | NOT QUALIFIED |
| Zero-copy, sustained 60 FPS, CP03 HYBRID-60, photons | NOT QUALIFIED |
| Process-specific watts/frame, energy savings, thermal effects isolated from resident load | NOT QUALIFIED |

The scheduler remains an opt-in experimental feature. The production default stays `balanced`; the experiment does not authorize promotion, merge, push, deployment or public performance claims.

**Recommended next CP-JA7F:** bounded sustained production-style workload with continuous device residency (20–30 minutes), thermal settling, per-process CPU/GPU attribution or explicit lack thereof, measurable stop/recovery windows, and physical GPU cross-vendor qualification when hardware is available. CP03 HYBRID-60 remains a separate performance gate.

