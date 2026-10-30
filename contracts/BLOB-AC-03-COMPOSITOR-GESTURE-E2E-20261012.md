# BLOB-AC-03 — Compositor Gesture E2E & GPU Pixel Oracle
Date: 2026-10-12 · ratified "Go" · first-party / private main
Baseline: a54edee37938990a4e9601707f18b7d16204ec68
Authority: blob.in's BLOB-AC-01 / BLOB-AC-02; renderer SDF/F4 and native production bridge remain owned by existing components.

## Purpose
Turn AC-02's headless native-consumer proof into a reproducible, *compositor-delivered* gesture E2E without manipulating the user's current Hyprland seat or duplicating blob.in's renderer.
Establish exact correlation between an independent Weston seat, native winit ingress, accepted InputRouter receipts, Begin/Preview/Commit sequence, UI-G02 state revision, and GPU-produced client pixels.

## Ownership and implementation
- Test-only Weston module: scripts/blob_ac03_weston_test_input.c; compiled against local Weston 15.0.1's libweston ABI; loaded only when BOTH the BLOB_AC03_ISOLATED_COMPOSITOR=1 gate and private socket prefix blob-ac03-private- are present. It constructs a private pointer seat and emits motion/button via libweston, NOT /dev/input or host Hyprland. The entire test runs in an unshare -Urn user+network namespace with private loopback.
- Native consumer extension: only crates/showcase/src/bin/blobin_ui_ac02_wayland.rs, adding explicit opt-in --pixel-evidence-dir. It performs COPY_SRC from the actual wgpu surface texture for exactly one frame before, one during preview and one after a commit, maps the GPU staging buffer and writes raw RGBA-order bytes for independent verification. No image generation or fake pixel oracle. Without opt-in no texture-copy behavior is enabled.
- Independent Python proof: scripts/blob_ac03_isolated_e2e.py; checks serials, native window ingress, receipt pairing, one Begin, two distinct absolute Preview deltas (55,140), one commit, exactly one document revision increase, no spurious activation, >=4 GPU submissions, and actual client swapchain pixels. It converts raw buffers to PNG and verifies left/right color positions across three stages. The raw buffer bytes are hashed, then deleted; corresponding PNGs are retained.
- Reproducible orchestrator: scripts/blob_ac03_verify.py; pins build inputs, runs strict unit/regression checks and builds test-only plugin and AC02 native fixture, stores stdout/stderr and SHA-256 evidence, then runs private E2E.
- No changes to the in-progress UI-G04/B files or production renderer; G04B/H files remain outside staging.

## Gates and classifications
AC03-G01: ownership, isolated namespace & module refusal outside unique private socket.
AC03-G02: std-only AC-01 + AC-02 semantic regressions, Rustfmt on touched file, Clippy -D warnings.
AC03-G03: native fixture and Weston module reproducibly compile offline against installed dependencies.
AC03-G04: actual private Weston seat motion/button -> Wayland -> native winit callback; serial correspondence for six events, including two previews and one commit.
AC03-G05: initial UI revision 1 / final revision 2; no double activation or double commit; cancel/noop semantics retained from AC-02 tests.
AC03-G06: actual swapchain GPU copy/readback before/preview/after; independent PNG pixel sample and content SHA-256 verifies card colors moved. **This does not establish compositor presentation feedback or screen capture.**
AC03-G07: evidence ledger, photos only from isolated private fixture, reproducible SHA/hash manifest and negative evidence retained.
AC03-G08: scoped commit, private push to canonical main and SHA match. No unmerged branches; no broad cargo-fmt side effects.

## Scope exclusions / no forbidden promotions
- Not physical USB/HID device provenance; test seat injected inside Weston.
- Not independent compositor presentation timestamp or frame-pacing/60 FPS validation.
- Not final blob.in 2D UI acceptance, accessibility or production-ready native widget library.
- Not SDF renderer BLOB-FRAME-v1, CP03 HYBRID-60, cross-GPU or cross-compositor product reliability.
- Weston 15 internal plugin ABI is **test-lab-only**; never ship/vend into Gnosix runtime.
- No ArtCraft upstream code copied. No user desktop screenshot, process takeover, input injection, network server or modified application configuration.

## Stop conditions
Any mismatched serial, missing native event, duplicated commit, non-finite delta, absent GPU stage, unexpected surface format/dimension, unqualified pixels or namespace refusal => HOLD and no promotion. The local baseline and independent G04B/H evidence are preserved regardless of outcome.
