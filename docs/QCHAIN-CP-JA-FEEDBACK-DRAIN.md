# CP-JA — Final presentation feedback drainage

Date: 2026-10-10. Parent: CP-J d29159d0bd52ab289e1147fb0b257d35e16669bf.
Branch: feat/qchain-feedback-drain-20261010. Local test only, no production promotion.

## Diagnosis and executed trials

The CP-J original viewer submitted 120 genuine GPU frames and Weston
confirmed 120 presentation events but the client dispatched only 119.
The original 300 ms no-op drain failed to receive the 120th.

Trial 1 — acquire and drop one unpresented WGPU surface texture during
the drain. PASS for source frames and native captures, but only
119/120 client-received presentation events. This hypothesis failed.

Trial 2 — explicitly submit one final sentinel presentation containing
the existing last verified texture, without generating a 121st
source GPU frame or claiming another canonical scene identity.
The source GPU frames remained 120/120 and the application logged
the sentinel distinctly: CPJA_SENTINEL_PRESENT.
Weston recorded 121 presentations and the client dispatched 120
wp_presentation_feedback.presented events, corresponding in order
to the 120 genuine GPU-source sequences 0 through 119.
The sentinel's own feedback was not dispatched before shutdown.

This experiment demonstrates that a subsequent surface presentation
unblocks delivery of the preceding presentation feedback. It does not
prove that a generic client event queue can be drained completely,
nor that the terminal sentinel is safe for a production runtime.
## Qualification and limitations

Exact source witness: 120 freshly computed Vulkan frames, 120 sealed
memfd IPC receipts, 120 genuine wgpu presentations. Weston samples
continue to be verified by the existing 8-capture CPI02 oracle.

Evidence root: /mnt/workbench/evidence/runs/qchain-cpja-20261010-01
- runs/feedback-01/ — failed acquire/drop without presentation
- runs/sentinel-01/ — final sentinel and client/server protocol logs
- oracle/terminal-sentinel.json — independent sequence attribution
- preflight/ — compilation, Clippy, Rust test output

Bounded verdict:
CPJA_SOURCE_120_OF_120_CLIENT_FEEDBACK_PASS_SENTINEL_OWN_ACK_HOLD.

No GPU hardware timestamps, physical photons, 60 FPS, zero-copy,
cross-vendor, full G06 qualification or CP03 HYBRID-60 PASS.
The sentinel repeats the previous image; it is not new GPU output.

Next: replace the terminal sentinel with an actual event-loop/Wayland
presentation state machine whose completion condition is a received
feedback for every genuine frame; test closing without an extra
presentation if supported by the windowing stack.
