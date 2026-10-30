# BLOB-AC-02 — Native Gesture Consumer · bounded qualification contract
Ratified implicit next from BLOB-AC-01 GO · 2026-10-12
Repository: private tension-atoi/blob.in-showcase, canonical main, baseline 3dbf7378440f23cf9afda198b5fb5f408f56e687
Origin: VectorCraft gesture concepts only. No source imported, no vendoring, no renderer authority transfer.

## Objective and truthful deliverable
Apply BLOB-AC-01's accepted pointer Begin/Preview/Commit/Cancel to a dedicated native Wayland 2D qualification surface.
Demonstrate visually projectable preview and stable UI-G02 reorder commits under UI-G03 layout and UI-G04/A input.
The application is a non-production fixture. It must not mutate the F4 SDF renderer, BLOB-FRAME-v1, GPU render bridge, live Hyprland configuration or user files.
The canonical renderer remains independently owned by its existing runtime.

## Native consumer ownership
- New first-party scene model: crates/showcase/src/ac02_scene.rs; exposed via showcase lib only as fixture.
- New first-party native probe: crates/showcase/src/bin/blobin_ui_ac02_wayland.rs, winit + wgpu; owns only its test window and two colored quads.
- No changes to dirty or ongoing G04/B files; no source dependency on G04B private module.
- Reuse BLOB-AC-01 in blobin-ui-core, existing snapshot IDs, UI-G03 bounds/epochs and UI-G04/A InputRouter.
- The native program receives Winit WindowEvents, emits typed G04 events and consumes the exact accepted output via NativeGestureScene.
- At preview: translate the fixture's ephemeral quad only; no UiTree write.
- At commit: when horizontal delta exceeds 28% of dragged card width towards the other sibling, atomically reorder the two cards using one UiTree::transact; then recompute G03 layout and matching hit-test.
- A subthreshold drag does not mutate canonical state; a click remains an activation without drag commit.
- Escape/blur/resize/pointer cancel clear previews; stale serial and stale layout remain fail-closed.
- The fixture is two cards and not a renderer-independent vector transform engine or final product UX.

## Gates
AC02-G01 ownership: inspect clean tracked baselines and preserve concurrent G04/B dirty files, no broad formatting.
AC02-G02 static: tests of commit, cancel, no-op, click semantics, left/right reorder, and post-commit visual/hit parity.
AC02-G03 native build: wgpu/Wayland binary builds and passes strict Clippy; no ArtCraft vendor or new crates.
AC02-G04 scoped runtime: independent Weston socket, Vulkan window, at least one wgpu frame submission and a trace.
AC02-G05 visible pixels: qualified ONLY if own-window composited screenshot has no external-window leakage and an independent pixel oracle passes. A black Weston screenshot is a HOLD for pixels; a live Hyprland screenshot containing overlapping user windows must be discarded, not archived.
AC02-G06 pointer E2E: independent real compositor-delivered drag + matched input receipts + exactly one semantic reorder and post-commit pixel witness. NOT RUN until a safe isolated injection transport and oracle are established. Existing G04/B/H witnesses are separate evidence and cannot be promoted here by analogy.
AC02-G07 evidence: seal stdout/stderr, executable and sources SHA-256, retain positive and negative qualifications, do not claim GPU presentation feedback or frame pacing.
AC02-G08 delivery: targeted commit, push to private origin/main, exact SHA match. Preserve unrelated G04/B changes and evidence.

## Explicit exclusions and safety
No physical mouse/keyboard injection into the user's active desktop by AC02.
No user-screen screenshot retained or uploaded when compositor output includes other windows. Any such temporary screenshot must be deleted.
No CP03 HYBRID-60 claim, no UI-G04 FULL PASS, no 60/120 FPS claim, no 3D.
No use of GitHub Actions as a qualification tool. No upstream code vendor without separate license audit.
Failure of AC02-G05/G06 does NOT turn G02/G03/G04/A or AC01 prior scoped proofs into FAIL; it bounds the acceptance of AC02 itself.
