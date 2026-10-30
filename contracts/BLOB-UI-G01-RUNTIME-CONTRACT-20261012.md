# BLOB-UI-01 / UI-G01 — Portable 2D Runtime Contract v0.1 (PROPOSED)
Date: 2026-10-12
Document status: DESIGN BASELINE FOR IMPLEMENTATION; not an API implementation.
UI-G01 audit baseline: `94ecd03`; CP03 HYBRID-60 original gates remain unchanged/open.

## Mission
Ship a native Linux-first, renderer-independent 2D UI substrate consumable by applications without importing blob.in's showcase, F4 transport or egui. 3D is deferred and shall not be a prerequisite to the 2D runtime. Requirements imply testable reusable primitives, not visual imitation.

## Logical crates / surface ownership
- `blobin-ui-core`: immutable component snapshot interface, stable `NodeId`, `SurfaceId`, typed `InputEvent`, action/state store, transactions, dirty/revision scheduler, deterministic layout.
- `blobin-ui-scene`: display-list commands and bounds; fills, paths, strokes, clipping, transforms, text runs, layered opacity; no window creation.
- `blobin-ui-render-wgpu`: resources, atlas/cache, GPU recording and presentation. Handles `SurfaceLost`, `Outdated`, `Timeout`, device loss with typed outcomes.
- `blobin-ui-platform-wayland`: window lifecycle, scale factor, compositor/input integration, event timestamping and per-surface identifiers.
- `examples/interface-workbench`: independent application consumer demonstrating real state mutations, responsive panels and motion.

These are module boundaries first; crate names are reserved as design intentions, not claims about existing files.

## Data contract (conceptual, not compiled Rust)
- `NodeId`: stable per component lifetime; recycled IDs require generation to reject stale events.
- `SurfaceId`: unique presentation/input namespace. Changing one surface never resets other surface revisions.
- `UiTreeSnapshot { revision, roots, nodes }`: immutable tree per transaction; revision strictly increasing on semantic changes.
- `UiNode { id, parent, children_order, style, semantics, hit_behavior }`: stable identity and accessibility metadata separate from draw commands.
- `Constraints { min, max, available, scale_factor }` -> `LayoutSnapshot { node_rects, transforms, clips, revision }`.
- `InputEvent { surface, timestamp, device, kind, position?, modifiers }`; coordinates normalized explicitly (physical vs logical) at platform boundary.
- `EventRoute { capture_path, target, bubble_path }`; pointer capture is explicit and ends on release/cancel/destroy.
- `SceneSnapshot { ui_revision, layout_revision, display_list, damage_regions }`.
- `PresentedFrame { surface, scene_revision, submit_timestamp, presentation_timestamp?, feedback_kind }`; absent feedback cannot be interpreted as successful display.

## UI-G02 / UI-G03 / UI-G04 invariants
1. A transaction cannot mutate a snapshot already handed to a renderer.
2. New state cannot be visually attributed to an older revision. Late frames are dropped or explicitly classified as stale.
3. Stable IDs and stable layout semantics across insertion/reorder; no duplicated response for a single physical event.
4. Hit testing uses inverse world transforms and clip intersection with topmost ordered eligible node; a stale layout snapshot cannot receive events for newer geometry.
5. Pointer capture identity survives movement outside visual bounds, but ends on release/cancel/node or surface disposal.
6. Focus navigation order is deterministic and exposes accessibility role, name, disabled/selected/pressed semantics and logical hierarchy.
7. Resize and scale-factor changes re-run layout and update hit regions atomically; coordinates from stale scale epochs are rejected or converted.
8. Animation supports retargeting from its current value; finite/bounded under hitches; reduced motion must not change final UI semantics.
9. Idle state must be event-driven: do not schedule a continuous 60 Hz loop if no active animation/pending work.
10. Surfaces cannot share input state or GPU teardown ownership accidentally.

## Tests and evidence prerequisites
| Gate | Minimal test / independent oracle | Required claim before status PASS |
|---|---|---|
| UI-G02 | headless tree insertion/deletion/reorder/revision tests + mutations | deterministic tree diff and invalidation for stable NodeIds |
| UI-G03 | mixed-DPR/resolution resize matrix; nested clips and boundary overlaps | correct layout/bounds/hit-data for target surfaces |
| UI-G04 | real compositor-delivered pointer/keyboard E2E with trace and independent counts | one physical A/click triggers exactly one expected target; drag/cancel/focus survive resize |
| UI-G05 | interruption/retarget/reduced-motion tests + idle-vs-motion cadence measurement | no physics NaN, jump, background idle busy loop |
| UI-G06 | headless display-list conformance + pixel oracle for paths, strokes, text, opacity, transforms | backend image agreement and verified draw command provenance |
| UI-G07 | clean-build independent app with only documented public exports | no `blobin-showcase` or `egui` imports in consumer core |
| UI-G08 | 60 FPS workload fixture, compositor feedback, histogram p50/p95/p99, input-to-present trace, memory/idle/recovery tests | measured and reproducible on named machine, no disallowed overclaim |

Minimum acceptance app: resizeable dock/rail, searchable virtualized list, scroll with pointer capture, multi-panel inspector, vector workspace, keyboard navigation, reduced motion, two surface lifecycles. Synthetic scripted state changes alone cannot satisfy input E2E.

## Non-negotiable CP03 firewall
- CP03 HYBRID-60 retains its original hardware, scene, composition, performance, fidelity and evidence requirements without alteration.
- BLOB-UI-01 uses a **distinct** `BLOBIN-UI-60` scene, metrics and acceptance report if/when throughput is claimed.
- Passing UI-G01 gives **no** UI-G02..08 or CP03 PASS.
- 3D architecture extension points may be documented but not implemented as release prerequisites.

## UI-G01 outcome and authorized next action
Source inventory, dependency extraction plan and test plan established. **UI-G01 SCOPED PASS (documentation + evidence inspection), UI-G02 OPEN.**
Allowed next: implement headless `blobin-ui-core` skeleton in a fresh, separate branch, with tests before attaching UI01 renderers. Do not silently bring GPL-licensed donor sources into `LicenseRef-Proprietary`.
