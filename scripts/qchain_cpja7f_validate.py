#!/usr/bin/env python3
"""CP-JA7F independent thermal, process, and source authority reconciliation."""
import json
import statistics
from pathlib import Path
from qchain_cpja7f_independent_oracle import verify as verify_wsi

BASE=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
CPU=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json")
NAME="resident-20min-02"

def need(ok,code):
    if not ok:raise AssertionError(code)
def load(p):return json.loads(p.read_text())
def stream(p):return [json.loads(line) for line in p.read_text().splitlines()]
def sensor_analysis(rows,complete):
    need(len(rows)>=5,"SENSOR_STREAM_EMPTY")
    need(all(row["test_name"]==NAME and
             0<=row["temp_c"]<75 and
             0<=row["power_w"]<180 and
             0<=row["gpu_util_pct"]<=100 and
             0<=row["fan_pct"]<=100 and
             0<=row["mem_mib"]<65536 and
             0<=row["query_duration_ms"]<=2500
             for row in rows),"SENSOR_UNSAFE_VALUE_OR_OWNERSHIP")
    need(rows[0]["temp_c"]<65,"SENSOR_BASELINE_HOT")
    gaps=[(b["monotonic_ns"]-a["monotonic_ns"])/1e9
          for a,b in zip(rows,rows[1:])]
    need(all(0<dt<=3 for dt in gaps),"SENSOR_GAP_GT_3SEC")
    span=(rows[-1]["monotonic_ns"]-rows[0]["monotonic_ns"])/1e9
    if complete:
        need(len(rows)>=1150 and span>=1200,"SENSOR_CONTINUITY_20MIN_UNPROVEN")
    first=rows[0]["monotonic_ns"]
    last=rows[-1]["monotonic_ns"]
    first_window=[x["temp_c"] for x in rows
                  if x["monotonic_ns"]-first<=300_000_000_000]
    last_window=[x["temp_c"] for x in rows
                 if last-x["monotonic_ns"]<=300_000_000_000]
    return {
      "samples":len(rows),"span_s":round(span,3),
      "temp_min_c":min(x["temp_c"] for x in rows),
      "temp_max_c":max(x["temp_c"] for x in rows),
      "power_min_w":min(x["power_w"] for x in rows),
      "power_max_w":max(x["power_w"] for x in rows),
      "peak_gpu_util_pct":max(x["gpu_util_pct"] for x in rows),
      "max_sampling_gap_s":round(max(gaps),3),
      "first_300s_temperature_median_c":statistics.median(first_window),
      "last_300s_temperature_median_c":statistics.median(last_window),
      "energy_attributable_to_experiment":False,
      "temperature_equilibrium_proven":False
    }
def process_analysis(rows,complete):
    need(rows,"PID_WITNESS_EMPTY")
    monitored=[r for r in rows if r["viewer"] and r["weston"]]
    need(len(monitored)==len(rows) or
         (len(rows)==len(monitored)+1 and
          (not rows[-1]["viewer"] or not rows[-1]["weston"])),
         "VIEWER_WESTON_GAP_OR_EARLY_LOSS")
    viewers={entry["pid"] for row in monitored for entry in row["viewer"]}
    westons={entry["pid"] for row in monitored for entry in row["weston"]}
    need(len(viewers)==len(westons)==1 and
         all(len(row["viewer"])==len(row["weston"])==1 for row in monitored),
         "PROCESS_RESIDENT_IDENTITY_CHANGED")
    need(all(x["cpu_affinity"]==[18,19]
             for row in monitored for x in row["viewer"]+row["weston"]),
         "PROCESS_AFFINITY_DRIFT")
    start=monitored[0]["monotonic_ns"]
    stop=monitored[-1]["monotonic_ns"]
    duration=(stop-start)/1e9
    if complete:
        need(len(monitored)>=400 and duration>=800,
             "PROCESS_WITNESS_COVERAGE_INSUFFICIENT")
    stress={}
    for row in monitored:
        for proc in row["stress"]:
            if proc["cpu_affinity"]==[18]:
                stress.setdefault(proc["pid"],[]).append(
                    (row["monotonic_ns"],proc["cpu_ticks"]))
    eligible={}
    for pid,records in stress.items():
        if len(records)>=6:
            tick_gain=records[-1][1]-records[0][1]
            if tick_gain>40:
                eligible[pid]={"samples":len(records),
                  "tick_increase":tick_gain,
                  "span_s":round((records[-1][0]-records[0][0])/1e9,2)}
    if complete:
        need(eligible,"STRESS_CPU18_TICKS_NOT_OBSERVED")
    return {"sampling_count":len(monitored),
            "sampled_residency_seconds":round(duration,2),
            "viewer_pid":next(iter(viewers)),
            "weston_pid":next(iter(westons)),
            "stress_cpu18":eligible,
            "continuous_from_first_sample":True,
            "captured_entire_device_lifetime":False}
