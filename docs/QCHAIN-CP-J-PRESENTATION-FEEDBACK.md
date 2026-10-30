# QCHAIN CP-J — Wayland Presentation Feedback & Frame Pacing

Date: 2026-10-10. Parent CP-I02: 48c9ed7a71a4efe4e60d1fca633b382ce1c5af72.
Branch: feat/qchain-frame-timing-20261010. Private local qualification only.

## Experiment design

- Real CP-F PersistentSession Vulkan/WGSL calculates 120 fresh frames per run on RTX 3070. IPC delivers one verified sealed memfd at a time to a native Wayland wgpu viewer using a one-element backpressure channel.
- Weston 15 runs headless, GL/NVIDIA renderer, isolated Wayland socket. Weston debug protocol is enabled ONLY on the isolated compositor. User Hyprland, Chrome, resident services, and CPU canonical source remain untouched.
- The viewer records its CPU durations for surface acquisition, queue submit, present call, and total draw. It also logs clock_gettime(CLOCK_MONOTONIC_RAW) immediately after its wgpu present call.
- `WAYLAND_DEBUG=client` records wl_surface.frame, wl_callback.done, wp_presentation.feedback and wp_presentation_feedback.presented events. Separate Weston `proto` trace independently records all compositor-to-client presentations, including events not dispatched by the viewer before shutdown.
- Weston announces `presentation clock: CLOCK_MONOTONIC_RAW, id 4`; the client receives wp_presentation.clock_id(4). The oracle correlates each server presentation timestamp with the nearest preceding raw-clock viewer submit and explicitly checks range, order, count and uniqueness.

## Measured results — two independent live runs

| Measure | Protocol-04 | Protocol-05 |
|---|---:|---:|
| GPU-calculated + sealed-IPC frames | 120 | 120 |
| wgpu present calls | 120 | 120 |
| wp_presentation feedback requests | 120 | 120 |
| Weston server `presented` events | **120** | **120** |
| Client-received `presented` events | **119** | **119** |
| Client wl_surface.frame callback replies | 120 | 120 |
| `discarded` reported | 0 | 0 |
| Median submit-to-presentation, same raw clock | 16.765 ms | 16.757 ms |
| P99 submit-to-presentation | 16.886 ms | 16.826 ms |
| Median interval of server presentation | 33.085 ms | 33.086 ms |
| P99 presentation interval | 35.451 ms | 35.680 ms |
| Estimated server presentation-event cadence | 30.230 Hz | 30.236 Hz |
| Weston compositor capture samples | 8 exact | 8 exact |

The cadence is a measurement of **Wayland server presentation feedback events** on a simulated 512x384 headless output, NOT proof of physical 30 FPS photons, 60 FPS support, display VRR, NVIDIA GPU timestamps, or end-to-end CP03 HYBRID-60.

The reported `refresh=16666666` ns describes Weston output refresh prediction, not demonstrated 60 FPS for the application. Feedback flags are 0; no hardware VSYNC flag was asserted. CPU source-to-GPU, host readback, memfd, and GPU upload remain in the path: not zero-copy.

## Causal findings

**GATE J-PRESENT-SERVER — PASS.** All 120 wgpu submissions are associated with uniquely ordered Weston server `wp_presentation_feedback.presented` events; timestamp differences remain within bounded windows. Eight compositor samples per run remain exact after its declared vertical flip.

**GATE J-CLIENT-DRAIN — HOLD.** Only the first 119 of the 120 `presented` events are processed by the client's Wayland event dispatch. The final event is present in Weston's server-side protocol log and the final frame has a `wl_callback.done` in the viewer trace, but that last presentation event is not delivered to the client-side log before shutdown. A 300 ms delayed exit did not close this gap. Do not misclassify as a missing server presentation or claim client 120/120.

**GATE J-OBSERVABILITY — PARTIAL.** wgpu CPU draw phases, IPC identity and `CLOCK_MONOTONIC_RAW`/server feedback are measured; driver GPU timestamps, application GPU kernel stages F2/F3/F4 independently timestamped, VRAM, frame drop attribution under load, and real Hyprland physical display refresh remain NOT_RUN.

**Weston `timeline` debug failure.** The first diagnostic run enabling `timeline` + `proto` crashed the isolated Weston GL renderer on `timeline_render_point_handler: Assertion result_available == GL_TRUE`. This failure is archived under `runs/protocol-01` and is not a GPU application regression. `proto` alone ran successfully. No operator compositor debug setting was changed.

The byte-level oracle checks the protocol's clocks and dual trace attribution, as well as strict timing order. Its adversarial suite executes five tests including a valid positive case, a removed server presentation, incorrect clock ID, mutated app timestamp sequencing and client feedback tampering. All PASS; the static N01–N17 CP-L/G06 program remains separately OPEN.

## Evidence & follow-up

Private root: `/mnt/workbench/evidence/runs/qchain-cpj-20261010-01/`.
- `runs/protocol-01/`: failed Weston `timeline` instrumentation (never promoted).
- `runs/protocol-04/`, `runs/protocol-05/`: complete GPU/IPC/Weston traces, client WAYLAND_DEBUG, server `proto` output and sampled PNGs.
- `oracle/protocol-04.json`, `oracle/protocol-05.json`: independent client/server protocol reconciliation.
- `oracle/negative-tests-final.log`: adversarial controls.
- `preflight/` : source builds and test logs.

**Bounded verdict:** `QCHAIN_CPJ_WESTON_SERVER_120_PRESENTED_CLIENT_119_DRAIN_HOLD`.

**Next CP-JA:** correct client event-loop final feedback drainage without weakening the semantic frame contract, then repeat 120/120 client receipt and independent timestamp audit; separately open CP-JB for GPU timestamps + load attribution. No merge, push, production deployment or public FPS claim.
