# blob.in — CP03-I01 / HYBRID-HERO-60@1 Integrated Scene

**Status: SOURCE ACQUISITION / IMPLEMENTATION OPEN / ALL CP03 GATES HOLD**
2026-10-12; parent Git `977e3cb65041b5654a44fbf5d28cdabc8f47760f`.
This contract is an operational integration preflight, **not a replacement for the
full previously ratified CP03 normative contract**. Recover the canonical
seven-gate specification and preserve its exact thresholds before qualifying.

## Identity and geometry invariants
- Product: **blob.in**, not Gnosix or an independent QCHAIN demo.
- Workload ID: `HYBRID-HERO-60@1` with exact 1280×720 frame raster, time-varying
  deterministic parameters and attributable scene/frame/source identity.
- Geometry requires genuine signed-distance objects and CSG **on the GPU**,
  a **closed triangulated mesh**, an **open triangulated mesh**, a genuinely
  mixed SDF/mesh boolean, and time-varying transforms. All categories must be
  simultaneously active in the same scene, not a collage of independent demos.
- Open-mesh boolean semantics (clipping/surface treatment) must be expressly
  declared. A naive inside/outside sign test for an open surface is invalid.
- Strict provenance for topology, winding, degenerate triangles,
  transformation matrices, numerical tolerances, scene epochs and materials.
- Any constituent `present=false`, dummy geometry, synthetic proxy or
  unexecuted feature MUST block the `HYBRID-HERO-60@1` claim.
- Real native Vulkan/Wayland present with unique ordered IDs; feedback,
  independent captures and byte-/tolerance-bound geometry oracles.
- Real input→frame causality and later physical light-sensor witness.
- Source and runtime build must correspond to same SHA-pinned revision.

## Performance target (normative details must be recovered)
Sustained ≥7200 presentations over ≥120 s, ≥600 per every 10 s, interval
p95 ≤17 ms, p99 ≤20 ms, maximum gap ≤33.4 ms, input→presentation p95
≤50 ms. On NVIDIA RTX 3070, with G01–G07 assessed together and
independent oracle. Input→photon evidence is a separate physical gate.
No cherry-picked trials, duplicate ACKs, invented presented feedback,
fallback without disclosure or control-plane-only claimed presentation.

## Donor boundaries discovered 2026-10-12
- Historical `blobin-core` is genuine blob.in 2D animated cubic Bézier,
  lyon tessellation + flat 2D triangle mesh (x/y/uv/rgba). The word
  `Mesh` does **not** establish a 3D manifold mesh or mixed 3D boolean.
- F2/F3/F4 experiments are independently qualified 512×384
  topology/material/effect GPU proofs, not 1280×720 hybrid-geometry scenes.
- CUDA-01 implements synthetic analytic 2D circles with union/difference/
  intersection/smooth-union. Explicitly **not** a general arbitrary-geometry
  CSG or a mixed 3D mesh+SDF implementation; it cannot close G01.
- GPU05 9370 `presented` over 124.994s exists as an earlier bounded
  compositor pacing witness, but CP03 numeric receipt is `NOT_QUALIFIED`
  (input samples zero; independent provenance not qualified).
- QCHAIN CP-JA7L ~31 FPS uses 512×384 F4 frames, not the final hero.

## Preflight acceptance stages
1. Source register with immutable SHA for donor code, docs and receipts.
2. Renderer/source capability inspection: distinguish REAL/partial/not-run
   from labels or marketing prose. Explicit BLOCKER for any required absent
   geometry.
3. Scene definition at 1280×720 plus deterministic interaction sequence,
   attributable source and replay oracle. No `HYBRID-HERO-60@1 PASS`
   before each category has an executed, independent witness.
4. First native GPU scene image and external capture, paired geometry oracle,
   then complete 120s A/B under guard, input and external validation.
5. Campaign with same binary/scene hashes, fail-closed falsification probes,
   positive source→GPU→WSI→pixel→input trace, and final G01–G07 signoff.

## Safety and publication
Private worktree, no resident Hyprland reset, no physical GPU failure,
no production merge/push/deploy. Historical source license boundaries
must be reviewed prior to vendoring or public release.
Do not backfill new gates with old receipt values. A conservative HOLD
is correct if source, normative thresholds or independent evidence is missing.
