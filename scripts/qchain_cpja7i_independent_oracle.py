#!/usr/bin/env python3
"""Independent GPU hardware timestamp bytes, loop pacing and native source oracle."""
import argparse,hashlib,json,re,statistics,struct
from pathlib import Path
from qchain_cpja7h_independent_oracle import verify as verify_native
from qchain_cpja7h_analyze import analyze as analyze_stages

BASE=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
RECEIPT=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json")
CAUSAL=re.compile(r"CPJA7I_FRAME_CAUSAL seq=(\d+) requested_interval_us=(\d+) wake_late_us=(\d+) ready_dwell_us=(\d+) empty_polls=(\d+) draw_api_us=(\d+) deadline_remaining_us=(\d+)")
QUERY=re.compile(r"CPJA7I_GPU_QUERY_COMPLETE frames=(\d+) queries=(\d+) period_ns=([0-9.]+) raw_bytes=(\d+) raw_sha256=([0-9a-f]{64}) primary_total_ns=([0-9.]+) secondary_total_ns=([0-9.]+)")
def need(ok,msg):
    if not ok:raise AssertionError(msg)
def percentiles(values):
    ordered=sorted(values)
    return {"min":min(ordered),"p50":statistics.median(ordered),
            "p95":ordered[int((len(ordered)-1)*.95)],
            "p99":ordered[int((len(ordered)-1)*.99)],
            "max":max(ordered)}
def verify(root,interval_ms):
    root=Path(root)
    native=verify_native(root,BASE,RECEIPT)
    stages=analyze_stages(root)
    app=(root/"viewer.stdout").read_text(errors="replace")
    m=QUERY.findall(app)
    need(len(m)==1 and app.count("CPJA7I_GPU_QUERY_CAPABILITY")==1,
         "GPU_TIMESTAMP_QUERY_CAPABILITY_OR_COMPLETION_MISSING")
    frames,queries,period_s,size_s,expected_sha,total_primary,total_secondary=m[0]
    need(int(frames)==1200 and int(queries)==4800 and int(size_s)==38400,
         "QUERY_CARDINALITY_OR_RAW_BYTES_FALSIFIED")
    period=float(period_s)
    need(0<period<10000 and period==period and
         native["source_frames"]==1200 and native["vulkan_typed_ack"]==2400
         and native["wayland_server_presented"]==2400
         and len(native["screenshots"])==8,
         "GPU_FEATURE_OR_NATIVE_WSI_UNPROVEN")
    raw=(root/"gpu-query-raw.bin").read_bytes()
    sha=hashlib.sha256(raw).hexdigest()
    need(len(raw)==38400 and sha==expected_sha,
         "GPU_RAW_QUERY_DIGEST_OR_BYTE_SIZE_MISMATCH")
    t=struct.unpack("<4800Q",raw)
    primary=[];secondary=[]
    for i in range(1200):
        a,b=t[i*2:i*2+2]
        c,d=t[2400+i*2:2400+i*2+2]
        need(b>a and d>c,"GPU_REAL_TIMESTAMP_PAIR_INVALID")
        primary.append((b-a)*period)
        secondary.append((d-c)*period)
    need(all(0<x<=50_000_000 for x in primary+secondary),
         "GPU_TIMESTAMP_DURATION_IMPLAUSIBLE")
    need(abs(sum(primary)-float(total_primary))<max(1000,1200*period)
         and abs(sum(secondary)-float(total_secondary))<max(1000,1200*period),
         "GPU_QUERY_SUMS_FALSIFIED")
    rows=CAUSAL.findall(app)
    need(len(rows)==1200 and
         [int(r[0]) for r in rows]==list(range(1200)) and
         {int(r[1]) for r in rows}=={interval_ms*1000},
         "EVENT_LOOP_CORRELATION_NOT_COMPLETE")
    fields=("seq","requested_interval_us","wake_late_us","ready_dwell_us",
            "empty_polls","draw_api_us","deadline_remaining_us")
    events=[dict(zip(fields,map(int,row))) for row in rows]
    need(all(e["draw_api_us"]>0 and e["draw_api_us"]<2_000_000
             and e["wake_late_us"]<3_000_000 and e["empty_polls"]<100
             for e in events),"HOST_CAUSAL_SPAN_INVALID")
    result={"schema":"gnu6.qchain.cpja7i_gpu_query_independent.v1",
            "verdict":"CPJA7I_AUTHENTIC_WGPU_PASS_TIMESTAMP_SCOPED_PASS",
            "run":root.name,"requested_interval_ms":interval_ms,
            "frames":1200,"vulkan_typed_acks":2400,
            "weston_presented":2400,"screenshots":8,
            "gpu_query_raw_sha256":sha,"gpu_query_raw_bytes":len(raw),
            "gpu_queries":4800,"gpu_period_ns_per_tick":period,
            "primary_gpu_pass_ns":percentiles(primary),
            "secondary_gpu_pass_ns":percentiles(secondary),
            "primary_gpu_total_ns":sum(primary),
            "secondary_gpu_total_ns":sum(secondary),
            "observed_submit_fps":round(1199/native["active_span_seconds"],4),
            "native_span_seconds":native["active_span_seconds"],
            "wake_late_us":percentiles([e["wake_late_us"] for e in events]),
            "frame_ready_dwell_us":percentiles([e["ready_dwell_us"] for e in events]),
            "draw_api_us":percentiles([e["draw_api_us"] for e in events]),
            "deadline_remaining_us":percentiles([e["deadline_remaining_us"] for e in events]),
            "empty_source_polls":None,
            "empty_source_poll_counter_instrumented":False,
            "host_stages":stages["measurements"],
            "f4_compute_gpu_timestamp":False,
            "gpu_and_host_clocks_comparable":False,
            "photon_timing":False,"cp03_hybrid60":False}
    return result
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--interval-ms",type=int,choices=[16,33],required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    need(not args.out.exists(),"REFUSE_OVERWRITE_ORACLE")
    report=verify(args.run,args.interval_ms)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],report["run"],"fps",report["observed_submit_fps"],
          "primary_gpu_p99_ns",report["primary_gpu_pass_ns"]["p99"],
          "secondary_gpu_p99_ns",report["secondary_gpu_pass_ns"]["p99"],flush=True)
if __name__=="__main__":main()
