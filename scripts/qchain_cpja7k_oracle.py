#!/usr/bin/env python3
"""Independent F4 GPU copy command timestamp, source and Wayland verifier."""
import argparse,hashlib,json,re,statistics,struct
from pathlib import Path
from qchain_cpja7i_independent_oracle import verify as native_verify

BASE_NAMES=("f2","f3","shadow","blur","bloom","echo")
COPY_NAMES=("rgba","mask","fields")
KERNEL=re.compile(
    r"CPJA7JC_F4_KERNEL_TIMING seq=(\d+) period_ns=([0-9.]+) "
    r"f2_ns=([0-9.]+) f3_ns=([0-9.]+) shadow_ns=([0-9.]+) "
    r"blur_ns=([0-9.]+) bloom_ns=([0-9.]+) echo_ns=([0-9.]+) "
    r"host_readback_wait_us=(\d+) inclusive_render_next_us=(\d+)")
COPIES=re.compile(
    r"CPJA7K_F4_GPU_COPY_TIMING seq=(\d+) period_ns=([0-9.]+) "
    r"rgba_ns=([0-9.]+) mask_ns=([0-9.]+) fields_ns=([0-9.]+)")
def need(ok,msg):
    if not ok:raise AssertionError(msg)
def stat(data):
    x=sorted(data);n=len(x)
    return {"median_ns":statistics.median(x),"p95_ns":x[int((n-1)*.95)],
            "p99_ns":x[int((n-1)*.99)],"min_ns":x[0],"max_ns":x[-1],
            "sum_ns":sum(data)}
def gpu_verify(root,n):
    raw=(root/"f4-copy-query.bin").read_bytes()
    need(len(raw)==n*144,"GPU_QUERY_RAW_SIZE_INVALID")
    ticks=struct.unpack("<"+("Q"*(n*18)),raw)
    text=(root/"engine-ledger/engine.stderr").read_text(errors="replace")
    kernel=KERNEL.findall(text);copies=COPIES.findall(text)
    need(len(kernel)==len(copies)==n,"GPU_COPY_KERNEL_WITNESS_CARDINALITY")
    need([int(x[0]) for x in kernel]==list(range(n)) and
         [int(x[0]) for x in copies]==list(range(n)),
         "GPU_COPY_KERNEL_SEQUENCE_INVALID")
    expect=f"CPJA7K_F4_QUERY_STREAM_COMPLETE frames={n} records={n} gpu_queries={n*18} query_bytes={n*144} period_ns="
    need(expect in text and
         f"CPJA7G_GPU_STREAM_COMPLETE frames={n} device=1 pipelines=3 buffers=5 dispatches_per_frame=6 queue_submissions_per_frame=1" in text,
         "GPU_PERSISTENT_SESSION_COMPLETION_NOT_PROVEN")
    samples={x:[] for x in BASE_NAMES+COPY_NAMES}
    host_wait=[];host_inclusive=[]
    for frame,(kern,cp) in enumerate(zip(kernel,copies)):
        period=float(kern[1])
        need(0<period<=10000 and period==float(cp[1]),
             "GPU_QUERY_PERIOD_DIFFERENT")
        row=ticks[frame*18:(frame+1)*18]
        need(all(b>a for a,b in zip(row[::2],row[1::2])),
             "GPU_QUERY_TIMESTAMP_PAIR_NONPOSITIVE")
        need(all(row[i]>=row[i-1] for i in range(1,18)),
             "GPU_QUERY_TIMESTAMPS_OUT_OF_ORDER")
        for i,name in enumerate(BASE_NAMES+COPY_NAMES):
            ns=(row[i*2+1]-row[i*2])*period
            claim=float(kern[2+i] if i<6 else cp[2+i-6])
            need(0<ns<=50_000_000 and abs(ns-claim)<=max(1.0,period),
                 "GPU_SOURCE_QUERY_CLAIM_MISMATCH_"+name)
            samples[name].append(ns)
        host_wait.append(int(kern[8]))
        host_inclusive.append(int(kern[9]))
    need(all(0<=x<=5_000_000 for x in host_wait) and
         all(0<x<=5_000_000 for x in host_inclusive),
         "GPU_HOST_WAIT_RECORD_INVALID")
    return {"raw_sha256":hashlib.sha256(raw).hexdigest(),
            "raw_bytes":len(raw),"frames":n,"gpu_query_count":n*18,
            "compute_gpu":{x:stat(samples[x]) for x in BASE_NAMES},
            "copy_gpu":{x:stat(samples[x]) for x in COPY_NAMES},
            "host_readback_wait_us":stat(host_wait),
            "host_compute_readback_us":stat(host_inclusive),
            "timestamp_period_ns":float(kernel[0][1])}
def verify(root,frames=1200,validate_wsi=True):
    root=Path(root);gpu=gpu_verify(root,frames)
    data={"schema":"gnu6.qchain.cpja7k_real_gpu_copy_queries.v1",
          "verdict":"CPJA7K_REAL_THREE_READBACK_COPY_TIMESTAMP_SCOPED_PASS",
          "gpu":gpu,"frame_count":frames,"compute_pass_count":6,
          "gpu_copy_count":3,"copy_commands_exclusive_of_host_poll":True,
          "copy_commands_exclusive_of_pcie_total_latency":True,
          "real_gpu_timestamp_pairs":frames*9,"source_device_creations":1}
    if validate_wsi:
        native=native_verify(root,33)
        need(native["frames"]==frames and
             native["vulkan_typed_acks"]==frames*2 and
             native["weston_presented"]==frames*2 and
             native["screenshots"]==8,"NATIVE_WSI_VISUAL_PROOF_NOT_QUALIFIED")
        data["native"]=native
    return data
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True,type=Path)
    p.add_argument("--frames",type=int,default=1200)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--no-wsi",action="store_true")
    a=p.parse_args()
    need(not a.out.exists(),"REFUSE_OVERWRITE_ORACLE")
    d=verify(a.root,a.frames,not a.no_wsi)
    a.out.write_text(json.dumps(d,indent=2)+"\n")
    print("CPJA7K_INDEPENDENT_PASS",d["frame_count"],
          "query_count",d["gpu"]["gpu_query_count"],
          "rgba_p99_ns",d["gpu"]["copy_gpu"]["rgba"]["p99_ns"],
          "fields_p99_ns",d["gpu"]["copy_gpu"]["fields"]["p99_ns"],flush=True)
if __name__=="__main__":main()
