# CP-JA7K — F4 individual GPU copy/readback timestamp experiment

Experiment isolated under /mnt/workbench/evidence/runs/qchain-cpja7k-20261012-01.
Source parent CP-JA7J-C Git 46d217ce9f1dce6d3cc95e2eb0d2dc4a2f841e62.
Source historical clean baseline 5132cf59b3842e27dcacf89bfe7060e807706e90.
No change of sealed CP-JA7JC branch; no Git promotion until separate worktree becomes available.

Claim to test: three GPU buffer-to-buffer copies each bracketed by actual Vulkan
timestamp queries, following six authentic compute pass pairs. Together 18
hardware timestamps per frame, all in one command encoder and one submission.
Use Features::TIMESTAMP_QUERY and Features::TIMESTAMP_QUERY_INSIDE_ENCODERS,
fail closed if unavailable. Distinguish copy command duration from host mapping,
driver synchronization, PCIe throughput and individual CPU transfer time.

Primary readback-copy test: 300 frame pilot, then 1200 frame full E2E,
same source, two Vulkan WSI swapchains, 2400 typed ACKs,
2400 Weston presented, eight byte-checked screenshots; no physical GPU reset.
At least 15 NVIDIA sensor samples, every gap <=3 seconds, 75 C / 180 W
sampled abort, baseline temp <65 C, wall timeout <=100 seconds.
No thermal/stress pressure on resident Hyprland.

Controls: preserve CPU byte identities and 6 GPU compute passes, 3 readbacks,
no intermediate host round-trip; independent oracle checks raw 1200 * 18
* 8 bytes = 172800 bytes, shader kernel and copy tick pairs,
frame IDs, output hashes and WSI feedback. Compare to original no-copy-query
baseline descriptively; causal claim requires preregistered paired A/B.
Adversarial mutations for raw bytes, GPU period, log duration, frame count,
WSI acknowledgments and visual pixel checks.

Do not confuse single GPU copy timestamps with:
(1) wall time for map_async/poll,
(2) host-side memory copying, or
(3) PCIe bus transaction-specific measurements.
CP03 HYBRID-60 remains OPEN unless separately qualified.
No merge, push, deployment or production promotion.
