#!/usr/bin/env python3
"""Independent per-frame host-stage timing admission and distribution."""
import argparse,collections,json,re,statistics
from pathlib import Path
FIELDS={
 "engine":("engine-ledger/engine.stderr",r"CPJA7H_ENGINE_TIMING seq=(\d+) compute_readback_host_us=(\d+) pipe_write_us=(\d+)",("compute_readback_host_us","pipe_write_us")),
 "broker":("source.stdout",r"CPJA7H_BROKER_TIMING seq=(\d+) pipe_read_us=(\d+) canonical_verify_us=(\d+) memfd_seal_us=(\d+) memfd_send_us=(\d+)",("pipe_read_us","canonical_verify_us","memfd_seal_us","memfd_send_us")),
 "client":("viewer.stdout",r"CPJA7H_CLIENT_TIMING seq=(\d+) request_to_packet_us=(\d+) integrity_copy_us=(\d+) channel_block_us=(\d+)",("request_to_packet_us","integrity_copy_us","channel_block_us")),
 "viewer":("viewer.stdout",r"CPJA7H_VIEWER_TIMING seq=(\d+) texture_upload_api_us=(\d+) primary_acquire_us=(\d+) primary_encode_us=(\d+) primary_submit_api_us=(\d+) primary_present_api_us=(\d+) secondary_acquire_us=(\d+) secondary_encode_us=(\d+) secondary_submit_api_us=(\d+) secondary_present_api_us=(\d+)",("texture_upload_api_us","primary_acquire_us","primary_encode_us","primary_submit_api_us","primary_present_api_us","secondary_acquire_us","secondary_encode_us","secondary_submit_api_us","secondary_present_api_us")),
}
def need(ok,msg):
    if not ok:raise AssertionError(msg)
def analyze(root,frames=1200):
    values={}
    raw={}
    for source,(file,pattern,names) in FIELDS.items():
        events=re.findall(pattern,(root/file).read_text(errors="replace"))
        need(len(events)==frames,"STAGE_CARDINALITY_"+source)
        seq=[int(x[0]) for x in events]
        need(seq==list(range(frames)),"STAGE_FRAME_SEQUENCE_"+source)
        for index,name in enumerate(names,1):
            readings=[int(x[index]) for x in events]
            need(all(0<=v<=5_000_000 for v in readings),"STAGE_OUTLIER_OR_NEGATIVE_"+name)
            raw[name]=readings
            ordered=sorted(readings)
            values[name]={
               "median_us":round(statistics.median(readings),2),
               "p95_us":ordered[int((frames-1)*.95)],
               "p99_us":ordered[int((frames-1)*.99)],
               "max_us":max(readings),
               "total_ms":round(sum(readings)/1000,3)}
    if frames==1200:
        engine=(root/"engine-ledger/engine.stderr").read_text(errors="replace")
        need("CPJA7G_GPU_STREAM_COMPLETE frames=1200 device=1 pipelines=3 buffers=5" in engine,
             "PERSISTENT_GPU_ENGINE_NOT_COMPLETE")
    return {"schema":"gnu6.qchain.cpja7h_host_timing.v1",
            "run":root.name,"frames":frames,
            "stage_series":len(raw),"counts_per_series":frames,
            "measurements":values,
            "contains_gpu_shader_timestamp":False,
            "readback_separated_from_compute":False,
            "measures_photons":False,
            "summation_as_end_to_end_latency_valid":False}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run",required=True,type=Path)
    p.add_argument("--frames",default=1200,type=int)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    need(not a.out.exists(),"REFUSE_OVERWRITE_ORACLE")
    data=analyze(a.run,a.frames)
    a.out.write_text(json.dumps(data,indent=2)+"\n")
    print("CPJA7H_TIMING_QUALIFIED",a.run.name,"compute_readback_p99_us",
          data["measurements"]["compute_readback_host_us"]["p99_us"],
          "texture_upload_api_p99_us",
          data["measurements"]["texture_upload_api_us"]["p99_us"],flush=True)
if __name__=="__main__":main()
