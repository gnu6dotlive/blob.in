#!/usr/bin/env python3
"""Fail-closed static validator for QCHAIN-GPU-EXECUTION-01 dispatch."""
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "contracts/qchain-gpu-execution-01/dispatch.json"
DOC = ROOT / "docs/QCHAIN-GPU-EXECUTION-01.md"
STATES = {"NOT_RUN", "PASS", "FAIL", "HOLD", "INCONCLUSIVE"}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def validate():
    spec = json.loads(PATH.read_text())
    doc = DOC.read_text()
    require(spec["schema"] == "gnu6.qchain.gpu_execution_dispatch.v1", "wrong schema")
    require(spec["document_status"] in {"draft", "reviewed", "adopted"}, "bad document state")
    require(spec["operator_ratification"] in {"PENDING", "RATIFIED", "REJECTED"}, "bad authority")
    require("Intent != contract != implementation != proof != public claim" in doc, "missing doctrine")
    require("CP03 HYBRID-60 reste OPEN" in doc, "missing CP03 boundary")
    require(spec["publication"] == "FORBIDDEN_WITHOUT_SEPARATE_AUTHORIZATION", "unsafe publication")
    base = spec["baseline"]
    require(re.fullmatch(r"[0-9a-f]{40}", base["source_commit"]), "invalid source commit")
    require(base["frame_count"] == 5 and base["unique_source_scene_identities"] == 5, "bad identities")
    require(base["distinct_f4_pixel_buffers"] == 3, "loss of pixel-collision guard")
    require((base["width"], base["height"], base["rgba_stride_bytes"], base["rgba_frame_bytes"])
            == (512, 384, 2048, 786432), "wrong fixture shape")
    require(spec["cp03_hybrid60"] == "OUT_OF_SCOPE_AND_OPEN", "CP03 claim inflation")
    gates = spec["gates"]
    workers = spec["workers"]
    gm = {g["id"]: g for g in gates}
    wm = {w["id"]: w for w in workers}
    require(len(gm) == len(gates) == 11, "missing or duplicate gate")
    require(len(wm) == len(workers) == 9, "missing or duplicate worker")
    require(set(gm) == {f"G{i:02}" for i in range(11)}, "unexpected gates")
    require(set(wm) == {f"W{i:02}" for i in range(9)}, "unexpected workers")
    require(set(spec["states"]) == STATES, "unknown verdict classes")
    require(spec["negative_laws"] == [f"N{i:02}" for i in range(1, 18)], "missing sabotage law")
    for g in gates:
        require(g["owner"] in wm and g["id"] in wm[g["owner"]]["assigned_gates"], "orphaned gate")
        require(g["status"] in STATES, "unknown gate status")
        require(g["artifact"].endswith(".json") and "/" not in g["artifact"], "unsafe artifact")
        require(all(d in gm and d != g["id"] for d in g["depends_on"]), "bad gate dependency")
    for w in workers:
        require(w["status"] in STATES, "unknown worker state")
        require(all(d in wm and d != w["id"] for d in w["depends_on"]), "bad worker dependency")
        require(w["scope"].strip() and w["deliverables"], "unbounded worker")
    def acyclic(graph):
        done, active = set(), set()
        def visit(node):
            require(node not in active, "dependency cycle: " + node)
            if node not in done:
                active.add(node)
                for dep in graph[node]:
                    visit(dep)
                active.remove(node)
                done.add(node)
        for node in graph:
            visit(node)
    acyclic({k: v["depends_on"] for k, v in gm.items()})
    acyclic({k: v["depends_on"] for k, v in wm.items()})
    if spec["operator_ratification"] == "PENDING":
        require(spec["execution_authority"] == "CONTRACT_AUTHORING_ONLY", "unratified execution")
        require(all(g["status"] == "NOT_RUN" for g in gates), "unratified gate claimed")
    return spec

if __name__ == "__main__":
    try:
        result = validate()
    except Exception as exc:
        print(f"QCHAIN_CONTRACT_STATIC_VALIDATION_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"QCHAIN_CONTRACT_STATIC_VALIDATION_PASS: {len(result['gates'])} gates, "
          f"{len(result['workers'])} workers, {len(result['negative_laws'])} adversarial laws")
