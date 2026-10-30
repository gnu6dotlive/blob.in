# QCHAIN-FRAME-03 — GPU compute parity qualification contract

**Date:** 2026-10-10 · **Status:** PROPOSED / NOT EXECUTED · **Dependency:** QCHAIN-FRAME-02 corner-masked compositor E2E PASS.

## Objective and boundary
Replace the CPU-sourced F4 buffers with genuinely GPU-computed F2→F3→F4 output, preserving the exact five bounded canonical scenes (512×384) and checking against the immutable CPU witness. A Vulkan texture upload of CPU bytes is **not** GPU compute.
Do not modify the production BLOB-FRAME-v1 ABI, resident render daemon, ordinary showcase UI, compositor configuration, or unrelated services. Keep original screenshot captures private.

## Gates
1. **G01 provenance:** freeze source commit, GPU identity/driver, scene canonical JSON and SHA256, shader/kernel revisions and fixture hashes; independent manifest.
2. **G02 compute:** produce F3 intermediate and F4 RGBA8 on device; attest dispatch completion and GPU→CPU readback, excluding CPU fallback. Separately identify CUDA versus Vulkan if only one is implemented.
3. **G03 oracle:** compare topology IDs, F3 numerical channels and all F4 pixels to the CPU oracle; report exact counts, per-channel maximum/mean error, threshold rationale and worst-coordinate evidence. Never silently redefine exact parity as tolerance.
4. **G04 adversarial:** five canonical scenes plus negative tests for substituted scene identity, stale epoch/revision, wrong digest, altered pixels, mismatched dimensions and CPU-fallback masquerading as GPU.
5. **G05 transport:** transmit only validated GPU-produced F4 through opt-in QCHAIN-FRAME-v1 or a separately versioned channel; same-UID and sealed memfd identity retained.
6. **G06 Wayland:** all five GPU-source frames submitted and compositor-captured; independent screenshot comparison must disclose Hyprland's 18px corner exclusion, any color transform, and each stage's capture provenance.
7. **G07 reproducibility:** fresh source build, independent replay, nonzero exit on any gate failure, review of warnings, logs and artifact SHA256; branch-only evidence.

## Acceptance semantics
- `QCHAIN_GPU_COMPUTE_EXACT_PARITY_PASS` requires zero unexpected deviations against the explicit CPU oracle on all required semantic outputs and pixels.
- `QCHAIN_GPU_COMPUTE_BOUNDED_TOLERANCE_PASS` is a distinct, non-equivalent verdict requiring predeclared channel-specific error budgets; never call it exact.
- `QCHAIN_GPU_WAYLAND_E2E_PASS_CORNER_MASKED` additionally requires G05–G07 and 5/5 captured frames. Presentation submissions alone are insufficient.
- Any missing gate is `NOT_RUN`, not `PASS`. CP03 HYBRID-60, cross-vendor, photodiode/physical photons and P06 photorealism remain out of scope and OPEN.

## Existing baseline
The independently rerun CPU-source compositor oracle passed 5/5 stages with **195,312 exact non-corner pixels per stage** and no mismatch outside the fixed four 18×18 squares. Verification artefact: `/mnt/workbench/evidence/runs/qchain-wayland-20261010-b/compositor-reverification-20261010.json`.
