# BLOB-AC-03 — List cursor and keep-visible scroll

**State: SCOPED PASS (headless).** First consumer: Gnosix UXE-03, where the launcher's search field keeps focus and Up/Down move the current application row.

`blobin_ui_core::list` is pure policy. It owns neither the rows nor the painting.

- **`ListCursor`:** the current row of a list of `len` rows.
  - An empty list has no current row; any other list always has one.
  - `reset(len)` makes the first row current; consumers call it when the results change.
  - `step` moves by `Previous`, `Next`, `First`, `Last`, `PageUp` or `PageDown`. A page is at least one row.
  - `Ends::Clamp` stops at the ends. `Ends::Wrap` wraps single steps only; page steps still clamp.
  - `select(index)` refuses an out-of-range index. Every move reports whether the current row changed.
- **`UniformRows { extent, gap }`:** rows of one height, one gap between them.
  - `content_extent` has no trailing gap; `viewport_for(rows, len)` is the height that shows at most `rows` rows.
  - `keep_visible` returns the smallest scroll change that shows a row; a row taller than the viewport aligns to its top.
  - `row_at` hit-tests from the viewport top; a point in a gap or past the last row is no row.
  - `page` counts whole rows that fit, at least one.
  - A negative or non-finite height, gap, scroll or viewport counts as zero.

Tests: 11 in `tests/list.rs`, all passing; strict Clippy passes. Consumer receipts belong to the Gnosix side.
