# BLOB-AC-02 — Axis lock for gestures

**State: SCOPED PASS (headless).** First consumer: Gnosix UXE-02, where a notification toast swipes horizontally to dismiss and drags vertically to expand.

`blobin_ui_core::gestures::AxisLock` is a pure policy applied by the consumer to the `Translation`s of one gesture. It does not route input and does not change the `GestureCoordinator`.

- **Inside the slop:** the projection is zero and nothing is locked, so a jittery press neither swipes nor scrolls.
- **First translation longer than the slop:** this locks the dominant axis. Ties lock horizontally.
- **Once locked:** the off-axis component stays zero until `reset()`.
- **Invalid slop:** a non-finite or negative slop becomes 0.

Tests: 3 new tests in `tests/gestures.rs` (13 in total), all passing; strict Clippy passes. Consumer receipts belong to the Gnosix side.
