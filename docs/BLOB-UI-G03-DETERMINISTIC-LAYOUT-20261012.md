# BLOB-UI-01 / UI-G03 — Deterministic Constraint Layout Qualification

Date: 2026-10-12
Source base: GitHub-backed `main` at `de4ff5e`
Delivery policy: direct `main` commit + private GitHub push, not a detached long-lived worker branch.
Status: **SCOPED PASS only when evidence/runs/blob-ui-g03-20261012/qualification.json reports PASS**.

## Mission

Turn the previously qualified renderer-independent component graph (UI-G02/A+B) into a deterministic logical measurement and placement system. Preserve the full CP03 HYBRID-60 gate firewall, keep 3D deferred, and do not confuse logical geometry with real hit-tested input or compositor-presented frames.

## Source / API

`crates/blobin-ui-core/src/layout.rs` is a new **std-only**, headless module. The already published tree and reconciliation APIs remain unchanged.

- `Size`, `Rect`: finite logical coordinates; half-open bounds.
- `PixelRect`: physical covered pixels calculated by **floor(left/top), ceil(right/bottom)**, avoiding cumulative rounded-width drift.
- `Length::{Auto,Px,Fraction}`: intrinsic, fixed logical size or parent-content fraction.
- `Style`: row/column, min/max size, padding, gap, flex grow/shrink, cross-axis stretch, nested child clipping.
- `LayoutStyles`: per-surface style-revision tracking; rejects invalid, stale or non-finite style overrides without mutating state.
- `Viewport`: logical extent, scale_factor (DPR) and host-owned geometry epoch; scale/resize must pass a distinct epoch.
- `compute(&UiSnapshot, &LayoutStyles, SurfaceId, Viewport)`: pure, atomic headless measure/place; no partial snapshot published on error.
- `LayoutSnapshot`: read-only node rectangles, own visible clip, physical clip coverage, deterministic preorder and typed stamp.
- `LayoutSnapshot::is_current`: rejects old surface epoch, changed per-surface tree revision, style revision, geometry epoch, viewport extent or DPR. Unrelated surface mutations **do not** invalidate unaffected surfaces.

### Measurement and placement semantics

1. Root siblings form a column flow in the requested viewport. A root normally uses `Style::fill()`.
2. Nodes derive intrinsic measurements from ordered child sizes plus gaps and padding; fixed and fractional dimensions clamp to min/max.
3. At placement, the content box excludes padding. Main-axis unused space is distributed by positive `flex_grow`; deficit is redistributed by weighted `flex_shrink`, with iterative min/max water-filling. Infeasible minima **overflow and clip**; layout must never silently violate the declared minimum.
4. Cross-axis Auto defaults to stretch up to max and at least min; explicit sizes retain their own cross extents.
5. `clip_children` intersects all descendant visibility with the parent's own rectangle. Without it, descendants inherit the ancestor clip, which may allow overflow beyond the immediate parent.
6. Layout uses stable `NodeId` ordering and no nondeterministic hash iteration. Depth >256, non-finite bounds, extreme offscreen extents, invalid styles and invalid viewports return typed errors.

### Scoped evidence

Reproduce locally without a GPU or compositor:

```sh
python3 scripts/blobin_ui_g03_verify.py
cargo run --offline -p blobin-ui-core --example layout_workbench
```

The verifier records hashes and complete outputs for strict formatting, 46 direct crate tests including 14 G03 tests, strict clippy, std-only dependency tree, a headless consumer and 51 workspace library regression tests.

The 14 G03 tests include **120 resolution × DPR combinations**, **512 independently calculated horizontal fixed+flex oracle cases**, pixel boundary checks, nested clip and un-clipped sibling, constrained row shrink/overflow, column fractional sizing, stale layout epochs, two-window independence, style validation, zero-sized viewport, depth rejection, and numeric-overflow rejection. Existing 400-step keyed reconciliation and 600-step transaction replay remain green.

## Deliberate exclusions

- No text intrinsic shaping; Auto for leaf components resolves from configured minima. Fonts, glyph metrics and line wrapping need an independent text-measure source (future scene/text subsystem).
- Layout is recomputed in full on every call, **not yet an incremental constraints cache**. G02/B page-copy-on-write is not proof of incremental layout performance.
- No absolute positioning, baseline alignment, scroll offset, grid, percent-based cyclic resolution, transform matrix, or rotated/skewed clipping. These require subsequent scoped contracts and oracles.
- `LayoutBox.visible` supplies rectangle hit geometry only; **no actual hit-testing, pointer capture, inverse transforms or event routing** (UI-G04).
- Physical pixel bounds are coverage diagnostics, not GPU draw submissions or compositor screenshots. No visual UI runtime, human input, 60 FPS or reduced motion claim.
- Limits on extreme coordinates and depth are intentional fail-closed guards; these are typed `LayoutError`s, not silent truncation.
- CP03 HYBRID-60 remains OPEN: G03 does not qualify the F4 pipeline, mixed 3D geometry or native presentation.

## Next gate

**UI-G04 — native input contract, hit regions and focus.** Start with logical physical coordinate conversion, event ordering, clip-aware topmost hit routing, pointer capture/cancel, typed focus and accessibility semantics. Qualify real compositor-delivered pointer/keyboard events separately from scripted tests. Begin on `main`, and finish by testing, sealing evidence, committing, pushing, and verifying `origin/main`.
