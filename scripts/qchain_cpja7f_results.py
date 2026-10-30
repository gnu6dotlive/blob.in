#!/usr/bin/env python3
"""Write factual CP-JA7F results only after the independent oracle admits the run."""
import argparse,json
from pathlib import Path
from qchain_cpja7f_validate import validate,NAME
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",required=True,type=Path)
    p.add_argument("--evidence",required=True,type=Path)
    a=p.parse_args()
    repo=a.repo.resolve()
    e=a.evidence.resolve()
    dest=repo/"docs/QCHAIN-CP-JA7F-RESULTS-20261012.md"
    if dest.exists():raise RuntimeError("RESULTS_REFUSE_OVERWRITE")
    result=validate(repo,e)
    thermal=result["sensor"]
    proc=result["process"]
    actual=result["native"]
    report=result["producer"]
    secs=actual["residency_observed_span_us"]/1e6
    p95=actual["preload_dwell_p95_us"]/1000
    stress=proc["stress_cpu18"]
    stress_records=", ".join(
        f"PID {pid}: {v['tick_increase']} CPU ticks over {v['span_s']}s"
        for pid,v in stress.items())
    content=f"""# CP-JA7F — Continuous low-duty Vulkan residency: independent qualification

Date: 2026-10-12. Hardware: physical RTX 3070 on resident Hyprland,
but all application tests use an isolated Weston 15 headless GL compositor.
Parent: `d2085e7be6a98e646b653c2493e8ce23b313f68c`.

**Decision: SCOPED PASS — 20-minute continuous two-swapchain Vulkan residency.**
No continuous high-load, temperature equilibrium, watt-hours/frame or
production release has been qualified. The original contract is
`docs/QCHAIN-CP-JA7F-RESIDENT-CONTRACT-20261012.md`.
Canonical evidence root:
`/mnt/workbench/evidence/runs/qchain-cpja7f-20261012-01`.

## Single device and native WSI authority

The single bounded `resident-20min-02` viewer displayed **300 canonical F4
frames** on two independently visible 512×384 Wayland swapchains. The source
frame 0→299 submission clock span was **{secs:.2f}s** ({secs/60:.2f}min),
comprising **{actual['interframe_gaps_3_to_6_seconds']} of 299**
intervals within 3–6 seconds; the **longest consecutive compliant streak**
was **{actual['longest_consecutive_cadence_streak']} intervals**.
The stipulated minimum span 1,200s and 270 consecutive compliant
intervals were independently verified.

Real Vulkan: 600 present ID issues, 600 true `vkWaitForPresentKHR` success
observations, 600 typed ACKs, 300 deliberately out-of-order delivery
ACKs and 0 orphaned acknowledgments. There were
**{actual['wayland_server_presented']}** compositor server `presented`
feedbacks, zero `discarded`, and eight compositor screenshot pairs
matching original F4 source RGBA (RGB <=3/channel, alpha exact).

The viewer reported exactly one
`CPJA7F_RESIDENT_DEVICE_CREATED epoch=0` and one normal
`CPJA7F_RESIDENCY_COMPLETE`. No callback for device loss
or logical-device rebuild was observed in the complete application logs.
The supplementary OS process watcher retained viewer PID
**{proc['viewer_pid']}** and Weston PID **{proc['weston_pid']}**
for **{proc['sampled_residency_seconds']:.2f}s** over
**{proc['sampling_count']}** valid sampled observations.

**Witness scope caveat:** the OS PID watcher was started after the
viewer had already begun; it did not cover the initial minutes.
The complete source/WSI/application traces, single viewer launched
by the runner and watcher observations jointly support continuous
device residency, but the watcher by itself does **not** cover the
entire process lifetime.

## Whole-board thermal envelope, not attributable application energy

The independent sensor oracle reconciled
**{thermal['samples']} samples** across
**{thermal['span_s']:.2f}s**, with no interval longer than
**{thermal['max_sampling_gap_s']:.2f}s** between records.

| Metric | Observed |
|---|---:|
| Whole-device GPU temperature | {thermal['temp_min_c']:.0f}–{thermal['temp_max_c']:.0f} °C |
| Whole-board instantaneous power | {thermal['power_min_w']:.2f}–{thermal['power_max_w']:.2f} W |
| Peak GPU utilization sampled | {thermal['peak_gpu_util_pct']:.0f}% |
| Median GPU temperature, first 300s | {thermal['first_300s_temperature_median_c']:.1f} °C |
| Median GPU temperature, final 300s | {thermal['last_300s_temperature_median_c']:.1f} °C |

The guard had sampled abort thresholds of >=75°C or >=180W,
a baseline refusal at >=65°C, a sensor-staleness limit of 3s
and a strict 1,500s wall-clock timeout. The resident desktop
and its GPU work were **not** suspended. Temperatures and board
power combine experimental and non-experimental loads; these
records cannot establish process-specific power draw or
thermal equilibrium under saturated GPU workload. Sub-sample
peaks cannot be excluded.

## CPU workload, proof and negative controls

One 45% target stress-ng worker was confined to CPU18 for a
bounded middle window, while the experiment remained pinned
to CPUs18–19. The live independent /proc witness observed
{stress_records}. These are actual CPU-time growth measurements,
not simply an invocation receipt; an exact instantaneous
45% utilization was **not** continuously asserted.

The first unscored 100ms pilot with 300 frames failed an
inherited CP-JA7E-C preload-latency gate, even though it
presented frames correctly. The next unscored 100ms pilot
`pilot-residency-100ms-02` passed with the corrected residence
gate, but does not meet the 20-minute duration requirement.
A separate full-duration preflight was rejected before viewer
startup because the `bench/` directory was missing.
These initial failed/rejected attempts remain in evidence
and are **not** promoted to qualified long runs.

The source-to-submit p95 value ({p95:.2f}ms) includes
**intentional source-buffer preloading dwell**, not just GPU
render/present latency. This test does not make a 60FPS claim.

After the long run, the unchanged, hashed viewer was subjected
to three synthetic-Vulkan-loss fail-closed controls:
no recovery authorization, double fault and expected fault
not actually injected. Their independent negative verdicts
record nonzero viewer exit and zero false success receipts.
A separate adversarial suite rejected **26/26** falsified
thermal, process, Vulkan, Wayland, source and image witnesses.

Clippy (`-Dwarnings`), the inherited CP-JA7D-B
feature build and 31 `blob-frame` Rust tests passed.

## Gates and excluded claims

| Scope | Decision |
|---|---|
| >=1,200s continuous low-duty dual-swapchain residence | PASS |
| 270 consecutive 3–6s presentation intervals | PASS |
| Genuine 600 Vulkan WSI typed ACKs, independent source hashes | PASS |
| Eight differentiated, byte-checked compositor captures | PASS |
| At least 1,150 timely, safe whole-board GPU samples | PASS |
| CPU18 stress activity observed and capped | PASS |
| Full initial-to-final OS PID process watcher | PARTIAL; started late |
| Independent negative controls and adversarial tests | PASS |
| Thermal equilibrium under GPU saturation | NOT TESTED |
| 60FPS and CP03 HYBRID-60 | OPEN |
| Power attributable to blob.in, zero-copy | NOT TESTED |
| Real NVIDIA driver-emitted device loss, vendor parity | NOT TESTED |

No Hyprland restart, physical GPU reset, global Vulkan-layer
installation, merge, push, deployment or production default change.
**NEXT**: qualify continuous *active* GPU workload with a
separately predeclared thermal/energy budget, then CP03 HYBRID-60.
"""
    dest.write_text(content)
    print("CPJA7F_FACTUAL_RESULTS_WRITTEN",dest)
if __name__=="__main__":main()
