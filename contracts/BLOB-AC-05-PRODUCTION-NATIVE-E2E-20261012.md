# BLOB-AC-05 — Production Native Gesture to Actual Renderer E2E
Date: 2026-10-12 · user-approved GO
Canonical repository: private tension-atoi/blob.in-showcase, main baseline f364c69225cba10a532806a6937b620ab1874ca5

## Mandate
Qualify a production-canvas drag from an isolated Weston input seat through the REAL blobin-showcase UI (egui/winit/wgpu) and its existing BLOB-FRAME-v1 transport into the REAL blobin_renderd CPU engine and back into original, source-rendered SDF pixel buffers.
Do not substitute blob-frame-testserver reference cards (they do not evaluate geometry).
Stay read-only toward the upstream renderer and the users active Hyprland environment.
No changing the authoritative F4 runtime ownership or manufacturing GPU performance claims.

## Scoped implementation
- scripts/blob_ac05_weston_test_input.c: test-only Weston 15 plugin, isolated socket prefix blob-ac05-private- and opt-in environment guard. Private artificial seat emits 2D pointer gestures at actual production Primitive lab circle coordinates. Never use /dev/input or active Wayland socket. C code is first-party derived from the earlier first-party AC03 fixture.
- scripts/blob_ac05_private_preflight.py: manually starts private user+network-namespace Weston, actual blobin_renderd, worker05c/blobin_frame_worker fingerprinted by SHA256, and real blobin-showcase in CPU/Primitive lab. Records process logs and production trace, bounded lifetime. It is a launcher, NOT an independently passing oracle.
- crates/showcase/src/app.rs: fixes egui 0.36 TexturesDelta drop panic after resources are uploaded/freed; fixes disappearing transaction preview when egui repaints without new pointer delta. Emits opt-in trace events while tracing is enabled and allows opt-in original ReceivedFrame RGBA bytes to a local evidence directory for up to two frames. Not a substitute render kernel.
- scripts/blob_ac05_qualify_capture.py: offline independent oracle for the already captured source frames and traces, compresses original buffers losslessly, exports PNGs, pins hashes and verdict. Does not inject input.
- scripts/blob_ac05_revalidate.py: independently rechecks the archived gzip/PNG pixels, original source hashes and event/renderer logs without running any compositor.
- scripts/blob_ac05_verify.py: offline code/test/ledger verifier, NOT a claim that private Weston is replayed on every execution.

## Required qualification gates
AC05-G01 production-source provenance: independent reviewer can inspect source, binary identity, existing private main, known constraints, dirty parallel UI-G04B paths unchanged.
AC05-G02 runtime ingress: record actual compositor plugin motion+button steps, corresponding Winit positions and primary down/up on production window. Private user+network namespace ONLY.
AC05-G03 transaction: at least two absolute previews, no scheduler revision bump before release, one commit and exactly one revision advance.
AC05-G04 renderer: actual renderd origin blobin-cuda05f-render-bridge, two CPU BLOB-FRAME-v1 requests at revisions 3 and 4 with 3 primitives, two returned frames, no fallback or test-card server.
AC05-G05 SDF pixels: two independently mapped original renderer frames, SHA256 different, (205,400) white→black, (345,400) black→white, unchanged background pixel (20,20). Source bytes preserved in deterministic gzip, plus actual PNG.
AC05-G06 regression/build: strict Clippy, offline production build, production UI test and workspace library tests, no unrelated source formatting.
AC05-G07 evidence: logs, digest oracle, source hashes, runtime verdict precisely CPU_LOCAL_PREVIEW_NOT_GPU_QUALIFIED. A successful offline validation of prior captured data DOES NOT prove a new live run.
AC05-G08 delivery: only owned AC05 files staged, private GitHub main push verified by remote SHA; preserve all UI-G04B/H local state.

## HOLD and non-promotions
The enhanced new isolated replay orchestrator was attempted but its namespace check could not read /proc/1/ns/net in the user namespace; a subsequent execution was blocked by the environment. This is a separate automation/replay HOLD. The already executed prior private preflight and its saved independently qualified traces remain evidence for the bounded run.
No presentation feedback from Weston; native wgpu does submit frames but no independent compositor confirmation. No real USB/HID and no end-user design ratification. No AMD/Intel cross-vendor, GPU kernel, 60 FPS or CP03 HYBRID-60 claim. The CPU renderer advertises CPU_LOCAL_PREVIEW_NOT_GPU_QUALIFIED, reproduced verbatim.
No external ArtCraft vendor/copy. No changes to blobin_renderd, frame workers, BLOB-FRAME-v1 protocol or launcher G04B/H.
