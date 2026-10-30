# UI-G04/A — Headless Input Routing and Focus · 2026-10-12

Baseline: `5cf1ece` on private canonical `main`.

## Scoped delivery

`crates/blobin-ui-core/src/input.rs` introduces typed host-stamped pointer and keyboard events, logical/physical pixel normalization, fail-closed layout/resize/DPR/epoch checks, serial and timestamp ordering, clip-aware reverse-paint hit testing, capture/bubble route lists, pointer capture/release/cancel, focus traversal, repeat suppression, and window-blur teardown. Surfaces retain independent focus, pressed keys and pointer captures.

The headless `input_workbench` example verifies a click and a keyboard activation. The 19 new `input_routing` tests include stale IDs, overlapping nodes, nested clipping, physical-to-logical DPI, button identity, exactly-once activation, pointer-outside drag, cancel/blur, focus order, duplicate serial rejection, stale epoch/scale/resize, and two-window isolation. The preceding 46 tests remain green.

## Verdict boundary

**UI-G04/A SCOPED PASS** requires a passing receipt from `scripts/blobin_ui_g04a_verify.py`, strict lint, independent source examples and workspace library regression. This is a headless contract, **not** a native Wayland E2E.

**UI-G04/B HOLD**: no real compositor-delivered pointer/keyboard trace or independent physical injection-to-receipt count is provided in this gate. The existing `blobin_ui_lab` is egui-bound and has no qualified adapter to this new event router yet. Do not call UI-G04 FULL PASS, real pointer E2E, GPU frame presentation, 60 FPS or CP03 HYBRID-60 PASS.

## Next acceptance

UI-G04/B needs a **native Wayland consumer** connected to this input router, compositor-delivered pointer and keyboard events, independent origin/receipt counting, pointer capture after resize and focus loss, and explicit proof of exactly one physical input producing one expected semantic activation. Preserve the measured E2E traces and screenshot/geometry hashes. Only then promote FULL UI-G04.

All code and local proof shall be committed and pushed to `main`, no orphan branch and no GitHub Actions tests.
