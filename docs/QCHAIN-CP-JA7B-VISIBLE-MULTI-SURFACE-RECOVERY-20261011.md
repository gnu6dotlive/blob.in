# QCHAIN CP-JA7B — Visible Multi-Surface Recovery

**Date:** 2026-10-11
**Parent:** CP-JA7 `a164603adfd40b7132c9e9d7c4f7b0889349ae94`
**Scope:** private NVIDIA RTX 3070, Weston 15.0.1 headless GL/desktop-shell, 512×384 Vulkan-backed wgpu surface pair.
**Decision:** **SCOPED PASS** — compositor-visible primary/secondary surfaces and recovery after secondary teardown, with the CP-JA5/JA6 typed Vulkan wait path enabled. This is **not** a full Vulkan device recovery or a CP03 HYBRID-60 PASS.

## Goal and experiment boundary

CP-JA7 qualified two distinct Vulkan swapchain generations on one logical device, but Weston kiosk occluded a window. Its presentation ACKs did not prove that both windows were visually distinct or that closing the secondary restored visible output. CP-JA7B closes this visibility gap.

The execution is strictly isolated: private Weston socket, private source-broker socket, test-owned compositor module, test-scoped GPU streams. Hyprland, live shell processes, resident services, production binaries, deployment and the global Wayland socket are not modified. No merge or push in this qualification.

## Environment and reproducible setup

- Viewer: `crates/showcase/src/bin/qchain_cpja7_dual_viewer.rs`, with only the secondary render-pass scissor modification: the leftmost 16 pixels are black, while the primary preserves the canonical GPU frame; both use the **same** authenticated source frame and logical device.
- **Required feature:** `--features cpja5-present-wait`. This activates the CP-JA6 `CPJA6_TYPED_ACK` witness; an ordinary feature-off viewer is *not* a valid CP-JA7B typed-wait test.
- Weston shell: `--backend=headless --renderer=gl --shell=desktop --width=1536 --height=1024 --no-config --idle-time=0 --debug`.
- Test placement module: `tests/cpja7b/tile_views.c`, built for `libweston-15`. Filters mapped 512×384 views by same UID and process executable path ending in `/qchain_cpja7_dual_viewer`, then positions the primary at `(92,190)` and the secondary at `(810,190)`. Both compositor coordinates are interpreted after Weston-declared Y-flip in the screenshot oracle.
- Capture: `weston-screenshooter` on the isolated compositor socket. The expected image is **1536×1024**; the oracle compares two **512×384** regions, not the entire screenshot against an individual frame.
- GPU source: `qchain_cpi02_gpu_live`, transported through sealed-memfd Unix SEQPACKET; the canonical eight state-4 F4 RGBA buffers remain read-only from the prior GPU evidence.
- Color bound: `max(abs(actual_rgb - canonical_rgb)) <= 3` **per channel**, observed on this Weston GL setup only, with **alpha equality**. This is not a global tolerance and does not weaken the source/memfd SHA-256 identity. Observed compositor captures range from pixel-exact to a maximum delta of `[2,2,3,0]`.

Build the local isolated viewer, then copy the resulting binary under its **original basename** before running:

```sh
CARGO_TARGET_DIR=/mnt/workbench/build/qchain-cpja7-archived-20261010 \
  cargo build --offline -p blobin-showcase --bin qchain_cpja7_dual_viewer \
  --features cpja5-present-wait

cc -std=gnu11 -O2 -fPIC -shared \
  $(pkg-config --cflags libweston-15) tests/cpja7b/tile_views.c -lm \
  -o /path/to/private/tile_views.so
```

The placement module is deliberately executable-name-sensitive. A preflight using a renamed, typed-capable binary was rejected for **missing placement**; its overlapping-window capture and absence of PASS receipt were preserved. Restoring the required basename caused the same typed viewer to pass. Weston Lua shell was independently found unsuitable here because it crashed even on minimal scripts; the native desktop shell is used instead.

## Verified test scenarios

| Scenario | Source frames | Primary typed Vulkan ACK | Secondary typed Vulkan ACK | Per-surface Wayland feedback requests | Server `presented` / `discarded` | Screenshots |
|---|---:|---:|---:|---:|---:|---:|
| Typed dual-visible | 120 | 120 | 120 | 120 / 120 | 240 / 0 | 8/8 |
| Typed secondary drop after frame 59 | 120 | 120 | 60 | 120 / 60 | 180 / 0 | 8/8 |
| Rebuilt Weston module + typed secondary drop | 120 | 120 | 60 | 120 / 60 | 180 / 0 | 8/8 |

