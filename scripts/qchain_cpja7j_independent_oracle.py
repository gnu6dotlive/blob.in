#!/usr/bin/env python3
"""CP-JA7J independent intervention and byte-level native oracle."""
import argparse,hashlib,json,re,statistics
from pathlib import Path
from qchain_cpja7i_independent_oracle import verify as verify_native
BASE=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
HEADER=re.compile(r"CPJA7J_INTERVENTION_CONFIG pipe_bytes=(\d+) canonical_cache=(\d) baseline_blobs=(\d+) reference_digest=([0-9a-f]{64})")
BYTE_COMPARE=re.compile(r"CPJA7J_FULL_BYTE_COMPARE seq=(\d+) reference_sha256=([0-9a-f]{64}) status=EQUAL bytes=(\d+)")
def need(v,m):
    if not v:raise AssertionError(m)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def verify(root,pipe_bytes,cache):
    root=Path(root)
    interval=16
    native=verify_native(root,interval)
    stdout=(root/"source.stdout").read_text(errors="replace")
    header=HEADER.findall(stdout)
    need(len(header)==1 and stdout.count("CPJA7J_INTERVENTION_CONFIG")==1,
         "INTERVENTION_WITNESS_MISSING")
    hp,hc,num,digest_text=header[0]
    need(int(hp)==pipe_bytes and int(hc)==cache and int(num)==12,
         "INTERVENTION_CONFIRMED_PIPE_OR_CACHE_MISMATCH")
    timeline=json.loads((root/"engine-ledger/timeline.json").read_text())
    need(timeline["gpu_device_single_session"] is True and
         timeline["engine_exit"]==0 and
         timeline["cpja7j_pipe_bytes"]==pipe_bytes and
         timeline["cpja7j_canonical_cache"]==str(cache) and
         timeline["cpja7j_full_byte_comparisons"]==1200 and
         len(timeline["frames"])==1200 and
         [q["seq"] for q in timeline["frames"]]==list(range(1200)),
         "BROKER_PRODUCER_TIMELINE_OR_FULL_BYTE_COMPARE_MISMATCH")
    byname=timeline["cpja7j_reference_sha256"]
    need(len(byname)==12,"BASELINE_REFERENCE_BLOB_CARDINALITY_CHANGED")
    actual={p.name:digest(p) for p in
            (BASE/k for k in sorted(byname))}
    need(actual==byname and
         hashlib.sha256(json.dumps(byname,sort_keys=True).encode()).hexdigest()==digest_text,
         "REFERENCE_BLOB_DIGEST_FALSIFIED")
    checked=BYTE_COMPARE.findall(stdout)
    need(len(checked)==40 and [int(q[0]) for q in checked]==list(range(0,1200,30)),
         "FULL_BYTE_COMPARISON_WITNESS_MISSING")
    for seq,reported_hash,size in checked:
        n=int(seq)
        stage=min(n,4)
        variant=0 if n<5 else ((n-5)//12)%8
        material=("ceramic","gel","metal","paper")[variant//2]
        ref=f"state{stage}-{material}-frame{variant%2}-dpr2.gpu-rgba.bin"
        need(reported_hash==byname[ref] and int(size)==786432,
             "FULL_BYTE_CANONICAL_COMPARISON_FORGED")
    for row in timeline["frames"]:
        seq=row["seq"]
        stage=min(seq,4)
        variant=0 if seq<5 else ((seq-5)//12)%8
        material=("ceramic","gel","metal","paper")[variant//2]
        ref=f"state{stage}-{material}-frame{variant%2}-dpr2.gpu-rgba.bin"
        need(row["stage"]==stage and row["variant"]==variant and
             row["pixel_sha256"]==byname[ref] and
             row["canonical_verify_us"]>=0 and
             row["pipe_read_us"]>=0,
             "FULL_SOURCE_BYTES_OR_TIMING_NOT_REPRODUCIBLE")
    p99=lambda v:sorted(v)[int((len(v)-1)*.99)]
    t=native["host_stages"]
    return {
      "schema":"gnu6.qchain.cpja7j_controlled_intervention.v1",
      "verdict":"CPJA7J_INTERVENTION_REAL_GPU_NATIVE_PASS",
      "run":root.name,"pipe_bytes":pipe_bytes,"canonical_cache":cache,
      "baseline_reference_digest":digest_text,
      "canonical_reference_blobs":12,
      "canonical_full_byte_equality_checks":1200,
      "gpu_compute_frames":1200,
      "vulkan_typed_ack":native["vulkan_typed_acks"],
      "weston_presented":native["weston_presented"],
      "render_pass_gpu_query_count":native["gpu_queries"],
      "gpu_query_sha256":native["gpu_query_raw_sha256"],
      "screenshots":native["screenshots"],
      "submit_fps":native["observed_submit_fps"],
      "frame_span_seconds":native["native_span_seconds"],
      "gpu_render_p99_ns":native["primary_gpu_pass_ns"]["p99"],
      "pipe_write_median_us":t["pipe_write_us"]["median_us"],
      "pipe_write_p99_us":t["pipe_write_us"]["p99_us"],
      "canonical_compare_median_us":t["canonical_verify_us"]["median_us"],
      "canonical_compare_p99_us":t["canonical_verify_us"]["p99_us"],
      "client_integrity_copy_median_us":t["integrity_copy_us"]["median_us"],
      "client_integrity_copy_p99_us":t["integrity_copy_us"]["p99_us"],
      "source_read_pipe_median_us":t["pipe_read_us"]["median_us"],
      "source_read_pipe_p99_us":t["pipe_read_us"]["p99_us"],
      "compute_readback_median_us":t["compute_readback_host_us"]["median_us"],
      "submit_gap_p99_us":p99([int(v) for v in
           re.findall(r"CPJA7I_FRAME_CAUSAL seq=\d+ requested_interval_us=\d+ wake_late_us=(\d+)",
                      (root/"viewer.stdout").read_text(errors="replace"))]),
      "claims_causality_of_single_bottleneck":False
    }
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--pipe-bytes",type=int,required=True,choices=(65536,1048576))
    p.add_argument("--cache",type=int,required=True,choices=(0,1))
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    need(not a.out.exists(),"REFUSE_OVERWRITE_ORACLE")
    result=verify(a.run,a.pipe_bytes,a.cache)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],result["run"],"fps",result["submit_fps"],
          "pipe_us",result["pipe_write_median_us"],
          "canonical_us",result["canonical_compare_median_us"],flush=True)
if __name__=="__main__":main()

