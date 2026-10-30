# BLOB-UI-01 / UI-G02/A — Portable Component Substrate

Date: 2026-10-12
Parent audit: UI-G01 `e425232`
Branch: `feat/blobin-ui-g02a-core-20261012`
Scope: headless component identity + transactional state graph. **No renderer qualification.**

## Delivered source

- `crates/blobin-ui-core/Cargo.toml`: new, self-contained Rust workspace member, **no crate dependencies**.
- `crates/blobin-ui-core/src/lib.rs`: portable component substrate.
- `crates/blobin-ui-core/tests/component_tree.rs`: deterministic component/transaction tests.
- `crates/blobin-ui-core/tests/transaction_adversarial.rs`: rollback, non-resurrection and 600-step deterministic replay.
- `crates/blobin-ui-core/examples/tree_transaction.rs`: headless example.
- Workspace `Cargo.toml` and `Cargo.lock` updated to register the package.

No code was copied from the historical GPL-3.0-or-later blobin-core donor. The active workspace retains its existing LicenseRef-Proprietary declaration, pending a separate distribution/licensing review.

## Public API / invariants implemented

| Construct | Contract | Status |
|---|---|---|
| `SurfaceId` | Per-window/per-surface namespace; independently maintained revisions | Implemented |
| `NodeId {slot,generation}` | Stable identity across reorder; stale handles rejected after disposal and transaction abort | Implemented |
| `UiNode` | Read-only parent/children/surface/properties; children keep explicit order | Implemented |
| `NodeProperties` and `Role` | Platform-free logical role, name, enabled | Implemented (minimal semantics) |
| `UiTree::transact` | Atomic clone/commit boundary; rollback on typed error | Implemented |
| `UiTransaction` | Open/close surface, append root/child, indexed child insert, reorder, edit properties, recursive remove | Implemented |
| `UiSnapshot` | Immutable, clonable Arc-backed snapshot; ordered roots and node lookup | Implemented |
| `UiCommit / SurfaceChange` | Global and independent surface revision; dirty ancestors and removed tombstones | Implemented |
| No-op behavior | Unchanged properties/reorder and empty transactions do not increment revisions | Implemented |
| Rejected handles | Failed transaction reservations cannot alias later committed nodes | Implemented |
| GPU/Window/F4 independence | No wgpu, winit, egui, F4 broker or archive donors used in package | Implemented (dependency graph checked) |

Generation reservations intentionally survive a failed transaction while the semantic tree is rolled back. This prevents leaked speculative handles from being accidentally resurrected by subsequent commits.

Structural operations flag the whole affected surface for safe downstream relayout. The current dirty set contains changed nodes and their ancestors only, **not** a complete minimal, diff-driven invalidation graph. A removed node is reported as a tombstone and excluded from dirty redraws.

## Evidence / commands

Run from this worktree root:

```sh
cargo fmt -p blobin-ui-core -- --check
cargo test --offline -p blobin-ui-core --all-targets
cargo clippy --offline -p blobin-ui-core --all-targets -- -D warnings
cargo tree --offline -p blobin-ui-core
cargo run --offline -p blobin-ui-core --example tree_transaction
cargo test --offline --workspace --lib
```

Results and command output are recorded in `evidence/runs/blob-ui-g02a-20261012/`. The final qualification JSON is the source of truth for exact observed counts.

## Explicit exclusions / limitations

1. **No declarative diff engine yet.** G02/A uses a complete `State` clone for atomic updates; snapshot construction is O(nodes). Profiling and persistent data structures belong to UI-G02/B.
2. **No general layout or hit tree yet.** A node is an ordered logical component, not a measured/paintable widget. No text shaping, clipping, transforms, input routing, keyboard focus, pointer capture or accessibility bridge yet.
3. **No custom state-store subscription engine.** Minimal semantic properties are transacted; reactive dependencies and fine-grained invalidation belong to UI-G02/B.
4. **No cross-tree identity assertion.** `NodeId` is scoped to its owning `UiTree`, not an interchangeable global handle.
5. **No live native UI migration.** Existing egui/`blobin_ui_lab` modules and CP03 integration are unchanged. The example proves a headless client, not UI-G07 external application independence.
6. No claim of 60 FPS, user interaction E2E, Wayland presentation feedback, portable renderer parity or CP03 HYBRID-60 completion.

## Next: UI-G02/B — Deterministic Diff & Targeted Reconciliation

- Define immutable updates with stable parent/child identity and generation-safe reconciliation.
- Move away from full-state cloning toward per-subtree copy-on-write while preserving atomic rollback.
- Add dependency tracking between property/state changes, measure/layout/render dirtiness.
- Compare full rebuild vs incremental recomputation using an independent subtree oracle.
- Test key collisions, equivalent-node no-op patches, cancellation, burst coalescing and two-surface epoch isolation.

**Gate decision:** UI-G02/A may be marked SCOPED PASS only after testing and a clean commit. UI-G02 overall, UI-G03..UI-G08 and CP03 remain OPEN.
