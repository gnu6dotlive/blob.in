#!/usr/bin/env python3
"""Independent parser for persistent-session stress witness, not a GPU driver trace."""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

def check(ok,msg):
    if not ok:raise ValueError(msg)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def analyze(root,count,source):
    folder=root/f"single-session-{count}"
    with (folder/"out/single-session-stats.tsv").open(newline="") as f:
        rows=list(csv.DictReader(f,delimiter="\t"))
    check(len(rows)==1,"SESSION_STATS_COUNT")
    row=rows[0]
    for k,n in {"frames":count,"device_creations":1,"pipelines":3,
                "reusable_buffers":5,"rejected_invalid":1}.items():
        check(int(row[k])==n,f"SESSION_{k}_MISMATCH")
    nums={key:int(row[key]) for key in
          ("median_frame_us","p95_frame_us","p99_frame_us","max_frame_us")}
    check(0<nums["median_frame_us"]<=nums["p95_frame_us"]<=
          nums["p99_frame_us"]<=nums["max_frame_us"],"TIMING_DISTRIBUTION_BAD")
    log=(folder/("compute-v2.log" if count==1200 else "compute.log")).read_text()
    expected=f"QCHAIN_H2_SINGLE_SESSION_PASS frames={count} device=1 pipelines=3 reusable_buffers=5 rejected_invalid=1"
    check(expected in log,"SESSION_PROOF_NOT_COMPLETED")

    observed=re.findall(r"CPH2_IN_PROCESS_PROGRESS frames=(\d+) gpu_device=1",log)
    check(observed==[str(i) for i in range(200,count+1,200)],
          "PROGRESS_CHECKPOINTS_MISSING")
    t=(folder/("process-time-v2.txt" if count==1200 else "process-time.txt")).read_text()
    elapsed=re.search(r"Elapsed \(wall clock\) time .*?: (\d+:\d+(?:\.\d+)?)",t)
    rss=re.search(r"Maximum resident set size \(kbytes\): (\d+)",t)
    check(elapsed is not None and rss is not None,"RESOURCE_MEASUREMENTS_MISSING")
    prefix,sec=elapsed.group(1).split(":")
    seconds=int(prefix)*60+float(sec)
    check(seconds>0 and int(rss.group(1))>0,"INVALID_WALL_MEMORY")
    return {"frames":count,"device_creations":1,"pipelines":3,
       "reusable_buffers":5,"invalid_digest_rejections":1,
       "render_call_us":nums,"process_elapsed_seconds":seconds,
       "peak_rss_kib":int(rss.group(1)),
       "gpu_frame_equality_source":"Rust fixture checks each output versus CP-F raw reference",
       "independent_pixel_readbacks_written":False,
       "compute_log_sha256":sha(folder/("compute-v2.log" if count==1200 else "compute.log")),
       "stats_sha256":sha(folder/"out/single-session-stats.tsv")}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",required=True,type=Path)
    ap.add_argument("--source",required=True,type=Path)
    ap.add_argument("--archived-source",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    a=ap.parse_args()
    check(not a.out.exists(),"REFUSE_OVERWRITE")
    check(sha(a.source)==sha(a.archived_source),"TEST_WITNESS_SOURCE_DRIFT")
    result={"schema":"gnu6.qchain.h2_persistent_session_oracle.v1",
       "verdict":"QCHAIN_H2_SINGLE_SESSION_5000_FRAMES_PASS_SOURCE_LEVEL",
       "soak_cases":[analyze(a.root,1200,a.source),analyze(a.root,5000,a.source)],
       "witness_sha256":sha(a.source),
       "gpu_driver_allocations_independently_measured":False,
       "new_wayland_capture":"NOT_RUN"}
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],"sessions",len(result["soak_cases"]))
if __name__=="__main__":main()
