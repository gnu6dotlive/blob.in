# CP-JA7J-B — Sealed-memfd ownership intervention (subexperiment)

2026-10-12. Preregistered before the first client-copy intervention.
Independent subexperiment to CP-JA7J-A's 2×2 broker factorial.

## Hypothesis
Current viewer computes SHA256 of the immutable sealed memfd mapping, then
performs a redundant `MappedFrame::bytes().to_vec()` CPU copy before wgpu
texture upload. Replace the extra CPU copy with ownership transfer of
`MappedFrame` across the Rust channel. The sealed read-only mmap lives
until the draw consumes the bytes; `wgpu::queue.write_texture` still
copies to GPU staging. Do NOT claim GPU or IPC zero-copy.

## Bounded design
- Opt-in feature `cpja7j-mmap-consumer` exposes one viewer binary accepting
  `CPJA7J_CLIENT_PIXELS=copy|mmap`. Both paths keep SHA256, UID check,
  sealed memfd check, canonical stage verification and GPU timestamps.
- Four independent native 1200-frame E2Es under single viewer SHA:
  `client-copy-a`, `client-mmap-a`, `client-mmap-b`, `client-copy-b`.
- Same engine SHA, broker 64KiB pipe, zero canonical reference cache,
  16ms requested interval, balanced Vulkan wait profile.
- All four must have 1200 source F4 frames, 2400 actual typed Vulkan ACKs,
  2400 Weston presented, 4800 genuine GPU timestamp query ticks,
  eight compositor captures, 1200 SHA256 client checks.
- Host `integrity_copy_us` is an aggregate including SHA256 and
  copy-if-enabled: any improvement must not be described as a pure memcpy
  duration. Measure paired A/B medians and p99 as well as throughput.
- Safety remains <75°C, <180W, wall <100 seconds with >=15 NVIDIA
  samples; no fan/clock overrides, physical GPU reset or Hyprland change.
- Two mirrored trials per mode; independently hash exact binaries and
  verify per-frame pixel hash, native receipts, GPU queries and screenshots.
- Adversarial tests reject missing pixel-mode witness or contradictory
  mode and any altered F4 or Wayland evidence.
- Preserve old `cpja7i-gpu-timestamps` build and 31 Rust blob-frame tests.

## Fail-closed limits
Opt-in compilation and a separate hash anchor before first test. Mmap lifetime
and rustix seals are mandatory; no raw pointer escape, forged mutable alias,
or bypass of end-to-end integrity validation.
Only application submit throughput is measured, not photons or CP03 HYBRID-60.
An uncontrolled or statistically inconclusive result is HOLD.
