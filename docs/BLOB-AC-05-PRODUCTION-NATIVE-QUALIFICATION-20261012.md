# BLOB-AC-05 — Production Native E2E: real SDF CPU frames
Date: 2026-10-12. Contract: ../contracts/BLOB-AC-05-PRODUCTION-NATIVE-E2E-20261012.md
Independent verified captured-run oracle: ../evidence/runs/blob-ac05-20261012/qualified/capture-qualification.json

## What was actually run
The native production blobin-showcase binary ran under a private Weston compositor with its own test pointer seat, isolated from the users Hyprland and network using unshare -Urn. Its BLOB-FRAME-v1 socket connected to the actual blobin_renderd CUDA05F bridge, NOT blob-frame-testserver. The backend requested and actually used was CPU. First-party render workers and daemon were the binaries already built at /mnt/workbench/target/release, not code vendored into this repository.

## Measured chain
- Weston plugin: pointer enters first Primitive Lab circle at physical 258,400, presses primary, moves +60 then +140 pixels, releases.
- Real winit window: 6 pointer records in captured trace, including independent compositor-delivered press/release and exact movement coordinates.
- Actual egui canvas: preview positions change without writing SceneState coordinates and without scheduler invalidation. An idle repaint previously reset preview to baseline; the code now updates only when egui input indicates real pointer movement, and a test covers extra idle redraws.
- Real transaction: 1 Commit, scene circle x -0.26→-0.16, scheduler revision 3→4.
- Real Render Bridge: exactly two CPU requests (one baseline, one commit) and two BLOB-FRAME frames (revision 3 / revision 4). The geometry_sha256 changes, no testcard server and no intermediate render during drag.
- Independent source pixels: actual ReceivedFrame mapped bytes are archived as .rgba.gz with exact raw SHA and PNGs reconstructed without loss. At frame pixel 205,400 white→black; at 345,400 black→white; background 20,20 unchanged. Both frames 932×800 RGBA8.

## Native crash found and fixed
The first private production launch panicked in egui 0.36 due to dropping a non-empty TexturesDelta after the render uploader already processed its set/free operations. app.rs now explicitly clears consumed texture changes after submission. Subsequent independent production launch ran without this panic and received actual SDF frames.
A second issue: during active drag, repaint without fresh pointer motion can deliver a zero drag_delta(), clobbering the current Preview. app.rs now accepts delta only on real pointer movement, then commits the last accepted preview at release. Production egui tests cover two idle redraws during a drag.

## Reproduction versus evidence qualification
Offline evidence/compilation:
python3 scripts/blob_ac05_verify.py

Repeat live private preflight (manual; make test-only module first with cc/pkg-config):
scripts/blob_ac05_private_preflight.py

After a captured run:
python3 scripts/blob_ac05_qualify_capture.py --source evidence/runs/blob-ac05-20261012/preflight --destination evidence/runs/blob-ac05-20261012/qualified

Revalidate immutable proof:
python3 scripts/blob_ac05_revalidate.py --evidence evidence/runs/blob-ac05-20261012/qualified

The newly hardened alternative isolated replay script had a namespace-check failure and an execution block. It was NOT promoted as an automated PASS or used as the source of the positive evidence. A private run already performed before this attempt is independently qualified. Future agents must repair replay under authorized execution and rerun before declaring fresh automated E2E.

## Truth and exclusions
SCOPED PASS: compositor-origin gesture in real production app → semantic commit → actual CPU SDF field evaluations and real source-frame pixel differences, for one bounded Primitive Lab scene.
NOT QUALIFIED: compositor presentation acknowledgement, original GPU kernel execution, physical HID/USB, frame pacing, sustained 60 FPS, UX ratification, cross-vendor and CP03 HYBRID-60. Trace event name presented refers to receipt/upload decision, not compositor present feedback.
The existing UI-G04B/H parallel unpublished experiment remains untouched and excluded from this scope; AC05 does not overwrite its authority.