def validate(repo,root):
    samples=stream(root/"bench"/(NAME+".thermal.jsonl"))
    safety=load(root/"bench"/(NAME+".safety.json"))
    sensor=sensor_analysis(samples,True)
    need(safety["schema"]=="gnu6.qchain.cpja7ec_thermal_guard.v1" and
         safety["verdict"]=="CPJA7EC_SAFETY_BOUNDED_RUN_PASS" and
         safety["error"] is None and safety["runner_exit"]==0 and
         safety["stress_cpu_18"] is True,
         "SAFETY_CONTINUOUS_VERDICT_OR_STRESS_MISSING")
    need(safety["samples"]==sensor["samples"] and
         safety["temp_min_c"]==sensor["temp_min_c"] and
         safety["temp_max_c"]==sensor["temp_max_c"] and
         safety["power_min_w"]==sensor["power_min_w"] and
         safety["power_max_w"]==sensor["power_max_w"] and
         safety["temperature_abort_c"]==75 and
         safety["power_abort_w"]==180 and
         safety["wall_timeout_s"]==1500,
         "SENSOR_SUMMARY_TAMPERED")
    process=process_analysis(stream(
        root/"telemetry/residency-process-witness.jsonl"),True)
    producer=load(root/"runs"/NAME/"run-verdict.json")
    independently=verify_wsi(root/"runs"/NAME,BASE,CPU)
    saved=load(root/"oracle"/(NAME+".json"))
    need(saved==independently and
         independently["verdict"]=="CPJA7F_INDEPENDENT_TWENTY_MIN_RESIDENCY_PASS",
         "INDEPENDENT_DEVICE_ORACLE_DIVERGENCE")
    need(producer["frames"]==independently["source_frames"]==300 and
         producer["issued"]==independently["vulkan_issues"]==600 and
         producer["typed_ack"]==independently["vulkan_typed_ack"]==600 and
         producer["out_of_order_ack"]==independently["reordered_typed_ack"]==300 and
         producer["elapsed_between_first_last_us"]==
           independently["residency_observed_span_us"]>=1_200_000_000 and
         producer["cadence_gaps_in_3_to_6_seconds"]==
           independently["interframe_gaps_3_to_6_seconds"]>=270 and
         producer["longest_consecutive_cadence_streak"]==
           independently["longest_consecutive_cadence_streak"]>=270 and
         len(independently["screenshots"])==8,
         "PRODUCER_INDEPENDENT_RECONCILIATION_FAILED")
    need(independently["wayland_server_presented"]==600 and
         independently["wayland_client_presented"]==600 and
         "CPJA7C_RECOVERY_BEGIN" not in
             (root/"runs"/NAME/"viewer.stdout").read_text(),
         "PHYSICAL_SURFACE_WITNESS_CHANGED")
    return {"sensor":sensor,"process":process,
            "native":independently,"producer":producer}
