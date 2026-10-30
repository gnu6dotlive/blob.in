# BLOB-AC-03 — Weston compositor input + GPU client pixels
2026-10-12 · src: scripts/blob_ac03_weston_test_input.c; scripts/blob_ac03_isolated_e2e.py; crates/showcase/src/bin/blobin_ui_ac02_wayland.rs
Contract: ../contracts/BLOB-AC-03-COMPOSITOR-GESTURE-E2E-20261012.md
Proof: ../evidence/runs/blob-ac03-20261012/qualification.json

## Verified mechanism
The original lab module creates a dedicated Weston 15 pointer seat in a private compositor namespace and executes:
1. pointer enters left card at (135,145)
2. primary button down (Begin)
3. pointer dx=55 (Preview)
4. pointer dx=140 (Preview)
5. button up (Commit; one UI-G02 reorder)
There can be an extra initial enter/motion callback; the independent oracle demands the exact six native ingress records and matching InputRouter receipts.
UI-G03 layout recomputes after one document revision increment. The transient preview does not mutate the tree.

## Exact pixel evidence
An explicit opt-in flag enables COPY_SRC on the **actual wgpu SurfaceTexture** in the AC-02 fixture. The app copies rendered pixels before queue.present into staging, maps them and writes before/preview/after raw buffers. The oracle converts those buffers into private PNGs and demands:
- baseline: blue left / orange right
- preview: a visibly changed left sample; no completed reorder
- after commit: orange left / blue right
- GPU readback timestamps occur at UI revision 1 before, 1 preview, 2 after.
- all traces, output images and module source are hashed and attributable.
No application beyond this private fixture was captured.

## Evidentiary strength
TRUE: Weston compositor delivers pointer motions/buttons; winit callback accepts them; G04 InputRouter receipts and AC01/02 coordinator produce one semantic reorder; GPU client swapchain buffer changes with document state.
NOT TRUE / unqualified: physical HID, compositor frame-presentation acknowledgement, user desktop capture, frame-time percentile performance, CP03 HYBRID-60, production UX and other compositeurs.
A previous headless Weston screenshooter output was pure black; it has not been reclassified as visual proof. The new readback is GPU/client buffer evidence prior to presentation, NOT a compositor framebuffer screenshot.

## Reproduce
From local private main:
python3 scripts/blob_ac03_verify.py

The verifier executes rustfmt on the owned native source, strict Clippy, AC02 and AC01 suites, workspace library regressions, builds the native app (offline cargo) and a Weston 15 test module (gcc/pkg-config), starts unshare -Urn, runs a unique private Weston socket, saves JSONL event and compositor logs, maps client GPU swapchain pixels, then writes JSON qualification evidence.
No GitHub Actions. A missing Weston ABI/namespace permission triggers HOLD, never a silent host desktop fallback.

## Maintenance
The Weston test plugin references libweston internal ABI functions and is a laboratory harness requiring an ABI requalification on an upstream Weston change. Do not promote the plugin to production.
Use the existing Integration Spine as restart index and preserve the separate uncommitted UI-G04B/H research. Neither these G04B files nor any production F4/SDF renderer file belongs to AC03.
