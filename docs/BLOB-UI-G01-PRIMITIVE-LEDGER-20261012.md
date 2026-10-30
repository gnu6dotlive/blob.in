# BLOB-UI-01 / UI-G01 — Primitive Ledger (source-backed)
Date: 2026-10-12
Gate: UI-G01 inventory only. Implementation gates UI-G02..UI-G08 remain OPEN.
Audit baseline: `94ecd030ef8cde064d7518f681761c2706ce5b00` (`feat/blobin-native-ui-motion-20261012`).
Historical donor: read-only archive `/mnt/workbench/build/appstack-b3-baseline-4603aed/engine/blob.in`; NOT an active checked-out Git repository.
Witnesses: `/mnt/workbench/evidence/runs/blobin-ui01-20261012-01/`.

## Vocabulary (no inferred readiness)
- **CURRENT/SCOPED**: implemented in active candidate, demonstrated only in stated tests.
- **DONOR/CANDIDATE**: appears in historical archive; no current UI integration proof.
- **EXTERNAL/ADAPTER**: existing capability is delegated to egui, wgpu or winit and is NOT owned by blob.in.
- **MISSING**: no general independent runtime primitive demonstrated in inspected candidate.
- **BLOCKED**: requires legal/compatibility or semantic reconciliation before copying.

## Active candidate — 2026-10-12

| Primitive | Direct source | Finding | Disposition |
|---|---|---|---|
| Linux Wayland window and lifecycle | `crates/showcase/src/bin/blobin_ui_lab.rs:37-108,244-331` | winit Wayland window; resize reconfigures wgpu surface; isolated lab binary | **CURRENT/SCOPED**; platform adapter, not UI public API |
| Vulkan GPU presentation | same `:45-97,145-243` | wgpu Vulkan backend, egui-wgpu renderer; native compositor captures qualified | **CURRENT/SCOPED**, no steady 60 FPS or presentation-feedback proof |
| Event intake | same `:244-331` | winit keyboard/event loop; pointer UI delegated to egui-winit/egui | **EXTERNAL/ADAPTER**; explicit pointer routing and capture not independently specified |
| Reactive action state | `crates/showcase/src/ui_motion.rs:58-64,99-171` | typed `UiAction`, `ui_revision`, selection, panel toggles | **CURRENT/SCOPED** for one hard-coded 3-surface demo, not a general observable state graph |
| Springs and reduced motion | `ui_motion.rs:6-56,129-171` | bounded dt, convergence and reduced-motion tests | **CURRENT/SCOPED**; can be extracted without egui/wgpu |
| Responsive geometry | `ui_motion.rs:67-97` | rule-based rail + canvas + inspector; compact breakpoint | **CURRENT/SCOPED**; not constraint layout or intrinsic sizing |
| Animated vector surface | `crates/showcase/src/ui_widgets.rs:57-100` | CPU-generated 96/128-point polygon, egui::Shape fill | **CURRENT/SCOPED**; NOT Bézier path tessellation |
| Widget controls / focus | `ui_widgets.rs:29-56,100-444` | egui::Ui, egui::Id and Sense; authored buttons/panels | **EXTERNAL/ADAPTER**; no independent focus model or accessibility tree |
| UI typography | `ui_widgets.rs:19-27`; `Cargo.toml:23-25` | default egui font via painter, no independent shaping / atlas contract | **EXTERNAL/ADAPTER** |
| CSG scene editor | `crates/showcase/src/scene.rs:1-212` | circular primitives + CSG operators + world camera model | **CURRENT/SCOPED**; consumer-specific scene state |
| Scene hit testing | `scene.rs:140-149` | topmost circle in world-space, tolerance threshold | **CURRENT/SCOPED**; not component-tree hit testing |
| Frame/request scheduler | `crates/showcase/src/scheduler.rs:1-145` | revisions, one in-flight request, supersession and stale-frame rejection | **CURRENT/SCOPED** for remote F4 frames; UI scheduling semantics need separate design |
| Standalone app boundary | `crates/showcase/src/lib.rs`; `crates/showcase/Cargo.toml` | `ui_motion`, `ui_widgets` exported inside `blobin-showcase` alongside F4/CSG; `ui_widgets` imports egui directly | **MISSING** independent UI package and documented stable public contract |
| Retained component tree / diff | inspected `crates/showcase/src` | no general stable-ID tree + declarative diff/invalidation engine in inspected code | **MISSING** |
| Scroll/virtualized lists, clipping and transform stack | inspected UI modules | egui supports some controls, but blob.in public ownership not demonstrated | **MISSING** runtime-owned implementation |
| Independent access/navigation | inspected UI lab and recorded probe | no verified keyboard traversal/accessibility semantics; scripted state actions ≠ real input replay | **MISSING** |
| Input-to-photon and sustained cadence | `docs/BLOBIN-UI01-NATIVE-RENDER-AND-MOTION-20261012.md`; qualification JSON | explicitly unqualified; 16 ms wait is a scheduling hint, not frame-time proof | **MISSING** |

