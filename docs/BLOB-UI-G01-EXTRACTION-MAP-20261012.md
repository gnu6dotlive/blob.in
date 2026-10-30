# BLOB-UI-01 / UI-G01 — Extraction Map and Dependency Barriers
Date: 2026-10-12
Base `94ecd03`. This is a proposed architecture, not proof of implementation.

## Critical dependency inversion

Current direction:
`blobin_ui_lab executable -> blobin_showcase::ui_widgets(egui::Ui) + ui_motion(UiRuntime) -> egui tessellation -> egui-wgpu -> wgpu Vulkan -> Wayland`.

Target direction:
`consumer -> blobin-ui-core (state/events/tree/layout/motion) -> blobin-ui-scene (geometry/display list)`;
`blobin-ui-platform-wayland (winit input/window) -> core events`;
`blobin-ui-render-wgpu (scene display list -> GPU) -> surface lifecycle`.
`blobin-ui-egui-adapter` may exist only as an optional compatibility bridge, never as a required public core dependency.

The display list is the exchange type. Renderers do not own user state; widget controls do not own the GPU device; platform windowing does not own event dispatch policy. Use explicit surface IDs to avoid aliasing state across two windows.

## Extraction candidates and decision

| Source | Destination | Decision and required work |
|---|---|---|
| `ui_motion::Spring` | `blobin-ui-core::motion` | **EXTRACT FIRST** (standalone Rust); generalize retargeting, motion profile, timestep policy, finite-value guards, deterministic tests |
| `ui_motion::UiAction / UiRuntime` | `blobin-ui-core::state` | **REFACTOR**, demo-specific `SelectSurface(i < 3)` is NOT the public action vocabulary; preserve revision semantics |
| `ui_motion::Layout` | `blobin-ui-core::layout` | **DON'T LIFT AS-IS**; replace fixed rail/inspector heuristic with constrained layout API; keep as golden sample |
| `ui_widgets::organic_vertices` | optional `blobin-ui-scene::shape` | **ADAPT**: prototype polygon generator, must not impersonate archived cubic-Bézier pipeline |
| `ui_widgets::draw/button/blob` | `examples/interface-workbench` | **KEEP AS CONSUMER**; current `egui::Ui`, `egui::Id`, `Sense`, fonts, pointer state violate independence |
| `scene::SceneState::hit` | fixture `tests/ui_hit_oracle` | **ADAPT ORACLE**; topmost circle only, add ordered nested tree paths, transforms, clipping, overlapping hit areas |
| `scheduler::Scheduler` | `blobin-ui-core::scheduler` | **BORROW INVARIANTS ONLY**; existing model is for single in-flight F4 requests, not adaptive UI repaint or per-surface transactions |
| `blobin_ui_lab::Lab/Graphics` | `blobin-ui-platform-wayland` and `blobin-ui-render-wgpu` | **EXTRACT BEHIND TRAITS**; eliminate logic-policy coupling in renderer and window callback |
| Archived `path/group/tessellate` | `blobin-ui-scene::vector` | **QUARANTINE** until license decision and tests on arbitrary complex/hole paths, index overflow, malformed input |
| Archived `solve` | motion A/B oracle | **COMPARE** against UI01 spring before choosing solver implementation |
| Archived `ffi`, `blobin-qt`, `blobin-cxxqt` | none | **DO NOT IMPORT** |
| Existing `vendor/wgpu-hal-30.0.1` patched dependency | platform-only integration | **ISOLATE**; avoid embedding CP-J/CP03 vendor branch changes into portable UI-core |

## Non-negotiable boundaries
1. `blobin-ui-core` compiles with no winit, wgpu, egui, Qt, C++, GPU, F4 broker, environment variables or global singleton; unit tests run headless.
2. Renderer accepts immutable, versioned display-list snapshots; it cannot mutate component state.
3. Layout is deterministic for a given tree, constraints, DPR and resolved text metrics; no hardcoded app name or panel widths in the core.
4. Events are typed and timestamped, with explicit capture/target/bubble phases; node identity survives reorder, resize and animations.
5. Reduced motion changes duration/dynamics, not hit areas, semantics or state-revision monotonicity.
6. Per-surface input identity and frame provenance; close/reopen of one surface cannot invalidate another.
7. Device loss and compositor errors produce typed recoverable state, not a hidden fallback.
8. No `60 FPS` or `120 Hz` claim from `WaitUntil(16ms)`, `submitted` or average event-loop ticks alone.
9. All direct historical code imports require verified license/provenance and a recorded packaging decision.
10. UI and CP03 retain separate tests, metrics, acceptance records and no cross-credit.

## Recommended implementation order
- **UI-G02/A** core types + stable node identity + testable state transactions and minimal retained display tree; headless tests first.
- **UI-G02/B** deterministic tree diff and dirty propagation with explicit revision and dependency graph.
- **UI-G03** constraints, measure/place, DPR/reflow, clipping and transformed bounds.
- **UI-G04** hit-test tree, pointer capture, keyboard focus, gesture cancellation, true injected pointer/keyboard E2E.
- **UI-G05** motion/retargeting & no-runaway idle re-render; interruption consistency test.
- **UI-G06** renderer-agnostic vector display list + tessellation + glyph shaping; wgpu backend.
- **UI-G07** separate example/app that depends on exported crates, never showcase internals.
- **UI-G08** latency / frame pacing with presentation feedback, memory/idle and accessibility test protocols.

## Exit decision for UI-G01
**GO to UI-G02/A only**, with archived donor copy prohibited until legal/provenance review. No merge to main, remote push, default runtime changes, CP03 gate changes or production deployment authorized by this document.
