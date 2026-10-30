#!/usr/bin/env python3
"""CP-JA7G factual results: create only after independent positive/negative gates."""
import argparse,json
from pathlib import Path
from qchain_cpja7g_validate import validate

def need(ok,why):
    if not ok:raise RuntimeError(why)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",required=True,type=Path)
    ap.add_argument("--evidence",required=True,type=Path)
    a=ap.parse_args()
    w=a.repo.resolve()
    e=a.evidence.resolve()
    target=w/"docs/QCHAIN-CP-JA7G-ACTIVE-GPU-RESULTS-20261012.md"
    need(not target.exists(),"RESULTS_REFUSE_OVERWRITE")
    values=validate(e,w)
    need(len(values)==2,"TWO_INDEPENDENT_RUNS_REQUIRED")
    negatives=[]
    for name,frames,faults in (
        ("no-recovery",40,1),("double-loss",44,2),
        ("no-injection",120,0)):
        proof=json.loads((e/"negative"/name/"negative-verdict.json").read_text())
        need(proof["mode"]==name and proof["submitted_frames"]==frames
             and proof["injections"]==faults and proof["viewer_exit"]!=0
             and not proof["success_receipt"]
             and proof["verdict"].endswith("_FAIL_CLOSED_PASS"),
             "NEGATIVE_FAIL_CLOSED_MISSING_"+name)
        negatives.append(name)
    need("CPJA7G_ADVERSARIAL_17_OF_17_PASS" in
         (e/"oracle/adversarial.log").read_text(),
         "ADVERSARIAL_CONTROLS_NOT_ALL_REJECTED")
    left,right=values
    def row(d):
        return (
          f"| {d['profile']} | {d['frame_span_seconds']:.3f} s | "
          f"{d['effective_source_present_rate_fps']:.3f} | "
          f"{d['interval_p99_us']/1000:.2f} ms | "
          f"{d['gpu_util_median_pct']:.0f}% | "
          f"{d['gpu_util_max_pct']:.0f}% | "
          f"{d['temp_max_c']:.0f}°C | "
          f"{d['whole_board_power_max_w']:.2f} W | "
          f"{d['sensor_samples']} |"
        )
    s=f"""# CP-JA7G — Controlled sustained active Vulkan compute and WSI

Date: 2026-10-12. Parent: 1bde593ab0ffcfa4cd696d79a2d644c08835a973.
Branch: feat/qchain-active-gpu-soak-20261012.
Decision: **SCOPED PASS** for two >120s GPU-compute-active E2E sessions.
Baseline: physical NVIDIA RTX 3070, private Weston 15 headless GL,
resident Hyprland and user GPU activity left unchanged.

## Actual engine and identity
The qualifying source was freshly computed by the bounded Rust
`PersistentSession` Vulkan/WGSL GPU producer
`tools/qchain_cpja7g_active_gpu_live.rs`. It asserts **six compute
dispatches**, one GPU submission, zero intermediate host transfers, an
RTX 3070 adapter and source semantic identity for *each* frame.
Final source stats attest one compute device, three pipelines, five
reusable GPU buffers and all 3,600 frames. The original CP-I02
GPU binary is unchanged. The experimental engine was built via
`rustc` against three pre-existing local Cargo rlibs; their paths
and hashes are pinned in the evidence. This is **not** a claim of
clean-room rebuild from independently restored source dependencies.

Each genuine compute output passed canonical byte-for-byte F4 source
checks inside the broker before being transmitted via a sealed memfd
to a wgpu Vulkan viewer. Each of the two native Wayland swapchains
submits an independently identified Vulkan present for each frame.
Two persistent swapchains per run, no device-loss or device rebuild.

## Observations over the two independent active periods
| Profile | Frame time span | Submit FPS | Frame gap p99 | GPU util median | GPU util peak | Board temperature max | Board power max | Sensor samples |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{row(left)}
{row(right)}

Each run: 3,600 source frames; 21,600 compute dispatches; 3,600 compute
queue submissions; 7,200 native Vulkan present/wait-success typed ACKs;
3,600 intentionally reordered ACKs; 7,200 compositor server-side
`presented` feedbacks; zero `discarded`; eight privately captured,
compositor-visible screenshots conforming to original F4 RGBA
(RGB channel difference <=3; alpha exact). Both primary and secondary
windows have their own Wayland resources.

Combined across both runs: 7,200 fresh GPU renders, **43,200**
compute dispatches, 7,200 compute queue submissions, **14,400**
Vulkan WSI typed ACKs, 7,200 deliberately reordered ACKs, 14,400
Weston presentation feedbacks, and 16 screenshot witnesses.

Predeclared cadence: source-to-present submissions span >=95s/run,
>=90% consecutive presentation intervals in 20–100ms, and p99
interval <=250ms. Both passed under their original thresholds.
The effective 29 FPS is an *application submission-rate witness*:
not proof of physical photons, display refresh, or 60 FPS.

## GPU thermal and utilization caveats
The GPU was shared with the resident desktop. `nvidia-smi` measured
whole-device power, temperature, GPU utilization, VRAM and fan at
about 1s intervals. Both runs remained below sampled stop thresholds
75°C and 180W; no sensor gap exceeded 3s, no sensor error, no GPU
reset, no global Vulkan layer. GPU utilization was **not permanently
saturated**, and recorded board watts cannot be attributed to the
test alone. We do not claim thermally saturated steady-state operation,
application-only watts/frame, performance per watt or precise
photons-on-screen FPS.

## Fail-closed controls, negative provenance and scope
The first `active-balanced-3600` preflight was rejected before the
viewer could begin rendering: the guard referenced the build root
instead of the isolated evidence binary directory. Its nonpositive
safety receipt remains in the evidence. A corrected **separately named**
`active-balanced-3600-02` qualified using the exact same anchored
viewer/engine binaries and unmodified preregistered contract; no
old artifact was overwritten or reclassified.

Three additional loader-injected synthetic loss controls on the
exact viewer binary all terminated nonzero without false receipts:
no recovery authorization, double loss, and false required loss.
No actual NVIDIA ICD-emitted loss was induced. Seventeen independent
mutations of thermal, Vulkan, source, compute, Wayland and pixel
evidence were rejected. Clippy `-Dwarnings` for CP-JA7G, legacy
CP-JA7F checks and 31 `blob-frame` tests passed.

## Final qualifications
- **PASS scoped:** GPU compute was fresh and real, two independent
  3,600-frame sessions, correct native present-wait ACKs, two
  visible surfaces, source/image hashes, bounded temperature/power
  samples, independent oracle, fail-closed and adversarial controls.
- **OPEN:** long-term 30+ min active compute, GPU saturation,
  thermal equilibrium, robust randomized trials, vendor interoperability,
  hardware-originated driver device loss, zero-copy, photons,
  60 FPS and **CP03 HYBRID-60**.
- **NOT AUTHORIZED:** merge, push, release, production scheduler
  promotion, GPU driver reset or resident compositor modification.

Recommended next: CP-JA7H / CP03 hybrid-60 preparation should
explicitly separate compute, upload, dispatch, wait, compositor and
user-visible frame pacing before any 60-FPS success assertion.
"""
    target.write_text(s)
    print("CPJA7G_FACTUAL_RESULTS_CREATED",target)
if __name__=="__main__":main()
