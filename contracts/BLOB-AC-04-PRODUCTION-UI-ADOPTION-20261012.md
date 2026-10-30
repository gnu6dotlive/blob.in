# BLOB-AC-04 — Production Canvas Transactional Gesture Adoption
Date: 2026-10-12. Mandate approved. Private main baseline ef4ca6d.
Targets: production egui/winit/wgpu showcase editor. BLOB-FRAME-v1 SDF renderer remains independently owned.

## Mission
Replace the existing production-canvas circle drag that directly writes SceneState on every mouse movement and invalidates the remote renderer repeatedly.
Adopt the AC01 Begin / absolute Preview / one Commit or Cancel transaction semantics in the existing canvas. Preview must remain local and non-destructive; commit triggers exactly one canonical scene/camera update and one scheduler invalidation.

## Ownership
- First-party module crates/showcase/src/ac04_scene_gestures.rs imports blobin_ui_core::gestures::Translation, stores original circle/world position or camera, ephemeral preview, and bounded 32-entry move undo history.
- Existing egui Response remains the single authoritative pointer recognizer/capture owner on the production egui canvas. Do NOT attach a second UI-G04 InputRouter over egui: duplicate pointer ownership risks duplicate delivery. This is a scoped behavior/type adapter, not a claim that core GestureCoordinator directly routes this production canvas.
- Production app draws an explicit temporary contour/ghost on top of the last BLOB-FRAME image, or locally reprojects that image during pan. Renderer frame content remains runtime-owned.
- Circle selection can update UI state on Begin; circles/camera and scheduler revision remain unchanged until Commit.
- On commit: one scene/camera edit, one scheduler.invalidate; no-op and cancel do not mutate.
- Ctrl+Z undoes last compatible circle MOVE only; stale external edits refuse; lab changes clear history.
- Escape, focus loss, resize/viewport mismatch, invalid delta, stale target and external state conflict cancel.
- For egui 0.36, drag_delta resets to zero on release; preserve last accepted preview through drag_stopped. At drag start recover press point by subtracting cumulative drag delta to hit test small targets.

## Gates
AC04-G01 OWNERSHIP: preserve all dirty concurrent G04B/H paths, no global fmt, no duplicate render worker.
AC04-G02 MODEL: absolute preview, no canonical scene writes until commit, pan, stale, cancellation, undo and invalid values tested.
AC04-G03 REAL EGUI: use egui Context.run_ui pointer and keyboard events to prove preview is transient, one scheduler invalidation on commit, Ctrl+Z undo, Escape cancellation, pan, and resize epoch.
AC04-G04 RUST: offline production binary build, strict Clippy -D warnings, production library regression, entire workspace library regression, no dependency additions.
AC04-G05 EVIDENCE: store stdout/stderr SHA-256 per command and source hashes; ledger and integration spine updated.
AC04-G06 DELIVERY: targeted commit + push to private origin/main; verify remote SHA, exclude G04B/H unpublished files.

## Exclusions and truth labels
No ArtCraft source or license-ambiguous vendor. No claims of new GPU SDF capabilities, inspector numeric-field gesture conversion, full history/redo, live compositor input into PRODUCTION app, compositor presentation timestamps, 60 FPS, accessibility sign-off, or CP03 HYBRID-60 PASS.
AC03 Weston + native GPU pixel E2E belongs to its separate two-card fixture and cannot be used as proof of production BLOB-FRAME evaluation.
