#!/usr/bin/env python3
"""Independent thermal safety, plan and GPU source reconciliation, fail-closed."""
import hashlib
import json
import re
from pathlib import Path

PLAN_NAMES=(
 ("c01-balanced","balanced",False),
 ("c02-eco","eco",False),
 ("c03-eco-cpu","eco",True),
 ("c04-balanced-cpu","balanced",True),
 ("c05-balanced","balanced",False),
 ("c06-eco","eco",False)
)
THERMAL_NAMES=(("pilot-balanced-03","balanced",False),)+PLAN_NAMES+(
 ("pressure-proof-eco","eco",True),
 ("pressure-proof-balanced","balanced",True)
)
def require(ok,msg):
    if not ok:raise RuntimeError(msg)
def load(path):return json.loads(path.read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def check_safety(name,profile,stress,report,rows):
    require(report["verdict"]=="CPJA7EC_SAFETY_BOUNDED_RUN_PASS" and
            report["error"] is None and report["runner_exit"]==0,
            "SAFETY_VERDICT_NOT_PASS")
    require(report["run"]==name and report["profile"]==profile and
            report["stress_cpu_18"] is stress and
            report["runner_affinity"]==[18,19],
            "SAFETY_RUN_PROFILE_AFFINITY_DRIFT")
    require(report["temperature_abort_c"]==75 and
            report["power_abort_w"]==180 and
            report["baseline_limit_c"]==65 and
            report["wall_timeout_s"]==60,
            "THERMAL_GUARDS_REWRITTEN")
    require(5<=len(rows)==report["samples"] and
            4<=report["duration_s"]<=60,
            "THERMAL_SAMPLES_OR_WALLTIME_MISSING")
    require(all(row["test_name"]==name and
                row["temp_c"]<75 and row["power_w"]<180 and
                0<=row["gpu_util_pct"]<=100 and
                0<=row["fan_pct"]<=100 and
                row["query_duration_ms"]<=2500 and
                row["mem_mib"]>=0 for row in rows),
            "GPU_MONITOR_SANITY_OR_CEILING_FAILED")
    require(rows[0]["temp_c"]<65,"GPU_PRE_FLIGHT_TOO_HOT")
    deltas=[(b["monotonic_ns"]-a["monotonic_ns"])/1e9
            for a,b in zip(rows,rows[1:])]
    require(all(0<dt<=3 for dt in deltas),
            "GPU_MONITOR_TIMESTAMP_STALE")
    require(report["temp_max_c"]==max(x["temp_c"] for x in rows) and
            report["temp_min_c"]==min(x["temp_c"] for x in rows) and
            report["power_max_w"]==max(x["power_w"] for x in rows) and
            report["power_min_w"]==min(x["power_w"] for x in rows) and
            report["gpu_util_max_pct"]==max(x["gpu_util_pct"] for x in rows)
            and report["fan_max_pct"]==max(x["fan_pct"] for x in rows),
            "GPU_THERMAL_SUMMARY_MISMATCH")
    require(report["host_power_attributable_to_app"] is False,
            "UNSUPPORTED_PROCESS_ENERGY_ATTRIBUTION")
    return {"name":name,"profile":profile,"stress_requested":stress,
            "valid_samples":len(rows),"temperature_max_c":report["temp_max_c"],
            "board_power_max_w":report["power_max_w"],
            "duration_s":report["duration_s"]}
def check_stress(name,report,rows):
    require(report["verdict"]=="CPJA7EC_STRESS_CPU18_LIVE_WITNESS_PASS" and
            report["run"]==name and report["cpu_affinity"]==[18] and
            report["launcher_exit"]==0 and report["samplings"]==len(rows)
            and len(rows)>=8,"CPU_STIMULUS_WITNESS_INVALID")
    live={}
    for sample in rows:
        for proc in sample["processes"]:
            if proc["affinity"]==[18]:
                live.setdefault(str(proc["pid"]),[]).append(proc["ticks"])
    growth={pid:max(vals)-min(vals) for pid,vals in live.items() if len(vals)>=3}
    require(growth and max(growth.values())>=40 and
            max(growth.values())==report["max_tick_growth"] and
            report["max_tick_growth"]>0,
            "CPU_STIMULUS_NOT_PROVEN_ACTIVE")
    return {"run":name,"observed_tick_growth":max(growth.values())}
def verify_native(root,profile,baseline,receipt):
    # Independent oracle reads source bytes and compositor screenshots; producer PASS ignored.
    from qchain_cpja7ec_independent_oracle import verify
    independent=verify(root,baseline,receipt)
    producer=load(root/"run-verdict.json")
    require(independent["verdict"]=="CPJA7EC_INDEPENDENT_NATIVE_300FRAME_PASS"
            and independent["profile"]==producer["profile"]==profile
            and independent["source_frames"]==producer["frames"]==300
            and independent["vulkan_issues"]==producer["issued"]==600
            and independent["vulkan_typed_ack"]==producer["typed_ack"]==600
            and independent["reordered_typed_ack"]==producer["out_of_order_ack"]==300
            and independent["wayland_server_presented"]==producer["wayland_server_presented"]==600
            and len(independent["screenshots"])==producer["captures"]==8,
            "INDEPENDENT_GPU_COMPOSITOR_RESULTS_DIVERGE")
    require(producer["latency_gate_pass"] and producer["max_inflight"]==2 and
            producer["received_to_submit_p95_us"]==independent["p95_us"] and
            producer["received_to_submit_p99_us"]==independent["p99_us"],
            "SOURCE_TO_PRESENT_LATENCY_NOT_REPRODUCED")
    return producer,independent
def evaluate(repo,e):
    plan=load(e/"bench/plan.json")
    require([(x["name"],x["profile"],x["stress"]) for x in plan["plan"]]==
            list(PLAN_NAMES),"PREDECLARED_CYCLE_PLAN_CHANGED")
    require(plan["preregistered_contract_sha256"]==
            digest(repo/"docs/QCHAIN-CP-JA7E-C-SUSTAINED-THERMAL-CONTRACT-20261012.md")
            and plan["viewer_binary_sha256"]==
            digest(e/"preflight/bin/qchain_cpja7_dual_viewer"),
            "PRE_RUN_CONTRACT_OR_EXACT_EXECUTABLE_TAMPERED")
    base=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
    receipt=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json")
    results=[]
    for name,profile,stress in THERMAL_NAMES:
        summary=load(e/"bench"/(name+".safety.json"))
        rows=[json.loads(line) for line in
              (e/"bench"/(name+".thermal.jsonl")).read_text().splitlines()]
        thermal=check_safety(name,profile,stress,summary,rows)
        production,independent=verify_native(e/"runs"/name,profile,base,receipt)
        stored=load(e/"oracle"/(name+".json"))
        require(stored==independent,"INDEPENDENT_ORACLE_RECEIPT_DIFFERS_FROM_RAW")
        results.append({**thermal,"frames":production["frames"],
                        "typed_acks":production["typed_ack"],
                        "p95_us":production["received_to_submit_p95_us"]})
    proofs=[]
    for name in ("pressure-proof-eco","pressure-proof-balanced"):
        report=load(e/"bench"/(name+".cpu-witness.json"))
        rows=[json.loads(line) for line in
              (e/"bench"/(name+".cpu-witness.jsonl")).read_text().splitlines()]
        proofs.append(check_stress(name,report,rows))
    # Explicitly do not infer actual pressure activity in C03/C04 from metadata alone.
    # These additional probes independently prove the same bounded stress command can run.
    return {"profile_results":results,"cpu_activity_extra_proofs":proofs}
