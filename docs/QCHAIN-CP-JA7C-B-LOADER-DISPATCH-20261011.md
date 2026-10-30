# CP-JA7C-B — Vulkan Loader-Level Device Loss

Date: 2026-10-11
Parent: CP-JA7C `b89470d4daf448489be078cc0ba0981e9edb6c50`
Decision: **SCOPED PASS — private explicit-layer Vulkan return-value injection, not physical/driver device loss.**

## Goal and boundary

CP-JA7C used an opt-in conditional inside the vendored wgpu-hal before its Vulkan function call. CP-JA7C-B qualifies an independent failure source **outside the HAL**: a private Vulkan explicit layer returns `VK_ERROR_DEVICE_LOST` directly through the `vkQueuePresentKHR` function pointer obtained from the loader. The application uses the parent device-loss callback and bounded in-process rebuild path unmodified.

This test must not claim a fault returned by the actual NVIDIA ICD or a real physical device reset. A Vulkan layer *simulates* the Vulkan return value at the loader dispatch chain; for the injected presentation it deliberately **does not call the next driver's `vkQueuePresentKHR`**. This demonstrates robustness to a failing Vulkan API call, not robustness to hardware loss or an actually poisoned NVIDIA GPU context.

## Private reproducible test environment

- Host: Arch/CachyOS, RTX 3070, Vulkan loader 1.4.363, libweston 15 headless GL, Wayland `desktop-shell`.
- `tests/cpja7cb/gnu6_loader_fault_layer.c`: purpose-built C Vulkan **explicit layer**, built with `cc -std=c11 -O2 -fPIC -shared -Wall -Wextra -Werror -pthread`.
- Layer negotiation and dispatch: `vkNegotiateLoaderLayerInterfaceVersion`, `vkGetInstanceProcAddr`, `vkGetDeviceProcAddr`, `vkCreateInstance`, `vkCreateDevice`, `vkCreateSwapchainKHR`, `vkGetDeviceQueue`, `vkQueuePresentKHR`, and per-device destroy.
- The loader manifest `VK_LAYER_GNU6_cpja7cb_fault.json` and `.so` live **only** inside the private evidence directory, never under `/usr/share/vulkan`. Only the viewer subprocess gets `VK_LAYER_PATH`, `VK_INSTANCE_LAYERS=VK_LAYER_GNU6_cpja7cb_fault`, and `CPJA7CB_LOADER_FAULT=primary-id-41`. The broker/engine processes never receive those layer variables.
- Viewer build uses `--features cpja5-present-wait`, **not** `cpja7c-device-lost-test`. This distinction ensures CP-JA7C's internal HAL fault injector is absent. The application still enables its existing `CPJA7C_RECOVER_IN_PROCESS=1` device-lost recovery controller.
- The layer identifies the first-created swapchain per device, then matches typed Vulkan present ID 41. The initial device's 41st primary present returns `VK_ERROR_DEVICE_LOST` without forwarding it to the ICD.

### Loader lifecycle discovery and correction

An initial loader probe rejected a manifest with a numeric `implementation_version`; the installed loader expects the value as a string. After correction, `vulkaninfo --summary` initialized through the private layer. The first layer build also wrongly required swapchain function pointers for a `vulkaninfo` device without `VK_KHR_swapchain`; relaxing that assumption corrected a probe failure.

The first visual pilot (archived) exposed a more important lifecycle issue: after wgpu discarded the lost Vulkan instance/device, the loader **unloaded and then reloaded** the explicit-layer shared library. C static state was reset and the test mistakenly injected a second fault at new-device present ID 41. The viewer correctly failed closed. The corrected test layer persists the fault counter through a test-viewer-only environment marker, surviving layer reload **without involving other user processes**. For the adversarial double-loss mode, a second injection occurs deliberately on new-device present ID 5.

## Positive E2E qualification

Three valid positive runs use private Weston and distinct private source-broker sockets:

- `runs/loader-recovery-02`
- `runs/loader-recovery-03`
- `runs/loader-rebuilt-recovery-04` (source-recompiled explicit-layer .so, byte-identical SHA-256)

