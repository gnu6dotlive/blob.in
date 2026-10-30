# CP-JA7 — Multi-Swapchain Authority and Loss Boundaries

Date: 2026-10-10. Parent: CP-JA6 `e460b0f1c9f6ac2551c32e49c951b1683ce32ded`.
Branch: `feat/qchain-wgpu-multi-swapchain-20261010`.
RTX 3070, wgpu 30.0.1 + isolated vendored wgpu-hal 30.0.1, Weston 15 headless.
Private experimental code, no merge, push, deployment or public performance claim.

## Tested native topology

`qchain_cpja7_dual_viewer.rs` uses **one Vulkan-backed wgpu
instance, one logical device and queue, and two distinct winit Wayland
windows and configured swapchain surfaces**. The verified 120-frame
CP-F GPU compute stream is authenticated over the existing sealed
memfd IPC. Each source frame is uploaded once to a shared texture
and drawn to both swapchains; each swapchain receives its own typed
`VkPresentIdKHR` and `vkWaitForPresentKHR` through the CP-JA6 HAL.

The original CP-JA6 viewer depended on winit redraw callbacks for
progress. Weston kiosk obscures one window and can withhold redraw
callbacks. The first experimental run stalled after two frames, and
was archived as `runs/dual-01`. The new dual witness drives the
pacing from its bounded data/event loop; renderer callbacks cannot
silently stall an occluded surface.

## Positive: same device, two live swapchains

Two full dual-surface runs `dual-02` and `dual-03` each achieved:
- 120/120 fresh GPU frames from the engine and sealed IPC;
- swapchain generation 1: typed Vulkan success IDs 1–120;
- swapchain generation 2: typed Vulkan success IDs 1–120;
- 240 typed Vulkan waits returning success (480 total across both runs);
- eight exact 512×384 compositor screenshots per run of the visible
  kiosk window, with zero pixel mismatch after Weston Y-flip.

**IMPORTANT: visibility distinction.** Weston kiosk stacks these
two full-screen windows. In the observed dual run, client and
server jointly record 121 `presented` events and 119
`discarded` events. **Those 119 occluded presentations are not
displayed frames**, even though their Vulkan wait calls return
success. Do not convert 240 typed waits into 240 visually presented
frames. The second window's independent visual correctness remains
unqualified.

## Secondary surface teardown: Vulkan PASS, visual recovery HOLD

With `CPJA7_DROP_SECONDARY_AFTER=60` the secondary swapchain is
released after its frame 59 receives its typed ACK; the primary remains
alive and processes its 120-frame source. The HAL logs:
- primary generation: 120/120 typed `VK_SUCCESS` IDs 1–120;
- secondary generation: 60/60 typed `VK_SUCCESS` IDs 1–60;
- total: 180 typed acknowledgments, no cross-generation reuse.

However, the kiosk compositor **does not visibly recover** the
primary after the secondary window closes. The first five sample
captures match their canonical GPU pixels, but samples 5, 6 and 7
have 196,608 pixel mismatches each (entire 512×384 frame). The
original screenshot-qualification runner correctly exits nonzero
with `WESTON_SAMPLED_PIXEL_DIFF` and writes **no success receipt**.

The independent oracle records
`CPJA7_DROP_SECONDARY_VK_180_ACK_PASS_VISUAL_RECOVERY_HOLD`.
This is **not a CP-JA7 full PASS**; Weston kiosk visibility recovery
requires its own compositor-aware fix and new captures.

## Private compositor disconnect: fail-closed

`scripts/qchain_cpja7_disconnect_run.py` starts a completely
isolated Weston and source/viewer pair, terminates only its
own Weston process after source seq=59, waits for viewer exit, and
requires nonzero exit, no end-of-stream marker and no PASS receipt.
The physical run yielded
`CPJA7_PRIVATE_WESTON_LOST_VIEWER_FAIL_CLOSED` with viewer exit 1.
This is a real Wayland compositor disconnect, **not** an injected
Vulkan `VK_ERROR_DEVICE_LOST`, hardware hot-unplug or device recovery.

The trial never touches the user's Hyprland compositor or services.

## Independent oracle, adversaries and remaining gates

`scripts/qchain_cpja7_independent_oracle.py` checks exact
source/secondary frame sequences, distinct swapchain generation IDs,
per-generation consecutive present IDs, total typed ACK count,
client/server Wayland `presented` and `discarded` events and
per-screenshot exact pixels. Six tests in
`scripts/test_qchain_cpja7_oracle.py` pass, including removal of
the last secondary ACK, duplicated ID, cross-generation forgery,
dropped server event and a teardown HOLD. All altered witnesses
are isolated copies: canonical evidence is not overwritten.

Run evidence:
`/mnt/workbench/evidence/runs/qchain-cpja7-20261010-01/`
- `runs/dual-01`: first kiosk redraw starvation HOLD, preserved.
- `runs/dual-02`, `runs/dual-03`: dual-swapchain-scope test PASS.
- `runs/drop-01`: secondary release Vulkan PASS, compositor HOLD.
- `negative/weston-disconnect-01`: private Weston killed, fail-closed.
- `oracle/`: independent per-run reports and negative controls.
- `preflight/`: builds, Rust tests, Clippy, exact-commit archival qualification.

**Scoped verdict:** `CPJA7_DUAL_SWAPCHAIN_TYPED_AUTHORITY_PASS_VISUAL_RECOVERY_HOLD`.

Still OPEN: actual physical Vulkan device loss and recovery;
independent visual presentation of both windows; two simultaneous
presents in flight (the HAL still synchronously waits per present);
physical photons; two compositors, AMD/Intel and cross-host validation;
CP03 HYBRID-60, CP-L G06, zero-copy and 60 FPS.

Suggested CP-JA7B: use a Weston desktop shell with independently
positioned visible surfaces and compositor-aware capture, then
test window removal and recovery. CP-JA7C: controlled
`VK_ERROR_DEVICE_LOST` at a Vulkan layer or vendor-supported
fault-injection harness (no disruption to the system compositor).
