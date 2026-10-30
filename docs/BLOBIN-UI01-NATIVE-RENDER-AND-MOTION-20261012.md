# blob.in / UI01 — Native 2D interface engine and motion foundation

Date: 2026-10-12. Base CP03-I01 preflight `dcdee4fc50c74f80482d437cd774ba976608c9f5`.

## Product decision and gate boundary

**Priority:** native GPU-accelerated 2D interfaces, genuinely interactive layouts,
motion design, reusable primitives and inspectable frame/input state.
The 3D renderer remains an **OPTIONAL FUTURE CAPABILITY**; it does not block
2D UI platform development. The previously ratified CP03 HYBRID-60 contract
is **OPEN and deferred**, not weakened, declared obsolete or falsely passed.
Future UI throughput qualification must have a separate scene and metric gate.

The standalone `blobin_ui_lab` has no dependency on a running
F4 broker, no Electron/web runtime, and uses winit + Wayland + wgpu
Vulkan + egui's GPU tessellation path. This is a **native vertical slice**,
not a production-ready general-purpose retained UI toolkit.

## Implemented source

- `crates/showcase/src/ui_motion.rs`: reusable typed UI action/revision
  state, bounded semi-implicit spring animation, reduced-motion mode,
  motion enable/disable, selectable surface and responsive panel layout.
- `crates/showcase/src/ui_widgets.rs`: authored native 2D components,
  96–128-point organic vector geometry animated each frame, layered glows,
  interactive rail, responsive canvas, animated inspector and timeline.
- `crates/showcase/src/bin/blobin_ui_lab.rs`: standalone Vulkan Wayland
  window, input processing, resize handling, repaint-on-motion,
  lifecycle and typed JSONL tracing, safe bounded `--probe-frames`.
- `scripts/blobin_ui01_run.py`: private Weston headless executable
  smoke, four independently obtained compositor screenshots, 180 frames,
  six deterministic test actions; restores screenshot bottom-up
  orientation to an upright view.
- `scripts/blobin_ui01_oracle.py`: verifies real NVIDIA Vulkan adapter,
  correct typed state revisions, screenshot bytes and changing pixels;
  explicitly forbids claiming WP presentation and 60FPS.
- `scripts/test_blobin_ui01_oracle.py`: independently rejects 7/7
  altered evidence and fraudulent readiness claims.

## Run interactively

```sh
cd /home/tension_atoi/Projects/.worktrees/blobin-showcase-ui01-20261012
cargo run --offline -p blobin-showcase --bin blobin_ui_lab
```

In an ordinary local Wayland session, mouse input selects the rail/surface,
toggles inspector/animation, and the center button changes focus.
Keys: Space toggles animation, R toggles reduced motion, I toggles
inspector, Escape exits. The app is separate from the F4 engine and broker.

For a bounded private diagnostic run, use the evidence runner with an
already built executable, a fresh empty root and `--frames 180`.
The run will open a real native Wayland window in an isolated compositor.

## Actual qualification

180 native wgpu/Vulkan submissions on NVIDIA RTX 3070 in a private
Weston headless desktop, with 4 independent real compositor PNG captures
1536×1024, six state actions and changing pixels between captured frames.
20/20 `blobin-showcase` Rust library tests PASS (six new motion tests),
Clippy `-Dwarnings` PASS for the native lab binary.
An independent oracle recomputed screenshot SHA256, dimensions and
ROI pixel differences. Seven adversarial mutations were rejected.

**Not demonstrated:** manually or robotically executed pointer clicks,
user-driven accessibility and keyboard navigation audit, `wp_presentation`
typed feedbacks, latency from input to light, 60 FPS sustained,
independently qualified anti-alias parity, long-running memory stability,
production readiness or real 3D geometry. No GPU device reset.

## Subsequent bounded roadmap

**UI02 — Component substrate:** reusable 2D display tree with stable node
IDs, hit-test/layout metrics, clipping, text shaping, transforms and
separately testable input dispatch; retain true interactive provenance.
**UI03 — High-fluidity composition:** GPU-native vector paths, retained
resource caching, transitions/gesture physics, damage-driven repaint,
virtualized lists, scalable typography and accessibility support.
**UI04 — Renderer and distribution gate:** native multi-surface compositor,
input→frame→Wayland presentation evidence, cross-resolution screenshot
oracle, sustained cadence and constrained resources. Establish a
separate `BLOBIN-UI-60` workload and pass gates before any FPS claims.
**3D optional:** a capability backend with its own geometry and resource
contracts; deferred while UI02–UI04 mature.

Original CP03 HYBRID-60 remains deferred/OPEN. No push, merge,
production deployment or interference with resident Hyprland.
