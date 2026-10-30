# QCHAIN CP-H — Independent Integration & Runtime Hardening

Date: 2026-10-10. Parent: CP-G 127fc160. Branch: feat/qchain-gpu-runtime-hardening-20261010.
Scope: isolated private CP-H checkpoint. No merge, push, deploy or resident changes.

## Rebuild

Git archive of CP-G extracted without .git, offline locked Cargo build into distinct target.
Baseline: 20/20 transport unit tests and 2/2 canonical evidence tests PASS.
Initial missing QCHAIN_EVIDENCE_ROOT environment was corrected and preserved in logs.
Same host and operator: NOT an external independent auditor.

## Transport hardening

- Checked scene_revision + 1 overflow, rejects u64::MAX without panic.
- Five-second bounded packet receive timeout on GPU source and client.
- Exactly one sealed memfd of 786432 bytes required; missing, extra, unsealed, truncated and oversized descriptors rejected.
- Source verifies actual CP-F Vulkan log and CPU canonical receipt SHA-256 before socket binding.
- All five scene epochs, source scene identities and semantic digests tied to canonical ledger.
- Source commit pinned; local hashes are NOT signed GPU hardware attestations.
- Blocking accept remains; no watchdog or unattended auto-restart was added.

## Executed tests

| Check | Observation |
|---|---|
| Hardened Rust unit and evidence tests | 31/31 + 2/2 PASS |
| Clippy all targets with warnings denied | PASS |
| Three fresh source process runs | 15/15 GPU-buffer IPC receipts PASS |
| Intentional early disconnect | Source refuses, exit nonzero |
| Fresh restart after disconnect | 5/5 PASS |
| Corrupted Vulkan compute log | Rejected before socket binding |
| Corrupted CPU canonical receipt | Rejected before socket binding |
| Prior CP-G compositor oracle tests | 5/5 PASS on archived evidence |
| New CP-H native GPU-viewer submissions | 5/5, both processes exit 0 |
| New CP-H independent Hyprland capture | HOLD, 0 accepted captures |

## Evidence, limits and next

Private root: /mnt/workbench/evidence/runs/qchain-gpu-hardening-20261010-01/
Key files: independent-build/baseline-test-with-fixture.log; fault-tests/rust-full-final2.log;
fault-tests/clippy.log; recovery-verdict-final.json; receipt-negative-gate/result.json;
wayland/capture-reconciliation.json.

The CP-H GPU viewer submitted five frames; the capture gate correctly refused them because
Chrome remained the active window. No user window focus was stolen, and NO new CP-H capture PASS.
The earlier GPU-source Wayland five-capture PASS remains CP-G-specific and is not promoted.
Restart tests replay already-computed GPU buffers, not GPU kernel execution after restart.

Full 17 adversarial laws, external auditor, sustained FPS/p99, driver tracing, zero-copy,
CP03 HYBRID-60, cross-vendor and photon evidence remain OPEN.

Bounded verdict: QCHAIN_CPH_TRANSPORT_HARDENING_RESTART_PASS_WAYLAND_CAPTURE_HOLD.
Next: active-window observation when non-disruptive, supervisor-qualified full GPU engine restart
and sustained runtime measurements. No public promotion.
