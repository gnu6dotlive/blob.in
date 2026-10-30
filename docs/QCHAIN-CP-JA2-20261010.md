# CP-JA2 — Feedback-driven shutdown qualification (bounded HOLD)

Date: 2026-10-10. Parent CP-JA `087f78362bd996b13251ea3e89cbe2092abb2509`.
Branch: `feat/qchain-feedback-driven-exit-20261010`.
Private experimental worktree only. No merge, push, deployment, resident service or Hyprland change.

## Causal investigation

The 120 freshly computed Vulkan frames and the sealed-memfd stream continue to present under an isolated Weston headless GL compositor. The precise discrepancy persists: **120 presentation feedbacks in the Weston server log, but only 119 consumed on the client**.

- **Trial A:** keep the winit event loop awake with repeated `request_redraw()` without new `present()` for 1100 ms. Outcome 119 client / 120 server; eight Weston capture samples exact. No clean shutdown.
- **Trial B:** additionally block on `wgpu::Device::poll(PollType::Wait)` and continue no-present redraws. Outcome 119 client / 120 server. GPU queue completion does not prove the last WSI presentation notification was dispatched to the app.
- **Prior CP-JA sentinel:** one additional presentation delivers the prior source feedback, producing 120 client / 121 server. The sentinel's own ACK remains undelivered.

These distinguish application render/surface progress, GPU queue completion and Vulkan/Wayland WSI feedback. They do not demonstrate a production-safe feedback drain.

## Strict fail-closed observer

`scripts/qchain_cpja2_feedback_gate.py` independently compares 120 source submission sequence identities, outgoing `wp_presentation.feedback`, client `presented`, and server `presented`. It refuses mismatched counts, reordered client/server records and discarded presentations. An outstanding final ACK yields a nonzero exit status, never PASS.

**Important trust boundary:** `WAYLAND_DEBUG` logs are mutable diagnostic text, not trusted typed callbacks. A deliberately appended, syntactically valid fake ACK can make such a log appear complete. Accordingly the gate *always* leaves `typed_app_feedback_received=false`, `production_ready=false` and `may_report_clean_shutdown=false`, even if diagnostic text appears complete. The only acceptable production gate is native typed feedback attributed to the actual Wayland/Vulkan presentation path.

Five adversarial/unit tests PASS, including the forgery demonstration and the no-sentinel/sentinel HOLDs. No static contract may be promoted from these observations. The failure of the first test fixture was itself detected: it appended a fake line through a symlink into the original `redraw-only/viewer.stderr`. The contaminated file was preserved as `oracle/contaminated-client.log`; exactly the injected final line was removed from the original, whose restored SHA-256 is `9c188470811025b9fca0622e0d697d4e464865aef4d12d38ab721d6ad88e1ff9`. After repairing the fixture to unlink the symlink before mutation, the suite passed and a before/after SHA check of the restored witness was identical.

## Verdict, evidence and next engineering choice

Private root: `/mnt/workbench/evidence/runs/qchain-cpja2-20261010-01/`.
- `experiments/redraw-only/` — trial A, original client/server trace and compositor captures.
- `experiments/device-poll/` — trial B, original client/server trace and compositor captures.
- `oracle/{redraw-only-gate,device-poll-gate,sentinel-gate}.json` — strict denial receipts.
- `oracle/contaminated-client.log` — preserved accidental adversarial fixture contamination.
- `scripts/test_qchain_cpja2_feedback_gate.py` — five cases, including forgery of an untrusted trace.

**Verdict:** `CPJA2_TYPED_FINAL_FEEDBACK_SHUTDOWN_HOLD`.

**Required CP-JA3:** identify whether the `wp_presentation` feedback objects originate in Vulkan WSI (as distinct from winit), then use a *typed* feedback channel or supported Vulkan presentation-wait feature. Verify this against independent Weston traces without a sentinel, with an explicit failure deadline. Until then no 120/120 **client-authenticated** claim, no CP03 HYBRID-60, no zero-copy, no physical display or production promotion.
