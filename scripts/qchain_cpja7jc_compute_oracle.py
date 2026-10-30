#!/usr/bin/env python3
"""Independent byte-level replay of six authentic F4 GPU compute pass timestamps."""
import argparse,hashlib,json,re,statistics,struct
from pathlib import Path
NAMES=("f2","f3","shadow","blur","bloom","echo")
TIMING=re.compile(
    r"CPJA7JC_F4_KERNEL_TIMING seq=(\d+) period_ns=([0-9.]+) "
    r"f2_ns=([0-9.]+) f3_ns=([0-9.]+) shadow_ns=([0-9.]+) "
    r"blur_ns=([0-9.]+) bloom_ns=([0-9.]+) echo_ns=([0-9.]+) "
    r"host_readback_wait_us=(\d+) inclusive_render_next_us=(\d+)")
def need(ok,msg):
    if not ok:raise AssertionError(msg)
def stats(v):
    x=sorted(v)
    return {"min_ns":min(x),"median_ns":statistics.median(x),
        "p95_ns":x[int((len(x)-1)*.95)],
        "p99_ns":x[int((len(x)-1)*.99)],"max_ns":max(x),
        "total_ns":sum(x)}
def verify(root,n=1200):
    raw=(root/"f4-compute-query.bin").read_bytes()
    need(len(raw)==n*96,"RAW_GPU_TIMESTAMP_BYTES_INCORRECT")
    ticks=struct.unpack("<"+("Q"*(n*12)),raw)
    engine=(root/"engine-ledger/engine.stderr").read_text(errors="replace")
    rows=TIMING.findall(engine)
    need(len(rows)==n and [int(r[0]) for r in rows]==list(range(n)),
         "GPU_KERNEL_WITNESSES_NOT_SEQUENTIAL")
    complete=f"CPJA7JC_F4_QUERY_STREAM_COMPLETE frames={n} records={n} query_bytes={n*96} period_ns="
    need(complete in engine,"GPU_F4_TIMESTAMP_SOURCE_NOT_COMPLETED")
    need(f"CPJA7G_GPU_STREAM_COMPLETE frames={n} device=1 pipelines=3 buffers=5 dispatches_per_frame=6 queue_submissions_per_frame=1" in engine,
         "F4_SINGLE_PERSISTENT_GPU_SESSION_NOT_PROVEN")
    all_ns=[[] for _ in NAMES]
    waits=[]
    inclusive=[]
    for frame,row in enumerate(rows):
        period=float(row[1])
        need(0<period<=10000 and period==period,"GPU_PERIOD_INVALID")
        for i in range(6):
            a,b=ticks[frame*12+2*i:frame*12+2*i+2]
            need(b>a,"INVALID_GPU_PASS_TIMESTAMP_PAIR")
            ns=float(b-a)*period
            need(0<ns<=50_000_000,"GPU_PASS_DURATION_OUT_OF_BOUNDS")
            need(abs(ns-float(row[2+i]))<=max(1.0,period),
                 "ENGINE_GPU_TIMING_DIFFERS_FROM_RAW_TICKS_"+NAMES[i])
            all_ns[i].append(ns)
        waits.append(int(row[8]))
        inclusive.append(int(row[9]))
    need(all(0<x<5_000_000 for x in inclusive) and all(0<=x<5_000_000 for x in waits),
         "HOST_READBACK_SPANS_INVALID")
    return {"schema":"gnu6.qchain.cpja7jc_source_gpu_timestamps.v1",
       "verdict":"CPJA7JC_SIX_TRUE_F4_GPU_COMPUTE_PASSES_PASS",
       "frames":n,"raw_gpu_query_bytes":len(raw),
       "raw_gpu_query_sha256":hashlib.sha256(raw).hexdigest(),
       "gpu_hardware_timestamp_count":n*12,
       "dispatches":n*6,"queue_submissions":n,
       "pass_gpu_timing":dict(zip(NAMES,map(stats,all_ns))),
       "host_inclusive_render_next_us":stats(inclusive),
       "host_readback_wait_us":stats(waits),
       "actual_f4_compute_gpu_timestamps":True,
       "per_gpu_copy_timestamps":False}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--frames",type=int,default=1200)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    need(not a.out.exists(),"REFUSE_OVERWRITE_SOURCE_ORACLE")
    proof=verify(a.root,a.frames)
    a.out.write_text(json.dumps(proof,indent=2)+"\n")
    print(proof["verdict"],"frames",a.frames,"sha256",proof["raw_gpu_query_sha256"],
          "bloom_p99_us",proof["pass_gpu_timing"]["bloom"]["p99_ns"]/1000,flush=True)
if __name__=="__main__":main()
