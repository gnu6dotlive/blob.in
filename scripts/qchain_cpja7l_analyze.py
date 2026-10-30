#!/usr/bin/env python3
"""Independent four-run matched-binary crossover and host-readback analysis."""
import argparse,hashlib,json,statistics
from pathlib import Path
from qchain_cpja7j_independent_oracle import verify as transport_verify
from qchain_cpja7k_oracle import gpu_verify

PLAN=(("pipe-a1",65536),("pipe-b1",1048576),
      ("pipe-b2",1048576),("pipe-a2",65536))
SOURCE=Path("/mnt/workbench/evidence/runs/qchain-cpja7k-20261012-01/preflight/bin/qchain_cpja7k_f4_source")
VIEWER=Path("/mnt/workbench/evidence/runs/qchain-cpja7i-20261012-01/preflight/bin/qchain_cpja7_dual_viewer")
def need(ok,why):
    if not ok:raise AssertionError(why)
def load(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def positive(root):
    e=Path(root);w=Path(__file__).resolve().parents[1]
    anchor=load(e/"preflight/anchor.json")
    expected=[list(x) for x in PLAN]
    need(anchor["order"]==expected and anchor["frames_per_run"]==1200
         and anchor["frame_interval_ms"]==16
         and anchor["parent"]=="54c2daca0fb11e40a60554458c1a6b6808529a5d",
         "PREREGISTRATION_CHANGED")
    for f,hash_before in anchor["sha256"].items():
        need(sha(Path(f))==hash_before,"ANCHORED_PROGRAM_OR_BINARY_DRIFT_"+f)
    metrics=[]
    for name,pipe in PLAN:
        r=e/"runs"/name
        broker=transport_verify(r,pipe,0)
        gpu=gpu_verify(r,1200)
        safety=load(e/"bench"/(name+".safety.json"))
        telemetry=[json.loads(row) for row in
                   (e/"bench"/(name+".thermal.jsonl")).read_text().splitlines()]
        need(broker["verdict"]=="CPJA7J_INTERVENTION_REAL_GPU_NATIVE_PASS"
             and broker["gpu_compute_frames"]==1200
             and broker["vulkan_typed_ack"]==2400
             and broker["weston_presented"]==2400
             and broker["screenshots"]==8
             and broker["pipe_bytes"]==pipe and broker["canonical_cache"]==0,
             "TRANSPORT_NATIVE_WSI_NOT_QUALIFIED_"+name)
        need(gpu["frames"]==1200 and gpu["gpu_query_count"]==21600
             and gpu["raw_bytes"]==172800
             and gpu["timestamp_period_ns"]>0,
             "SIX_COMPUTE_THREE_COPY_GPU_QUERIES_INVALID_"+name)
        need(safety["verdict"]=="CPJA7L_MATCHED_PIPE_GUARD_PASS"
             and safety["error"] is None and safety["runner_exit"]==0
             and safety["intervention_pipe_bytes"]==pipe
             and safety["canonical_cache"]==0
             and safety["temperature_abort_c"]==75
             and safety["power_abort_w"]==180
             and safety["wall_timeout_s"]==100
             and safety["host_power_attributable_to_app"] is False
             and safety["samples"]==len(telemetry)>=15,
             "THERMAL_AND_TREATMENT_GUARD_INVALID_"+name)
        need(all(x["test_name"]==name and 0<=x["temp_c"]<75
                 and 0<=x["power_w"]<180 and x["gpu_util_pct"]<=100
                 and x["query_duration_ms"]<=2500 for x in telemetry)
             and max(x["temp_c"] for x in telemetry)==safety["temp_max_c"]
             and max(x["power_w"] for x in telemetry)==safety["power_max_w"]
             and all(0<(b["monotonic_ns"]-a["monotonic_ns"])<=3_000_000_000
                     for a,b in zip(telemetry,telemetry[1:])),
             "GPU_SENSOR_WITNESS_FALSIFIED_"+name)
        metrics.append({
          "run":name,"pipe_bytes":pipe,"fps":broker["submit_fps"],
          "source_span_seconds":broker["frame_span_seconds"],
          "pipe_write_median_us":broker["pipe_write_median_us"],
          "pipe_write_p99_us":broker["pipe_write_p99_us"],
          "source_pipe_read_median_us":broker["source_read_pipe_median_us"],
          "broker_verify_median_us":broker["canonical_compare_median_us"],
          "viewer_copy_median_us":broker["client_integrity_copy_median_us"],
          "render_next_host_median_us":gpu["host_compute_readback_us"]["median_ns"],
          "host_readback_poll_median_us":gpu["host_readback_wait_us"]["median_ns"],
          "host_readback_poll_p99_us":gpu["host_readback_wait_us"]["p99_ns"],
          "copy_rgba_gpu_median_ns":gpu["copy_gpu"]["rgba"]["median_ns"],
          "copy_mask_gpu_median_ns":gpu["copy_gpu"]["mask"]["median_ns"],
          "copy_fields_gpu_median_ns":gpu["copy_gpu"]["fields"]["median_ns"],
          "gpu_query_sha256":gpu["raw_sha256"],
          "reference_digest":broker["baseline_reference_digest"],
          "sensors":len(telemetry),
          "max_board_power_w":safety["power_max_w"],
          "max_gpu_temp_c":safety["temp_max_c"]})
    need(len({x["reference_digest"] for x in metrics})==1,
         "REFERENCE_COMPARABILITY_FAILED")
    a1,b1,b2,a2=metrics
    effects=[round(b1["fps"]-a1["fps"],5),
             round(b2["fps"]-a2["fps"],5)]
    compare={
       "paired_differences_b_minus_a_fps":effects,
       "median_pair_effect_fps":statistics.median(effects),
       "direction_consistent":effects[0]*effects[1]>0,
       "performance_inference":"BOUNDED_LOCAL_EXPLORATORY_ONLY",
       "statistical_significance_proven":False,
       "physical_60fps_proven":False,
       "unique_bottleneck_causally_isolated":False,
       "power_attribution":False}
    return {"schema":"gnu6.qchain.cpja7l_matched_binary_crossover.v1",
       "verdict":"CPJA7L_FOUR_MATCHED_BINARY_NATIVE_E2E_SCOPED_PASS",
       "runs":metrics,"effect":compare,"raw_anchor_sha256":sha(e/"preflight/anchor.json"),
       "qualified_frame_count":4800,"gpu_timestamps":86400,
       "vulkan_typed_ack":9600,"wayland_presented":9600,"screenshots":32}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    need(not a.out.exists(),"ORACLE_REFUSE_OVERWRITE")
    result=positive(a.evidence)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],"fps",[(x["run"],x["fps"]) for x in result["runs"]],
          "effects",result["effect"]["paired_differences_b_minus_a_fps"],flush=True)
if __name__=="__main__":main()
