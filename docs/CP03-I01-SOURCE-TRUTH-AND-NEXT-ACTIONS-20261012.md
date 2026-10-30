# blob.in — CP03-I01 First source truth, integration next actions

Date 2026-10-12. Parent `977e3cb65041b5654a44fbf5d28cdabc8f47760f`.
Status: **PREFLIGHT PASS / HYBRID-HERO-60@1 NOT BUILT / G01–G07 HOLD**.

## What the actual source inspection demonstrates

| Donor / evidence | Fresh observation | Permitted use | Not yet proven |
|---|---|---|---|
| Historical blob.in `blobin-core` | Bézier `Path`, `Blob`, 2D `Mesh {Vertex{x,y,u,v,rgba}}`, lyon tessellator; 41 library tests passed on an isolated copy | Identity, animation/state, 2D topology reference | Closed/open 3D mesh, mixed 3D booleans, native GPU presentation |
| F2/F3/F4 Rust lab | `PersistentSession::render_next` GPU-source pipeline; CP-JA7J-C and JA7K authenticated kernels/readbacks | GPU effects, deterministic hashes, timing/reference | General SDF/mesh boolean workload, 1280×720 integrated scene |
| CUDA-01 | Analytic circle CSG union/subtract/intersect/smooth-union; synthetic standalone CUDA | Bounded analytic CSG numerical reference | General arbitrary geometry, mixed mesh booleans, production backend |
| GPU05 native presentation | 9,370 `presented` over 124.994 s in earlier compositor work | Timing infrastructure and failure lessons | CP03 itself: numeric receipt has `cp03_pass=false`, input samples=0 |
| CP-JA7L | Four matched binary F4 trials at about 31 FPS, nine GPU stages instrumented | Trace collector/oracles/safe Vulkan runtime | CP03 hybrid renderer or 60 FPS on target geometry |

Source paths and exact hashes recorded separately in
`/mnt/workbench/evidence/runs/blobin-cp03i01-20261012-01/source-audit/donor-inventory.json`.
Historical `blobin-core` tests were run on a qualification-only copy whose
workspace lint block was stripped; unchanged source bytes were verified.
Its 41 library tests are not equivalent to 47 historical tests in other
configurations, or to an integrated Qt/GPU qualification.

## CP03-I01 actual engineering task order

**I01-A: Recover normative scene.** Locate full ratified CP03 spec
and freeze `HYBRID-HERO-60@1` scene identity, primitive types, open-mesh
semantics, Boolean tolerances, 1280x720 camera and interaction replay.
No laboratory fixture can be relabeled as the real scene.

**I01-B: Geometry authority.** Implement GPU SDF and CSG, real closed
triangular 3D mesh, open triangle surface semantics, and typed mixed
boolean operators with degenerate cases and independent geometry oracle.

**I01-C: Composition.** Draw these geometries in the same resident GPU
pipeline into a native 1280x720 Vulkan/Wayland swapchain. Preserve source
frame IDs, typed ACKs, presentation feedback, deterministic animation,
and a real input hit/miss trace. No disguised CPU fallback.

**I01-D: Native image baseline.** Acquire independent compositor capture
and geometry oracle of the same frame. Record compute, copies, WSI,
feedback, memory and input timing; any first low-FPS baseline is valid
as a diagnostic but is NOT CP03 performance PASS.

**I01-E: Handoff.** Only after source and scene fidelity qualify,
hand SHA-pinned binary/scene/frame receipts to CP03-I02 GPU residency,
I03 sustained cadence and I04 seven-gate final independent audit.

## Seven-gate triage

- G01 geometry: HOLD; source does not implement mixed 3D boolean on GPU.
- G02 presentation: HOLD for hero scene; native proofs are on other fixtures.
- G03 60 FPS: HOLD; latest F4 matched-binary runs near 31 FPS at 512x384.
- G04 input/display: HOLD; no qualified hero input-to-photon witness.
- G05 GPU origin: HOLD for hero scene; compute/copy donors are independently proved.
- G06 constrained resources: HOLD for hero scene; guards exist on lab runs.
- G07 reproducibility: HOLD for integrated binary; independent lab oracles exist.

No merge, push, release, GPU driver reset or resident compositor interference.
Review historical source licensing before any source vendoring or distribution.
