#!/usr/bin/env python3
"""CP-JA7I reread raw evidence, independent GPU oracle and safety streams."""
import hashlib,json
from pathlib import Path
from qchain_cpja7i_independent_oracle import verify

RUNS=(("baseline-33-02",33),("target-16-02",16))
NEGATIVES=(("no-recovery",40,1),("double-loss",44,2),
           ("no-injection-02",120,0))
def need(cond,why):
    if not cond:raise AssertionError(why)
def load(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def assess(repo,e):
    anchor=load(e/"preflight/anchor-02.json")
    need(anchor["parent"]=="f99eebaa2e253ad3b2abbc4c339bbcd7c9425027" and
         anchor["viewer_sha256"]==sha(e/"preflight/bin/qchain_cpja7_dual_viewer") and
         anchor["engine_sha256"]==sha(e/"preflight/bin/qchain_cpja7h_timing_gpu_live") and
         anchor["contract_sha256"]==sha(repo/"docs/QCHAIN-CP-JA7I-GPU-TIMESTAMP-CAUSALITY-CONTRACT-20261012.md") and
         anchor["plans"]==[
           {"run":"baseline-33-02","interval_ms":33,"frames":1200},
           {"run":"target-16-02","interval_ms":16,"frames":1200}],
         "UNQUALIFIED_BINARY_OR_PREREGISTRATION_DRIFT")
    results=[]
    for name,interval in RUNS:
        trace=verify(e/"runs"/name,interval)
        saved=load(e/"oracle"/(name+".json"))
        producer=load(e/"runs"/name/"run-verdict.json")
        sensor=load(e/"bench"/(name+".safety.json"))
        samples=[json.loads(row) for row in
                 (e/"bench"/(name+".thermal.jsonl")).read_text().splitlines()]
        need(trace==saved and
             trace["verdict"]=="CPJA7I_AUTHENTIC_WGPU_PASS_TIMESTAMP_SCOPED_PASS" and
             trace["frames"]==producer["frames"]==1200 and
             trace["vulkan_typed_acks"]==producer["typed_ack"]==2400 and
             trace["weston_presented"]==2400 and trace["gpu_queries"]==4800 and
             trace["gpu_query_raw_bytes"]==38400 and trace["screenshots"]==8 and
             trace["gpu_period_ns_per_tick"]>0 and
             trace["empty_source_poll_counter_instrumented"] is False,
             "INDEPENDENT_GPU_TIMESTAMP_NATIVE_WSI_DIVERGED_"+name)
        need(sensor["schema"]=="gnu6.qchain.cpja7h_board_guard.v1" and
             sensor["verdict"]=="CPJA7H_GUARDED_ATTRIBUTION_PASS" and
             sensor["runner_exit"]==0 and sensor["error"] is None and
             sensor["temperature_abort_c"]==75 and
             sensor["power_abort_w"]==180 and sensor["wall_timeout_s"]==100 and
             sensor["host_power_attributable_to_app"] is False and
             len(samples)==sensor["samples"]>=15 and
             max(x["temp_c"] for x in samples)==sensor["temp_max_c"] and
             max(x["power_w"] for x in samples)==sensor["power_max_w"] and
             all(x["test_name"]==name and 0<=x["temp_c"]<75 and
                 0<=x["power_w"]<180 and
                 0<=x["gpu_util_pct"]<=100 and
                 0<=x["query_duration_ms"]<=2500 for x in samples),
             "GPU_BOARD_GUARD_SPOOFED_"+name)
        need(all(0<(b["monotonic_ns"]-a["monotonic_ns"])<=3_000_000_000
                 for a,b in zip(samples,samples[1:])),
             "NVIDIA_SENSOR_SAMPLE_STALE_"+name)
        results.append({
          "name":name,"interval_ms_requested":interval,
          "frame_count":1200,"native_typed_acks":2400,
          "gpu_hardware_queries":4800,
          "real_gpu_period_ns":trace["gpu_period_ns_per_tick"],
          "primary_render_pass_gpu_ns":trace["primary_gpu_pass_ns"],
          "secondary_render_pass_gpu_ns":trace["secondary_gpu_pass_ns"],
          "host_draw_api_us":trace["draw_api_us"],
          "wake_late_us":trace["wake_late_us"],
          "ready_dwell_us":trace["frame_ready_dwell_us"],
          "fps_submitted":trace["observed_submit_fps"],
          "source_span_seconds":trace["native_span_seconds"],
          "gpu_query_sha256":trace["gpu_query_raw_sha256"],
          "source_host_p50_compute_readback_us":trace["host_stages"]["compute_readback_host_us"]["median_us"],
          "source_pipe_write_p50_us":trace["host_stages"]["pipe_write_us"]["median_us"],
          "client_integrity_copy_p50_us":trace["host_stages"]["integrity_copy_us"]["median_us"],
          "sensor_samples":len(samples),
          "maximum_gpu_temp_c":sensor["temp_max_c"],
          "maximum_board_power_w":sensor["power_max_w"]})
    for name,frames,injections in NEGATIVES:
        verdict=load(e/"negative"/name/"negative-verdict.json")
        need(verdict["mode"]==("no-injection" if name=="no-injection-02" else name)
             and verdict["submitted_frames"]==frames and
             verdict["injections"]==injections and
             verdict["viewer_exit"]!=0 and not verdict["success_receipt"] and
             verdict["verdict"].endswith("_FAIL_CLOSED_PASS") and
             not (e/"negative"/name/"run-verdict.json").exists(),
             "NEGATIVE_CONTROL_NOT_FAIL_CLOSED_"+name)
    need("CPJA7I_ADVERSARIAL_11_OF_11_PASS" in
         (e/"oracle/adversarial-final.log").read_text(),
         "ELEVEN_ADVERSARIAL_MUTATIONS_NOT_REJECTED")
    for path,needle in (
       ("preflight/clippy.log","Finished"),
       ("preflight/ja7h-compat.log","Finished"),
       ("preflight/blob-frame-tests.log","31 passed; 0 failed")):
        need(needle in (e/path).read_text(),"RUST_REGRESSION_NOT_PASS_"+path)
    need(not (e/"runs/baseline-33/run-verdict.json").exists() and
         load(e/"bench/baseline-33.safety.json")["verdict"]=="CPJA7H_GUARDED_ATTRIBUTION_HOLD",
         "INITIAL_QUERY_SET_LIMIT_FAILURE_RELABELED")
    need(not (e/"negative/no-injection/negative-verdict.json").exists(),
         "EARLIER_MISSING_QUERY_ENV_NEGATIVE_FALSE_PASS")
    return results
