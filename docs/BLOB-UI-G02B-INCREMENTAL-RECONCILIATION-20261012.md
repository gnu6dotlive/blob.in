# BLOB-UI-01 / UI-G02/B — Incremental Reconciliation Qualification

Date: 2026-10-12
Branch: **main** (canonical integration, no new permanent research branch)
Baseline: GitHub-backed commit `489cb9f`
Status: **SCOPED PASS only if the recorded verifier exits 0; see evidence**

## Goal and implemented design

Retain the UI-G02/A public interface while eliminating full-node graph cloning on each transaction and snapshot, introducing keyed child reconciliation, and reporting domain-specific invalidation without tying the core to egui, Wayland, wgpu, F4 or the archived GPL donor.

The new `State` uses a `Vec<Arc<Page>>` with **64 slots per page**, `Arc::make_mut` only for edited pages, `Arc<BTreeMap<SurfaceId, Surface>>` for surface state, and a persistent Arc-backed free-slot linked stack. Cloning the transaction workspace or snapshot copies shared pointers, rather than every `UiNode`.

A snapshot holds its immutable state, so holding pre-transaction snapshots still returns the old node values and old surface epochs. A single leaf property change in a 1,024-child fixture copies **one** page, proven using pointer-identity diagnostics. This is **page-granular copy-on-write, not full O(1) persistent updates**: cloning the page-reference vector remains O(number of pages); a changed page clones up to 64 slots. The surface map uses copy-on-write at map granularity.

## Public API extensions

| API | Contract |
|---|---|
| `KeyedChild::new(key, properties)` | Stable sibling key; duplicate and empty keys fail atomically |
| `UiTransaction::reconcile_children(parent, &[KeyedChild])` | Preserve matching NodeIDs/subtrees; deterministic insert/delete/reorder/property updates; remove unkeyed children when replacing keyed list |
| `ReconcileReport` | Counts direct child retained/inserted/removed/moved/updated; not renderer draw calls |
| `UiNode::key()` | Optional read-only keyed identity; original imperative APIs produce `None` |
| `UiSnapshot::shared_pages_with`, `page_count` | Read-only diagnostics for COW qualification, no mutable internals |
| `UiSnapshot::surface_epoch` | Monotonic lifetime identity across close/reopen and failed open transactions |
| `SurfaceChange::surface_epoch` | Typed epoch attribution for final open surface |
| `SurfaceChange::damage` | Direct `NodeDamage` hints: semantics, layout, paint, child-structure; distinct from existing dirty ancestor set |

Existing `UiTree` methods, `UiSnapshot::get`, `SurfaceChange::dirty/removed`, `UiCommit`, generations, transaction rollback and per-surface revisions are retained. All edits produce one atomic revision per transaction, independent of the number of edits in that transaction.

## Gate evidence

The verifier `scripts/blobin_ui_g02b_verify.py` runs reproducible local commands, captures stdout/stderr and SHA-256 checksums to `evidence/runs/blob-ui-g02b-20261012/`:

1. `cargo fmt -p blobin-ui-core -- --check`
2. `cargo test --offline -p blobin-ui-core --all-targets` — expects **at least 32 passing direct tests**
3. `cargo clippy --offline -p blobin-ui-core --all-targets -- -D warnings`
4. `cargo tree --offline -p blobin-ui-core` — verifies std-only runtime package
5. `cargo run --offline -p blobin-ui-core --example tree_transaction`
6. `cargo test --offline --workspace --lib` — expects at least **51 passing library regression tests**

Incremental independent oracle: **400 deterministic reconciliation mutations** compared against a reconstructed full key/label model. Additional tests: key retention including grandchildren, reorders, duplicate/empty key rejection, full rollback, 1,024-node COW sharing, 200-key no-op diff, paint-only vs layout invalidation, 100-update single-revision burst, deletion tombstones, separate surface isolation, monotonic epochs after close/reopen and aborted open. The older **600-step** adversarial transaction replay is retained.

## Disclosed limitations

- The keyed reconciler handles **immediate children per call**, not a recursive declarative widget-builder DSL; higher-level recursive reconciliation is not yet qualified.
- Reconciliation still constructs temporary `BTreeMap`/`BTreeSet` sibling indexes and computes a complete direct-child order. This is not an O(changes-only) patch algorithm for extremely large sibling lists.
- The 64-slot page allocation is fixed, free slots reuse ID slots with globally increasing generations, and pages are not compacted; allocator pressure, long-term fragmentation and cross-thread concurrency need explicit profiling.
- `damage` is a typed domain hint per directly changed node, **not a complete observable dependency/subscription graph** or a guarantee that the final renderer will redraw only that region. Child changes carry a structural flag, and the `dirty` set includes ancestors for safe traversal.
- No independent wgpu display-list, constraint layout, hit tree, compositor-delivered pointer E2E, accessibility bridge, GPU presentation feedback, 60/120 Hz claim or 3D runtime is implemented by this gate.
- CP03 HYBRID-60 remains unchanged and **not PASS**. No historical GPL donor code is copied, and no GitHub Actions runner is invoked.

## Handoff

If `evidence/runs/blob-ui-g02b-20261012/qualification.json` reports `SCOPED_PASS`, mark **UI-G02/B scoped complete**, but not the whole native UI engine. The next dependency is **UI-G03 — deterministic constraint-based layout with scale/resize and clip propagation**. Integrate on `main`, test and push. Keep the repository private and authoritative.
