#!/usr/bin/env bash
set -euo pipefail
W=/home/tension_atoi/Projects/.worktrees/blobin-showcase-qcja3-20261010
R=/mnt/workbench/evidence/runs/qchain-cpja3-20261010-01/probes/runtime-viewer-01
B=/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw
python3 "$W/scripts/qchain_cpj_protocol_run.py" \
 --engine /mnt/workbench/build/qchain-cpi02-engine-20261010/debug/examples/qchain_cpi02_gpu_live \
 --viewer /mnt/sandbox/builds/cargo/debug/qchain_cpja3_vulkan_trace \
 --broker "$W/scripts/qchain_cpi02_stream_source.py" \
 --baseline "$B" \
 --receipt /mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-reconciliation.json \
 --root "$R"
