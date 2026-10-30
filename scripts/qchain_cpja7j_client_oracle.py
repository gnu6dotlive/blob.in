#!/usr/bin/env python3
"""Independently verify sealed-memfd ownership mode with exact GPU/Wayland proof."""
import argparse,json,re,statistics
from pathlib import Path
from qchain_cpja7j_independent_oracle import verify as verify_native
HEADER=re.compile(r"CPJA7J_CLIENT_OWNERSHIP mode=(copy|mmap) immutable_sealed_memfd=1 full_sha256=1")
SAMPLE=re.compile(r"CPJA7J_CLIENT_PIXEL_MODE seq=(\d+) mode=(copy|mmap) source_sha256=([0-9a-f]{64})")
def need(v,msg):
    if not v:raise AssertionError(msg)
def verify(root,mode):
    root=Path(root)
    verified=verify_native(root,65536,0)
    viewer=(root/"viewer.stdout").read_text(errors="replace")
    declared=HEADER.findall(viewer)
    need(declared==[mode],"CLIENT_MAPPING_MODE_NOT_TRUSTED")
    events=SAMPLE.findall(viewer)
    need(len(events)==40 and
         [int(seq) for seq,_,_ in events]==list(range(0,1200,30)) and
         all(m==mode for _,m,_ in events),
         "CLIENT_MATERIALIZATION_PER_FRAME_WITNESS_INVALID")
    timeline=json.loads((root/"engine-ledger/timeline.json").read_text())
    for seq,_,dig in events:
        need(timeline["frames"][int(seq)]["pixel_sha256"]==dig,
             "CLIENT_MAPPING_SHA_DIVERGED_FROM_SOURCE")
    need(verified["gpu_compute_frames"]==1200 and
         verified["vulkan_typed_ack"]==2400 and
         verified["weston_presented"]==2400 and
         verified["render_pass_gpu_query_count"]==4800 and
         verified["canonical_full_byte_equality_checks"]==1200 and
         verified["screenshots"]==8,
         "CLIENT_NATIVE_F4_WSI_RENDER_NOT_QUALIFIED")
    return {
      "schema":"gnu6.qchain.cpja7j_client_mapped_ownership.v1",
      "verdict":"CPJA7J_CLIENT_SEALED_MEMFD_OWNERSHIP_PASS",
      "run":root.name,"mode":mode,
      "frames":1200,"full_pixel_shas":1200,
      "gpu_timestamps":4800,"vulkan_typed_acks":2400,
      "weston_presented":2400,"screen_captures":8,
      "observed_submit_fps":verified["submit_fps"],
      "client_hash_plus_copy_median_us":verified["client_integrity_copy_median_us"],
      "client_hash_plus_copy_p99_us":verified["client_integrity_copy_p99_us"],
      "source_pipe_write_median_us":verified["pipe_write_median_us"],
      "canonical_compare_median_us":verified["canonical_compare_median_us"],
      "actual_client_pixel_buffer_copy":mode=="copy",
      "cpu_sha256_remains_required":True,
      "actual_gpu_zero_copy":False
    }
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--mode",choices=("copy","mmap"),required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    need(not args.out.exists(),"REFUSE_ORACLE_OVERWRITE")
    result=verify(args.run,args.mode)
    args.out.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],result["run"],"fps",result["observed_submit_fps"],
          "client_host_integrity_us",result["client_hash_plus_copy_median_us"],flush=True)
if __name__=="__main__":main()

