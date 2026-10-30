# BLOB-AC-01 — Transactional Native Gesture Contract
Date: 2026-10-12
Integration target: canonical main, private tension-atoi/blob.in-showcase
Origin research: VectorCraft POC02 (storytold/vectorcraft @ dc640f3d6177cd528e917b1d542b59ccfd46443c); conceptual behavior only, no upstream code copied.
Status: CONTRACT RATIFIED BY USER / IMPLEMENTATION AND QUALIFICATION SEPARATE

## Mission
Build a std-only reusable gesture protocol on existing blobin-ui-core, not a second tree, renderer, graphics backend or compositor service.
Carry pointer delivery through UI-G04 InputRouter receipts and stale-epoch gates, preserve UI-G03 geometry/scale and UI-G02 stable NodeIds/COW snapshots.
Model one logical drag as Begin / Preview* / Commit OR Cancel. Render consumers may display overlays, but preview must not publish canonical state.

## Scope / ownership
- Implement new module crates/blobin-ui-core/src/gestures.rs, export it from lib.rs.
- Drive it with accepted UI-G04 InputReceipt paired to exactly the event dispatched by InputRouter.
- Gesture state belongs to this module, keyed by (surface,pointer), bound to one UI-G03 LayoutStamp and target NodeId.
- Geometry output is logical delta, not layout positioning, scene mutation, render submission or file writing.
- Consumer owns document edits, preview compositing and undo integration. The example tests one semantic commit per completed drag.
- Explicit cancellation on pointer cancel, Escape, window blur and invalidation; isolation across surfaces.
- Preserve the parallel UI-G04/B experiment files already dirty on main; no edits to them.

## Invariants / refusal
- No gesture begins without capture, enabled interactive node or matching source receipt.
- No drag commit for click/tap without a nonzero displacement.
- All deltas are absolute relative to pointer-down (no cumulative drift).
- Duplicated or mismatched receipts, invalid or stale epochs and nonfinite coordinates fail closed.
- A mid-gesture epoch/style/layout change cancels; no implicit rebasing.
- Pointer may move outside bounds only while router capture remains on original NodeId.
- Multi-pointer gestures remain independent; duplicate down never creates duplicate Begin.
- Key Escape and blur cancel all active gestures on their own surface.
- No unsafe code, no new dependencies, no egui/wgpu/Wayland imports, no third-party vendoring.

## Acceptance gates
AC-G01: check existing main/worktree ownership and preserve ongoing G04B dirty files.
AC-G02: code builds offline; rustfmt/clippy strict; direct gesture tests and existing regression tests green.
AC-G03: example consuming UI-G02/G03/G04 demonstrates Begin, multiple Previews, one Commit and one undoable semantic change; cancellation has zero canonical writes.
AC-G04: deterministic tests for duplicate serial, physical DPR normalization, out-of-bounds capture, Escape/blur/cancel, multi-surface isolation and lifecycle epochs.
AC-G05: source-only evidence, command stdout/stderr and hash ledger recorded; no G04B FULL PASS, FPS, GPU/renderer or CP03 claim.
AC-G06: commit only BLOB-AC-01-owned paths and push to existing PRIVATE origin/main; verify exact SHA and clean status of OUR paths. Concurrent G04B files may remain dirty and must not be staged.

## Explicitly deferred
- Renderer-backed animation, GPU frame, live Wayland pointer injection, native geometric transforms, accessibility end-user acceptance, cross-process authority.
- UI-G04/B remains HOLD until its independent physical pointer oracle passes.
- CP03 HYBRID-60 unchanged and remains NOT PASS.
- Actual GPL donor file remains external; no import.