## Historical blobin-core donor — archival candidate ONLY

| Primitive | Archived source | Observed capability | Extraction disposition |
|---|---|---|---|
| Cubic-Bézier `Path`, `Contour`, `Cubic` | `blobin-core/src/path.rs` | logical coordinates, contour winding and bounds; source SHA-256 `50422f48242972c08a9040bed5a71d4b7eb53aa68e734a78397663325bd796bd` | **DONOR/CANDIDATE**; revalidate degenerates and bounds |
| Tessellation via lyon | `blobin-core/src/tessellate.rs` | adaptive fill; GPU-oriented mesh with `u16` indices | **DONOR/CANDIDATE**; handle errors, index overflow and non-convex contours |
| Affine transforms | `blobin-core/src/group.rs` | translate, rotate, scale and parent composition using glam | **DONOR/CANDIDATE**; define transform inversion and hit-test mapping |
| Spring/easing/tween | `blobin-core/src/solve.rs` | configurable token-derived spring and tween | **DONOR/CANDIDATE**; compare determinism and monotonicity against UI01 spring |
| Organic shapes | `blobin-core/src/blob.rs` | RectBlob, SuperBlob, Inverted lower to cubic Paths | **DONOR/CANDIDATE**; export as optional geometry recipe |
| Materials | `blobin-core/src/material.rs` | color/alpha/gradient/noise parameters | **DONOR/CANDIDATE**; avoid renderer-specific assumptions |
| Pool scheduler | `blobin-core/src/pool.rs` | engine entity ticks / dirty engine IDs | **DONOR/CANDIDATE**; not equivalent to component-frame scheduler |
| Qt/C++ hot bridge | `blobin-core/src/ffi.rs`, `blobin-qt/` | `cxx` and Qt render adapter | **EXCLUDE** from native 2D core |
| GPUI painting adapter | `blobin-gpui/src/canvas.rs` | GPUI Canvas drawing historical paths | **REFERENCE ONLY**, do not depend on GPUI in 2D core |

Historical `blobin-core/Cargo.toml` and root `Cargo.toml`: `GPL-3.0-or-later`, lyon 1.0, glam 0.27, cxx 1.0, optional rayon. Current showcase workspace: `LicenseRef-Proprietary`. **License compatibility is BLOCKED pending an explicit distribution/licensing decision**; do not paste donor source into the proprietary workspace or silently relicense it. A privately owned archive does not by itself establish sublicensing authority over all dependencies/contributions.

## Verification executed in this UI-G01 review

- `cargo test --offline -p blobin-showcase --lib` in UI01 worktree: **20 passed, 0 failed**; includes 6 `ui_motion` tests, plus geometry/widget and frame scheduler tests.
- `python3 scripts/test_blobin_ui01_oracle.py`: **7/7 adversarial evidence mutations rejected**.
- Prior sealed result: `qualification-20261012.json`, `BLOBIN_UI01_NATIVE_MOTION_SCOPED_PASS`, 180 submitted native frames, 4 compositor captures, 6 scripted UI-state actions. This historical report was inspected, **not rerun as an independent native capture** during UI-G01.
- Report explicitly records `human_pointer_click_verified=false`, `compositor_wp_presentation_feedback_qualified=false`, `sustained_60fps_qualified=false`, `cp03_hybrid60_pass=false`.

## Audit outcome

**UI-G01 source inventory: COMPLETE / SCOPED PASS.**
**Portable interface runtime: NOT QUALIFIED.** No claims about production quality, independent component embedding, user input replay or CP03 HYBRID-60 are upgraded by this inventory.
