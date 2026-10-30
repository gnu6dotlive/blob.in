# QCHAIN CP-E — Bounded per-frame GPU-resident compute qualification

**Date:** 2026-10-10. **Authority:** QCHAIN-GPU-EXECUTION-01.
**Result:** `QCHAIN_CPE_ONE_DEVICE_RESIDENT_GRAPH_40_FRAMES_EXACT_GPU_PARITY_PASS`.

The new branch `feat/blobin-qchain-gpu-resident-20261010`, based on
`c270ca32790597049b59ccba77d1694fa4a439f7`, adds a parallel F4 GPU graph.
No source CPU witness, production runtime, or global Wayland setting was changed.

## Engine

F2 signed-mask WGSL, F3 RGBA/analytics WGSL and four F4 passes share
**one wgpu Device and one command encoder per frame**; one queue submission
and no GPU→CPU→GPU transfers between the six dispatches.
Three readbacks after the last dispatch provide output and oracle diagnostics.

## Recorded evidence

Private location: `/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpe-resident-01/`.

| Qualification | Outcome |
|---|---|
| Five scenes / four materials / two frames | 40/40 GPU frames |
| GPU RGBA vs CP-D GPU | **exact 40/40**; zero differing bytes |
| GPU F2 signed masks vs original CPU | exact 5/5 |
| GPU F3 readback vs previous independent GPU field oracle | 5/5 in lab tolerance |
| F2 analytic mask vs F3 analytic mask | 5/5 exact |
| Per-frame GPU operations | 6 dispatches, 1 submit, zero intermediate host transfers |
| Final diagnostic readbacks | 3 |
| Rust F4 tests / Clippy | PASS |
| Forced unavailable Vulkan adapter | expected nonzero refusal, no fallback |
| Independent oracle mutations | 5 expected rejects + 1 positive = 6/6 PASS |

The final independent verifier is `scripts/qchain_cpe_oracle.py`, with
`scripts/test_qchain_cpe_oracle.py` for adversarial mutations.
The oracle uses the CPU immutable reference, CP-D GPU images, CP-C F3
numeric readbacks and independent binary/range checks.

**Evidence SHA:** `166e323dc8b62c7c948a0740ebf5472dc542820cf10870e1b99dec23c6b0e69e`
for `independent-oracle.json`.

## Methodological boundary

Exact equality is to the prior **GPU** output, not to the CPU bytes.
The CPU/GPU numeric parity remains bounded. A single device per *frame*
does not mean persistent resources across frames. The dispatch/submit
counts are validated against the authored code path, not driver tracing.
No GPU-source Wayland presentation, protocol G07, full adversarial G06,
CP03 HYBRID-60 or public deployment is claimed.

**Next:** implement a bounded persistent session retaining device/pipelines
between frames, then qualify opt-in GPU provenance transport and native Wayland
GPU-source capture. Neither is accomplished in this commit.
