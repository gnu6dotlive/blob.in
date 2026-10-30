# QCHAIN-FRAME-01 — Scene-bound CPU memfd transport

**Status:** `REAL_F2_F3_F4_CPU_FRAMES_SEALED_SEQPACKET_ROUNDTRIP_PASS / SHOWCASE_WAYLAND_NOT_RUN / QCHAIN_FULL_OPEN`.

**Owner:** isolated branch `feat/qchain-scene-frame-protocol-20261010` of `blob.in-showcase` (base `9b98155b09b957de8e1ed874fe127c0f82cdc559`).

## Implemented and observed

- New opt-in protocol module `crates/blob-frame/src/qchain.rs`, version `QCHAIN-FRAME-v1`. Existing BLOB-FRAME-v1 control types and semantics are unchanged.
- `SceneRequest` binds request_id, revision, canonical F2 scene SHA256, F2 semantic digest and expected F4 RGBA SHA256 to **one** exact source frame.
- `serve_one` accepts a same-UID peer, validates its exact scene/revision/hash binding and responds with a **single sealed memfd** carrying the actual CPU F4 output. Explicit labels: `F2_F3_F4_CPU_WITNESS_NOT_WAYLAND`, `gpu_qualified:false`, `compositor_observed:false`.
- `receive_one` validates the exact response, frame dimensions **512×384**, stride **2048**, bytes **786432**, opaque alpha, F2 scene identity and the actual received pixel SHA256, preserving its sealed read-only mapping.
- Real private CPU evidence comes from `/mnt/workbench/evidence/runs/qchain-cpu-20261010/raw/`. An independent test loops all **five** original F4 RGBA outputs, transmits each over a real local SEQPACKET socket pair with SCM_RIGHTS, remaps and compares bytes exactly. A forged expected-pixels SHA is refused.
- Validation: new protocol unit tests **2/2 PASS**; real evidence integration tests **2/2 PASS**; Rust Clippy `-D warnings` PASS; no GPU invoked.

## Boundary explicitly not crossed

- The production `blobin_renderd` socket and process were not changed or contacted by this experimental source.
- The current `blobin-showcase` app still consumes **BLOB-FRAME-v1** `RenderRequest` for CSG circles. It has no QCHAIN-FRAME-v1 viewer mode. Therefore **no compositor screenshot, actual frame presentation, user input or physical photon evidence** is claimed.
- This channel is **separate and versioned**. It does not overload `geometry_sha256` from a circle scene, accept a forged backend, or pretend an arbitrary F2 organic field is CSG circles.
- The test pair is same-user IPC and requires same-UID peer. A production-capable controller would additionally require a source allowlist, monotonic session sequencing, resource quotas and explicit integration authority.
- There is no independent scene authority beyond the bounded witness fixture. This is experimental transport, not a released protocol.

## Next E2E gate

Create a **private opt-in QCHAIN viewer** that negotiates QCHAIN-FRAME-v1 and displays the actual received F4 frame in a native Wayland surface while preserving the current showcase's default path, then obtain a compositor screenshot verified against exact F4 RGBA bytes (allowing for known color-profile/resampling conversions). Only then classify `F2→F3→F4→local IPC→Wayland` as observed.

**No merge, push, GPU display test or production deployment.**
## Follow-up acceptance (2026-10-10)

The subsequent opt-in native Wayland compositor experiment is recorded separately in [`QCHAIN-FRAME-02-WAYLAND.md`](QCHAIN-FRAME-02-WAYLAND.md). Five CPU source frames were transmitted, submitted to a Vulkan presentation surface and independently matched to compositor captures byte-for-byte **outside Hyprland's documented 18px rounded-corner mask**. This does not change the original transport-only verdict above or qualify physical photons / CP03 FULL.