Each run must establish:
- Exactly 120 authenticated, monotonically ordered source frames; F4 GPU frame bytes and scene digests remain cryptographically exact.
- Exactly one fault event from the **loader layer**, exactly one real wgpu `DeviceLost` callback, and **zero CP-JA7C internal HAL-injection events**.
- The failed Vulkan ID 41 on initial generation 1 has **no success ACK**. Old generations 1 and 2 each report 40 `VK_SUCCESS` typed ACKs.
- Wgpu reconstructs an independent Vulkan instance/device and two fresh Wayland swapchains in the **same client process**. New generations 3 and 4 each report 80 typed ACKs, starting at present ID 1.
- Four unique Wayland resource IDs with feedback request counts 40/40 then 80/80; the old resources receive no post-recovery requests.
- Exactly 240 `presented` events, zero `discarded`, fully reconciled between client and private Weston server.
- Eight compositor screenshots per run: two distinguishable 512×384 regions within the 1536×1024 composite, with the secondary 16px signature. Their RGBA-derived oracle checks exact alpha and per-channel RGB deviation no more than 3, never claimed universally byte-exact.
- No false completion until source sequence 119; all scoped processes terminate cleanly.

## Negative trials and independent falsification

`scripts/qchain_cpja7cb_negative_run.py` validates:
1. **No recovery authorized:** loader fault at present ID 41, nonzero viewer exit after 40 accepted source frames, no false success receipt.
2. **Intentional second loader fault:** first loss at ID 41 and second at new device ID 5; one reconstruction but fail-closed at frame 44, never an endless retry.
3. **Recovery demanded with no fault:** 120 normal frames complete but the qualification viewer fails because it cannot honestly claim a recovery epoch.

The no-fault negative is a control on the *claim*, not a 120-frame presentation failure: it proves an enabled layer without the fault flag can transparently forward all frames. `vulkaninfo` without fault also passes through the explicit layer.

A separately implemented `scripts/qchain_cpja7cb_independent_oracle.py` recomputes all source hashes, screenshot pixel metrics, typed Vulkan ACKs, loader dispatch witness, device-loss ordering and Wayland client/server feedback directly from original logs and PNG bytes. It never trusts the positive runner's stored verdict.

`scripts/test_qchain_cpja7cb_oracle.py` uses temporary copies to falsify: missing fault, missing callback, missing new ACK, forged ACK for lost frame, missing recovery-ready marker, duplicated source sequence, corrupted post-recovery pixels, aliased windows, missing Weston presentation event, corrupted canonical hash, missing loader negotiation, missing loader-dispatch forward, and an illicit HAL-side fake injection. All **13/13** must be rejected.

## Scope matrix

| Qualification | Result |
|---|---|
| Private Vulkan layer negotiation and real loader dispatch | PASS |
| Fault `VK_ERROR_DEVICE_LOST` returned via `vkQueuePresentKHR` to HAL | PASS (synthetic layer) |
| wgpu device-loss callback, fail-closed, no lost-present ACK | PASS |
| Device + two swapchains recreated, source frame preserved | PASS |
| Two compositor-visible surfaces and post-recovery pixels | PASS |
| Client/server feedback and typed present ID reconciliation | PASS |
| Three independent positive runs, source-rebuilt layer | PASS |
| Live adversarial aborts and independent oracle falsification | PASS |
| Physical reset or genuine NVIDIA ICD `VK_ERROR_DEVICE_LOST` | **NOT RUN** |
| Cross-vendor AMD/Intel | **NOT RUN** |
| More than one present genuinely in flight | **OPEN** |
| CP03 HYBRID-60, zero-copy, physical display qualification | **OPEN** |

**Next:** CP-JA7D can qualify multiple Vulkan presentations simultaneously in flight, with typed sequence ownership and failure recovery. For future authentic driver-loss work, design a disposable GPU/VM safety envelope; **do not** trigger a real device loss on the RTX 3070 that hosts Hyprland. The CP03 HYBRID-60 gate remains independent.

No push, merge, release, production deployment, global Vulkan layer installation or resident compositor alteration is authorized.
