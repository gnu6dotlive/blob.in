# QCHAIN CP-I01 — Native Presentation Truth (isolated Weston)

**Date:** 2026-10-10. **Parent:** CP-H2 commit `6389c64`.
**Implementation branch:** `feat/qchain-native-presentation-20261010`.
**Scope:** independent Wayland compositor capture of five *precomputed, GPU-origin* canonical frames. Private, local and bounded.

## Execution and authority

The experimental source reads the five canonical RGBA buffers freshly produced by the
CP-H2 20th Vulkan cycle (F2→F3→F4 on the RTX 3070), and validates the CP-F
compute log + CPU original receipt. The GPU-source protocol remains
`QCHAIN-GPU-FRAME-v1`: Unix SEQPACKET, same-UID check, exact sealed memfd and
SHA/epoch/semantic-scene binding.

A separate **Weston 15 headless GL compositor** was started using its own
private `WAYLAND_DISPLAY` socket and kiosk shell at 512×384. Its GL renderer
identified the NVIDIA RTX 3070. The regular user's Hyprland socket, Chrome
focus, global configuration, and resident processes were not touched.

Weston's output capture initially returned `unauthorized`, despite a zero
exit code. That screenshot was **not** accepted. A replacement *isolated*
headless Weston was launched with `--debug` solely to enable the
screenshooter protocol. This is not a production-safe setting and was
never enabled for the user's normal compositor.

## Pixel oracle

Weston's own startup log declares `screen capture uses y-flip: yes`.
The independent oracle authorizes **only this documented coordinate
normalization** (vertical flip of the screenshot) before comparing each
pixel to the original sealed-memfd GPU bytes. No arbitrary geometric
transforms, corner masks, perceptual metrics, or color tolerances.

Two independent five-frame presentation/capture runs completed:
`run-01` and `run-02`. Each submitted five frames through wgpu/Vulkan
and captured five 512×384 Weston screenshots. After the compositor-declared
y-flip, **5/5 exact byte parity per run**, totaling **1,966,080 checked
pixel positions** across both runs, with **zero pixel mismatches**.

The five distinct scene identities are corroborated by CPU scene SHAs,
semantic digests, manifest, IPC transmit/receive receipts, Wayland
submission logs, and capture PNGs. Source images themselves have
only three distinct pixel identities; the oracle does not infer scene
identity from the pixel bytes.

Five independent negative-control tests PASS: positive witness, refusal
when the compositor flip declaration is missing, centrally corrupted
screenshot, substituted same-pixel scene identity and falsified GPU compute
log hash.

## Evidence and verdict

Private evidence root:
`/mnt/workbench/evidence/runs/qchain-cpi01-20261010-01/`.

- `headless/weston-debug.log`: backend, GPU, output and y-flip declaration.
- `headless/run-01/`, `headless/run-02/`: source/viewer logs and five
  captured PNGs each.
- `headless/independent-qualification.json` and
  `headless/independent-qualification-run02.json`: byte-level oracles.
- `headless/adversarial.log`: controlled negative cases.
- `inventory/cpl-static-inventory-v2.json`: separate CP-L read-only audit.

**Bounded verdict:** `QCHAIN_CPI01_HEADLESS_WESTON_5_FRAMES_NORMALIZED_PIXEL_EXACT_PASS`.

**Important non-claims:** GPU→CPU readback→sealed memfd→presenter GPU reupload
remains; **not zero-copy**. This is an independent compositor screenshot,
not observation of physical display photons. Weston headless is a second
compositor, not a repeat of the operator's Hyprland environment. The
viewer presented five staged frames, **not a continuously computed 60 FPS
stream**; CP-I02 and CP03 HYBRID-60 stay OPEN. Hardware GPU timestamps,
persistent live presentation and cross-vendor tests remain NOT_RUN.
