# BLOB-AC-04 — Qualification and native UX behavior
Date: 2026-10-12. Contract: contracts/BLOB-AC-04-PRODUCTION-UI-ADOPTION-20261012.md
Reproduce from private main: python3 scripts/blob_ac04_verify.py
Receipt: evidence/runs/blob-ac04-20261012/qualification.json

## Production canvas change
The real blobin-showcase editor, not an additional standalone demo, now uses CanvasTransactions to manage SDF circle dragging and background pan as Begin → Preview* → Commit/Cancel.
On preview, canonical scene coordinates and camera are held; the UI presents a ghost/preview circle or a locally reprojected last BLOB-FRAME raster. The SDF runtime is NOT asked to re-evaluate every intermediate movement.
On commit, a single scene or camera mutation calls the existing Scheduler::invalidate once; the existing runtime worker and BLOB-FRAME protocol retain all evaluation and pixel ownership.
On cancellation or no-op, no renderer invalidation occurs. Escape, focus loss, viewport resize, nonfinite coordinates and stale target are accounted for. Ctrl+Z restores a compatible last circle move, with a bounded 32-entry move history and fail-closed conflict handling.
The UI displays a specific LOCAL PREVIEW indication so no viewer mistakes a ghost for newly computed runtime geometry.

## Actual egui tests
A headless driver uses egui Context.run_ui with the actual production ui_root and real egui pointer/keyboard event processing.
It checks drag preview vs canonical scene geometry + scheduler revision, exactly one commit on pointer up, Ctrl+Z undo, Escape cancellation, background pan baseline and viewport resize invalidation.
The test uncovered the real egui 0.36 release-cycle bug: drag_delta becomes zero at drag_stopped; the adapter now commits the last accepted preview, never re-previews zero on release. Hit test reconstructs the down position from cumulative drag displacement to avoid dropping small targets.
The egui-only test harness clears texture deltas explicitly; it does not make GPU/compositor performance claims.

## Authority boundaries
The existing egui Response is the sole pointer capture/hit-test authority in this production screen. The generic AC01 Translation delta type is reused, along with its transaction semantics, but its separate G04 InputRouter / GestureCoordinator is not installed over egui. UI-G02/G03/G04 lab proofs from AC01-03 are not silently promoted as real production input-router qualification.
No source external to blob.in is copied, and no dependencies are added.
The renderer implementation, frame bridge and SDF visual kernel remain unchanged.

## Evidence labels
SCOPED PASS requires the independent local receipt script, all exit codes zero and a private GitHub SHA match.
Out of scope: physical HID, compositor-delivered gesture and confirmed frame content from the production showcase, real BLOB-FRAME-v1 render output comparison, compositor frame feedback, timing/60 FPS, end-user polish, G04B FULL and CP03 HYBRID-60.
Next bounded step after AC04: production compositor gesture → real BLOB-FRAME rendered frame → independent post-commit pixel/hit-test oracle; inspector transaction migration separately.