The primary has frames `0..119`. The secondary has frames `0..119` in the dual test and `0..59` in the drop test. Two Vulkan swapchain generations are observed in each typed run. Their typed `VkPresentIdKHR` ACKs are consecutive, generation-local and all report `VK_SUCCESS`. Client and server Wayland `presented` records reconcile with no discard and no unresolved feedback in these **typed** runs.

In the drop trials, the private placement module observes `count=2 -> count=1` with the same primary Wayland resource. Four sampled frames before teardown show *both* windows simultaneously and independently, including the secondary 16px signature. Four later screenshots show the primary still matching the corresponding F4 reference and the secondary no longer present. A second composition test uses a Weston module **rebuilt from source** and reaches the same result. Positive dual run images cover all eight canonical F4 variants.

**Important:** Some compositor samples are byte-exact, but strict pixel equality is **not** universally established; do not report all sampled compositor pixels as SHA-exact. The source buffers and their cryptographic identities are exact, while rendered captures have an independently measured RGB bound.

## Oracle, counterexamples and artifact provenance

The production test runner is `scripts/qchain_cpja7b_visible_run.py`. Its PASS path requires source-stream continuity, canonical SHA-256 correspondence, correct compositor dimensions and coordinates, visually distinct surfaces, secondary release, consecutive typed Vulkan ACK per generation, per-surface Wayland feedback requests, bounded server outcomes, and compositor view-count transitions.

A **separate implementation**, `scripts/qchain_cpja7b_independent_oracle.py`, reads the stored bytes/PNG/Wayland logs and recomputes these results without importing the producer runner or trusting its PASS label. `scripts/test_qchain_cpja7b_oracle.py` applies seven changes to **temporary copies**, requiring rejection of each:
1. RGB drift exceeding three levels;
2. artificial reappearance of the secondary after close;
3. identical/superposed surface content;
4. removal of source sequence frame 119;
5. removal of Weston `count=1` mapping evidence;
6. missing typed secondary ACK;
7. removed compositor feedback event.

All **7/7** negative mutations were rejected. `blob-frame` also passed **31/31** local Rust unit tests. The official positive scenarios were independently verified against F4 canonical references.

Evidence root: `/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01/`

- `runs/typed-visible-positive-20261011b/` — two visible surfaces, 120/120 typed ACK per generation.
- `runs/typed-visible-drop-20261011b/` — secondary release after frame 59.
- `runs/typed-source-rebuild-drop-20261011/` — new Weston module compiled from the committed C source.
- `oracle/` — independent verdicts, not written by the runner.
- `preflight/` — typed viewer build output, module source-rebuild output, Rust tests, SHA-256 witnesses.
- `runs/typed-visible-positive-20261011/` — **archived expected HOLD**, typed binary renamed and therefore intentionally not recognized by the placement module.
- `runs/desktop-visible-*-20261011/` — previous geometry and window-behavior pilot runs made without the typed Vulkan HAL feature. Useful as observations; **not** counted toward the combined typed gate.

## Acceptance matrix

| Gate | Status | Witness |
|---|---|---|
| A: isolated real Weston desktop | PASS | private socket, private process, controlled module |
| B: two compositor-visible views | PASS | separate F4 pixels and black-edge secondary signature |
| C: typed per-swapchain Vulkan wait | PASS | generation-local 120/120 and 120/60 ACK streams |
| D: compositor presentation observed | PASS | client/server per-surface feedback reconciled |
| E: secondary close, primary remains | PASS | mapped views 2 → 1, later primary F4 pixels correct |
| F: independent oracle and adversarial negatives | PASS | separate oracle, seven fail-closed mutations |
| G: test-module source rebuild | PASS | second typed recovery run with rebuilt libweston module |

## Explicitly **not** qualified

- `VK_ERROR_DEVICE_LOST` injected into the running Vulkan device, loss poisoning, reinitialization and recovery: **CP-JA7C OPEN**.
- Several Vulkan presentations genuinely in flight: **OPEN**, because the current HAL synchronously waits per present.
- CP03 HYBRID-60, measured sustainable 60 FPS, GPU→Wayland zero-copy, physical display photons: **OPEN**.
- AMD/Intel and other compositors/hosts: **NOT EXECUTED**.
- Desktop-shell exit cleanup and the unusual Weston layer teardown warnings are not a product-lifecycle certification.
- This is not a warrant to deploy, merge upstream, publish performance claims or modify the resident Gnosix runtime.

**Handoff:** advance to CP-JA7C with controlled, private Vulkan device-lost fault injection and a fail-closed restoration contract. Retain the original CP-JA7 multi-swapchain authority, the typed CP-JA7B visual oracle, and the source-rebuild replay as regression baselines. Never substitute a Wayland disconnect for a real Vulkan `VK_ERROR_DEVICE_LOST`.
