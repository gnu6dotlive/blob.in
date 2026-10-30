# BLOB-AC-02 — Native Gesture Consumer : implementation and evidence
2026-10-12 · private main · fixture-only integration

## Implemented
This result promotes the headless gesture API from BLOB-AC-01 into a real Wayland/wgpu native consumer, but does not promote it into the production SDF renderer.
- AC02 scene controller: crates/showcase/src/ac02_scene.rs, pure UI-G02/G03/G04/A/AC01 consumer, no GPU object ownership.
- Native binary: crates/showcase/src/bin/blobin_ui_ac02_wayland.rs. Owns its separate window, its GPU, two illustrative cards and JSONL traces. The renderer/transport components of blob.in are unmodified.
- One native input path: Winit WindowEvent → InputRouter dispatch → GestureCoordinator observe → preview projection / atomic UiTree reorder → fresh G03 layout.
- Drag previews do not advance the canonical tree revision. A successful reorder changes the tree revision once, moves the card to its new layout box and ensures subsequent hit tests use the updated geometry.
- Click activation is preserved and is not conflated with a successful drag. Escape, blur and resize cancel an active preview.

## Scoped positive proof
Run: python3 scripts/blob_ac02_verify.py
The verifier checks the two owned source files with rustfmt without reformatting unrelated historical sources, strict Clippy on the owned native binary and showcase library, six native-consumer semantic tests, the prior AC01 crate tests, full workspace library regressions, offline binary build, and a privately namespaced Weston launch with a real wgpu/Vulkan submitted frame.
All per-command results and hashes are written under evidence/runs/blob-ac02-20261012.
The source and binary are first-party in blob.in; ArtCraft VectorCraft inspired the state model but no ArtCraft source or assets were imported.

## Independent witness boundaries
A private Weston headless test proved a Wayland native window, Vulkan adapter selection and at least one submitted frame. There was no compositor input injection, no observed native drag and no reliable compositor frame-presentation feedback.
Weston's screenshots were all black and therefore were **not qualified as visible pixel proof**. The diagnostic black PNG is negative evidence, not a screenshot of the UI.
A separately attempted Hyprland compositor crop included content from other desktop windows due to overlap/transparency; this unsafe image and its traces were **discarded immediately** and are not in the repo. Consequently there is no qualified live-user-session screenshot from AC02, and no other user windows should be present in artifacts.
Existing unpublished G04/B/H Hyprland input experiments are separate from this consumer. The G04/B/H witness may show real input routing, but it does NOT prove AC02 gestures or a post-commit compositor frame.
AC02-G05 visible-pixel oracle and AC02-G06 independently injected real gesture E2E remain OPEN.

## Consequences / next handoff
- Do NOT claim native gesture end-to-end production readiness, 60 FPS, standalone native renderer qualification, or CP03 HYBRID-60 PASS.
- Next optional gate: safe isolated compositor input automation on the AC02 class (not the user's desktop), independent ingress/receipt/commit oracle and compositor-owned capture not containing other windows. Avoid privileged uinput against the active Hyprland seat unless separately authorized.
- Confirm each AC02 source/evidence SHA and push receipt in private GitHub. G04/B dirty paths remain untouched and uncommitted.
