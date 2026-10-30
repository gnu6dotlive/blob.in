# CP-JA7C — Controlled Vulkan Device Loss and In-Process Recovery

**Date:** 2026-10-11. **Parent:** CP-JA7B `83d0c76d6c1e18a27ad520d4bec64071921c38b7`.
**Environment:** Arch/CachyOS, NVIDIA GeForce RTX 3070, Vulkan-backed wgpu 30.0.1, private Weston 15 headless desktop shell, F4 512×384 source frames.
**Verdict:** **SCOPED PASS, synthetic WSI fault only**. A real `VK_ERROR_DEVICE_LOST` *value* is propagated from a deterministic HAL test hook and handled by wgpu device-loss callbacks, followed by in-process rebuilding of the device and two Wayland swapchains. **No physical GPU loss or driver-returned error is claimed.** A Vulkan loader/layer-injected error or driver-reported loss remains future scope.

## Fault contract

CP-JA7C adds a test-only Cargo feature:
`--features cpja7c-device-lost-test` implies the existing `cpja5-present-wait` capability.

The vendored `wgpu-hal` native WSI implementation checks `CPJA7C_INJECT_LOST_AT=primary-generation-1-present-41`, only when the test feature is compiled. When generation 1 requests Vulkan present ID 41, it poisons the CP-JA6 swapchain lifecycle, emits `CPJA7C_INJECTED_VK_ERROR_DEVICE_LOST` and passes `vk::Result::ERROR_DEVICE_LOST` into the existing `DeviceError::Lost` mapping, **before** calling the vendor's `vkQueuePresentKHR`. This is a deliberately synthetic WSI result: no GPU reset, no vendor fault, no operating-system-wide error. The presentation with ID 41 cannot receive a typed success ACK.

At the next layer, wgpu's actual `set_device_lost_callback` fires with `DeviceLostReason::Unknown` and a `Device is lost` detail. The viewer's `lost_signal` forbids further draws on the old device. When `CPJA7C_RECOVER_IN_PROCESS=1`, the viewer preserves the exact authenticated source frame at sequence 40, drops the old device/window/swapchain resources, initializes another Vulkan instance/device with two distinct Wayland surfaces, and replays the held frame. `recovery_epochs` is bounded to exactly one. Another device-lost callback fails closed.

The test never claims that the underlying ICD actually lost its physical device. As a result, in-process recovery here demonstrates **the application's device-loss recovery control flow**, not recovery from hardware reset, a genuine ICD `VK_ERROR_DEVICE_LOST`, or a corrupted GPU context. A real loss could have additional teardown hazards absent from this injected case.

## Positive observations

Three separately executed private end-to-end runs retained at:
`/mnt/workbench/evidence/runs/qchain-cpja7c-20261011-01/runs/loss-recovery-01`, `loss-recovery-02`, `loss-recovery-03`.

Each run requires all of the following:
- Exactly 120 source frames with continuous source sequence, source F4 hash/semantic checks and sealed-memfd IPC.
- Exactly one synthetic HAL `ERROR_DEVICE_LOST`, exactly one wgpu device-lost callback.
- In-process recovery markers with the held frame sequence 40, exactly one rebuild, and uninterrupted completion.
- Two initial swapchain generations, followed by two **new** generations. Generation 1 and 2: 40 success IDs each; generations 3 and 4: 80 success IDs each; no ACK for generation 1 present ID 41.
- Four distinct Wayland resource IDs, with feedback requests 40/40 and then 80/80; no old-surface feedback request after the rebuild.
- 240 independently reconciled client/server `presented` feedback events and no `discarded`.
- Eight 1536×1024 compositor captures per run with two simultaneously visible, separately identified 512×384 surfaces. The canonical GPU bytes remain SHA-exact, while Weston GL screen pixels have a **per-channel RGB maximum deviation ≤3** and exact alpha after Y-flip.
- Valid application exit and stream completion; private Weston and IPC cleanup. `CP03 HYBRID-60` and real device loss are not inferred.

The positive runner is `scripts/qchain_cpja7c_run.py` and its production gate is `scripts/qchain_cpja7c_gate.py`. Independent qualification is performed by `scripts/qchain_cpja7c_independent_oracle.py`, which reads the original PNGs and the Wayland/Vulkan logs and independently recomputes all source, frame, recovery, feedback and pixel checks without trusting the producer's verdict.

## Controls and falsification

Three live negative runs use `scripts/qchain_cpja7c_negative_run.py`:
- **No recovery allowed:** inject generation 1 present 41, reject after 40 frames, nonzero exit, no success receipt.
- **Second loss after reconstruction:** inject on generation 1 present 41 and generation 3 present 5. The first reconstruction succeeds but the second device-loss callback terminates at source frame 44. No unbounded retry, no success receipt.
- **Recovery required without injection:** all 120 frames submit normally but the test exits nonzero because the mandatory recovery epoch never occurred. No fabricated recovered-device receipt.

A separate no-injection regression run with the exact same test-feature binary and the injection variable unset passes CP-JA7B's two-surface oracle, proving that merely compiling the feature does not trigger the fault.

`scripts/test_qchain_cpja7c_oracle.py` applies ten adversarial changes to isolated temporary evidence copies and requires the independent oracle to reject them: removed fault event, removed device-lost callback, missing new-generation ACK, forged failed-generation ACK, missing rebuild event, duplicated source sequence, pixel corruption after recovery, aliased surfaces, omitted compositor feedback and corrupted canonical source hash. **Ten of ten controls are rejected.** The pristine evidence is never overwritten.

## Verification gates

| Gate | Outcome |
|---|---|
| Isolated test-feature fault injection at HAL WSI boundary | PASS (synthetic VkResult) |
| Wgpu device-lost callback and device-invalidated control flow | PASS |
| Fail closed on old device; failed present not ACKed | PASS |
| In-process device + two swapchains rebuilt, source frame 40 replayed | PASS |
| All source semantics and per-generation presentation authority | PASS |
| Two-window compositor observation before and after device rebuild | PASS |
| Independent oracle and ten adversarial corruptions | PASS |
| Three live negative controls and feature-off-at-runtime baseline | PASS |
| 31 `blob-frame` unit tests and clean Clippy test-feature build | PASS |
| Actual NVIDIA ICD `VK_ERROR_DEVICE_LOST` returned by Vulkan call | **NOT TESTED** |
| Physical GPU reset, true device recovery after driver failure | **NOT TESTED** |
| Multiple presents genuinely in flight | **OPEN** |
| CP03 HYBRID-60 / display photons / AMD-Intel cross-vendor | **OPEN** |

**Handoff:** CP-JA7C-B should use an isolated Vulkan loader layer or supported driver instrumentation to return `VK_ERROR_DEVICE_LOST` through the actual function-pointer dispatch, then repeat the in-process recovery and destruction/recreation qualification. Only after that should true hardware-loss recovery be considered separately and carefully, with no reset or intervention on the resident display GPU. CP-JA7D can address multiple presentations in flight. Keep CP03 HYBRID-60 independent.

No merge, push, deployment, user compositor termination, resident service restart, or physical GPU faulting is authorized or performed in this run.
