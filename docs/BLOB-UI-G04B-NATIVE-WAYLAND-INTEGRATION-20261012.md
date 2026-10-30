# UI-G04/B — Native Wayland Input Integration · 2026-10-12

**Verdict:** Native window/Vulkan submission **SCOPED PASS**; compositor-delivered mouse/keyboard E2E **HOLD**. Consequently, **UI-G04/B FULL PASS is not ratified**.

**Source baseline:** `fcff81e`, main/private GitHub `tension-atoi/blob.in-showcase`.

## Implemented native bridge

- `crates/showcase/src/bin/blobin_ui_g04b_wayland.rs`: a separate, native winit Wayland consumer of the `blobin-ui-core` tree, G03 layout and G04/A input router.
- Owns a native wgpu Vulkan swapchain, a tiny WGSL 2D-rectangle shader and two labeled-in-state targets (left/right). It is a **qualification fixture**, not the final product design.
- Converts compositor-generated winit `CursorMoved`, `MouseInput`, `KeyboardInput`, `ModifiersChanged`, `Focused(false)`, `Resized` and `ScaleFactorChanged` into typed host events.
- Distinct JSONL `ingress` and `receipt` events include serial/epoch, route target, focus, capture and activation. `WindowEvent::Focused(true)` is traced separately; synthetic headless unit inputs never masquerade as native.
- Uses real window DPI to convert physical pointer to logical hit coordinates, a geometry epoch on resize/scale, a live G03 layout snapshot, and a bounded `--run-ms` command-line probe.
- Normal Vulkan backend is primary. The `BLOBIN_G04B_ALLOW_GL` opt-in is limited to RDP experiments; this installed wgpu build reports GL support not compiled in. RDP Weston with a GL compositor nevertheless presented a Vulkan-compatible WSI surface.

## What was observed

1. A **private Weston headless** compositor started the built binary, winit created a Wayland window, backend reported `Vulkan`, and at least one GPU frame was submitted. The native trace recorded **0 compositor mouse/keyboard events**, as expected for a headless compositor without an input device. The actual submission is **not independent presentation feedback**.
2. An **isolated network namespace** (`unshare -Urn`, loopback only) was successfully created. Weston VNC could not load its backend because `libneatvnc.so.1` and `libaml.so.1` are absent.
3. Weston RDP with Pixman created a compositor, but wgpu could not obtain a Vulkan-compatible surface. Switching Weston RDP to **GL renderer** fixed native Vulkan startup and enabled frame submission.
4. A headless FreeRDP3 input client built successfully from `scripts/blobin_ui_g04b_rdp_inject.c`, but **did not connect**: initial NLA negotiation required credentials absent from the lab; TLS-only, RDP-classic with combined TLS keys, and RDP-classic-only negotiation attempts also failed (four independent transport attempts). The RDP-Weston client never received a pointer or keyboard event. No password/account modifications or desktop input injection occurred.

Result: the E2E requirement `remote transport injected → Weston seat → Wayland → winit WindowEvent → G04/A route → expected exactly-once activation` remains **unproven**. Generated test-only TLS keys are outside the repository at `/mnt/workbench/evidence/runs/blob-ui-g04b-20261012-01/`, **not committed**.

## Reproduce local qualification

```sh
python3 scripts/blobin_ui_g04b_verify.py
cargo run --offline -p blobin-showcase --bin blobin_ui_g04b_wayland -- --trace=/tmp/g04b.jsonl --run-ms=5000
```

The first command runs bounded private Weston headless smoke, strict rustfmt/clippy, offline native build, UI-core tests and workspace library regression. The second command needs a Wayland compositor; it is not an automated physical-input qualification. Optional RDP lab helper `scripts/blobin_ui_g04b_rdp_e2e.py` must run **inside** a private network namespace and cannot be interpreted as a PASS unless an authenticated RDP client delivers countable real winit events. Its default script exits nonzero for absent input.

**Remaining gate:** prove at least two distinct native pointer targets, keyboard focus/activation, cancel/blur, resize-stale event invalidation and independent input/route counts. An isolated RDP transport would demonstrate **compositor-delivered virtual-device inputs**, not physical HID presses; physical hardware provenance would remain separate.

**Non-claims:** no framebuffer/presentation feedback oracle, compositor click E2E, production-grade visual controls, full UI-G04 PASS, steady 60/120 FPS or CP03 HYBRID-60 PASS.

**Integration policy:** integrate this bounded, truthful result on `main`, push to private GitHub, do not create another orphan worktree. Resume the RDP security negotiation gate or acquire a suitable isolated input-capable compositor before G04/B completion.
