# CP-I02 — Continuous GPU Compute → IPC → Native Wayland Presentation

**Date:** 2026-10-10. **Parent:** CP-I01 `e7ea791eb165a8d8ccb30619b45426be7fc0926d`.
**Branch:** `feat/qchain-continuous-wayland-20261010`.

## Goal and source contract

Replace preloading five GPU outputs into the viewer with **live** generation of
120 frames within one CP-F `PersistentSession` on the RTX 3070, backpressured
and transferred by new private `QCHAIN-GPU-STREAM-v1` IPC, then consumed
individually by native wgpu/Wayland.

The GPU producer `tools/qchain_cpi02_gpu_live.rs` was copied only into an
isolated Git archive of the CP-F engine at commit `5132cf5` and compiled
offline. It computes F2/F3/F4 on Vulkan WGSL, with six dispatches per frame.
The engine does not read PNGs or replay pre-rendered RGBA as output.

The Python source `scripts/qchain_cpi02_stream_source.py` reads one bounded
24-byte binary header plus 786,432 RGBA bytes from a live GPU process,
independently compares each buffer against the CP-F reference, and responds to
a viewer-requested seq only. This validation reads reference files but **never
uses those files as the transmitted pixel source**. It sends one exact-size
memfd sealed against write/resize on a private Unix SEQPACKET socket.

The Rust consumer `qchain_gpu_stream_viewer` independently validates the
seq, scene SHA, semantic digest, GPU source identity, fixed format,
exact memfd length, required seals and pixel SHA before upload to wgpu.
A bounded `sync_channel(1)` applies backpressure; the viewer retains at most
one current GPU frame instead of 120 preloaded buffers. The source emits
five semantic scene epochs, then eight deterministic material/heat variants
on the final scene (12 frames per variant); source code contract and oracle
must not conflate the five scene identities with three baseline pixel images.

## Execution evidence

Two isolated Weston 15 headless GL sessions, using the NVIDIA RTX 3070 and
opt-in `--debug` strictly on their private sockets:

| Gate | Run 01 | Run 02 |
|---|---:|---:|
| GPU computation and sealed IPC receipts | 120/120 | 120/120 |
| wgpu surface-present calls | 120/120 | 120/120 |
| Compositor screenshots of changing variants | 8/8 | 8/8 |
| Pixels exact after compositor-declared Y flip | 1,572,864/1,572,864 | same |
| Submission-interval median | 33.073 ms | 33.085 ms |
| Submission-interval P95 | 33.567 ms | 33.697 ms |
| Submission-interval P99 | 34.050 ms | 34.787 ms |
| Maximum interval | 44.844 ms | 36.070 ms |
| Receive-to-submit median | 48.497 ms | 48.547 ms |

The sampling schedule targets the middle of each twelve-frame material block.
The eight PNG captures per run were recomputed by an independent oracle
against the CP-F original bytes after the compositor's documented Y flip,
with **zero color tolerance or pixel masking**.

## Refus and distinctions

The independent oracle rejects: source timeline seq substitution, changed
semantic scene identity, modified central screenshot pixel and missing Weston
Y-flip declaration. One separately executed malformed IPC request (seq=999
instead of 0) was rejected fail-closed without a false completion receipt.
Existing CPU/GPU baseline tests remain unchanged.

The observed ~33 ms interval is a **user-space wgpu submit cadence** driven
by the viewer's 33 ms scheduler. There is no per-frame `wp_presentation`
feedback or independent compositor refresh event for all 120 submissions.
Eight compositor screenshots per run prove *samples* were displayed, not that
all 120 submissions were composited or seen as physical photons.
Consequently no sustained 30 FPS, 60 FPS, CP03 HYBRID-60, VRR or p99
display-latency claim is qualified. There is still GPU→host readback,
memfd and GPU reupload; this is **not** zero-copy. CPU RSS/VRAM and
cross-vendor observations are not part of this checkpoint.

The tests are bounded to 120 frames and approximately 4–5 seconds each,
not an unattended production soak. The isolated Weston debugging capability
was never enabled on the user's Hyprland session. Neither background
service deployment, push, merge nor runtime promotion is authorized.

## Receipts and promotion boundary

Private root:
`/mnt/workbench/evidence/runs/qchain-cpi02-20261010-01/`.

Evidence: `weston/run-01` and `weston/run-02` (captures, logs, GPU timeline); `oracle/run-01.json` and `oracle/run-02.json` (independent checks); `oracle/negative-tests.log` and `protocol/bad-seq/verdict.json` (negative controls).

**Bounded verdict:** `QCHAIN_CPI02_120_GPU_STREAM_8_WESTON_SAMPLE_EXACT_PASS`.

**Next:** CP-J should measure Wayland presentation feedback and compositor callbacks. CP03 HYBRID-60 and CP-L N01–N17 remain OPEN.
