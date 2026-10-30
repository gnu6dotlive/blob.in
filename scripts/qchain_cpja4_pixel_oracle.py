#!/usr/bin/env python3
"""CP-I02 independent exact evidence validator: 120 live GPU IPC frames, 8 captures.
No Wayland presentation callback feedback or hardware GPU timestamps inferred.
"""
import argparse,hashlib,json,re,statistics,math
from pathlib import Path
from PIL import Image,ImageOps
def need(ok,reason):
    if not ok:raise ValueError(reason)
def sha(b):return hashlib.sha256(b).hexdigest()
def percentile(values,p):
    s=sorted(values);return s[max(0,min(len(s)-1,math.ceil(len(s)*p)-1))]
def verify(root,baseline,receipt):
    recorded=json.loads((root/"run-verdict.json").read_text())
    proof=json.loads(receipt.read_text())
    need(recorded["verdict"]=="QCHAIN_CPJA4_120_GPU_FRAMES_SEALED_IPC_8_EXACT_WESTON_SAMPLES_PASS","RUN_NOT_PASS")
    weston=(root/"weston.log").read_text()
    need("GL renderer: NVIDIA GeForce RTX 3070" in weston,"COMPOSITOR_GPU_NOT_ATTESTED")
    need("screen capture uses y-flip: yes" in weston,"SCREEN_COORDINATES_UNDECLARED")
    engine=(root/"engine-ledger/engine.stderr").read_text()
    need("CPI02_GPU_STREAM_COMPLETE frames=120 device=1 pipelines=3 buffers=5" in engine,"COMPUTE_NOT_COMPLETED")
    viewer=(root/"viewer.stdout").read_text()
    source=(root/"source.stdout").read_text()
    need("CPJA4_VK_STREAM_COMPLETE submitted=120" in viewer and
         "CPI02_SOURCE_COMPLETE frames=120" in source,"STREAM_CLOSED_EARLY")
    rx=json.loads((root/"engine-ledger/timeline.json").read_text())
    need(rx["engine_exit"]==0 and len(rx["frames"])==120,"PRODUCER_FRAME_COUNT")
    pattern=r"CPJA4_VK_PRESENT_SUBMITTED seq=(\d+) stage=(\d+) elapsed_us=(\d+) received_to_submit_us=(\d+) epoch=(\d+) scene_sha256=([0-9a-f]{64}) rgba_sha256=([0-9a-f]{64}) dimensions=(\d+)x(\d+)"
    msgs=re.findall(pattern,viewer)
    need(len(msgs)==120,"VIEWER_SUBMISSION_COUNT")
    elapsed=[];latency=[]

    unique_hashes=set()
    for seq,(entry,log) in enumerate(zip(rx["frames"],msgs)):
        number,stage,elapsed_us,rcv_us,epoch,scene_sha,rgba_sha,width,height=log
        phase=min(seq,4)
        variant=0 if seq<5 else ((seq-5)//12)%8
        material=("ceramic","gel","metal","paper")[variant//2]
        reference=baseline/f"state{phase}-{material}-frame{variant%2}-dpr2.gpu-rgba.bin"
        exact_sha=sha(reference.read_bytes())
        need(int(number)==entry["seq"]==seq and int(stage)==entry["stage"]==phase and
             int(epoch)==phase and entry["variant"]==variant,
             f"SEQUENCE_IDENTITY_MISMATCH_{seq}")
        need(entry["pixel_sha256"]==rgba_sha==exact_sha and
             scene_sha==proof["stages"][phase]["scene_sha256"] and
             width=="512" and height=="384",f"GPU_FRAME_HASH_DRIFT_{seq}")
        elapsed.append(int(elapsed_us))
        latency.append(int(rcv_us))
        unique_hashes.add(rgba_sha)
    need(all(b>a for a,b in zip(elapsed,elapsed[1:])), "NONMONOTONIC_SUBMISSION_CLOCK")
    need(len(unique_hashes)>=4,"NO_MATERIAL_CHANGE")
    intervals=[b-a for a,b in zip(elapsed,elapsed[1:])]
    need(intervals==recorded["submission_intervals_us"],"RUN_TIMING_CLAIM_CHANGED")
    need(recorded["viewer_elapsed_us"]==elapsed[-1],"RUN_CLOCK_DRIFT")

    sample=[]
    for idx,seq in enumerate([9,21,33,45,57,69,81,93]):
        png=root/f"sample-{idx:02}.png"
        need(png.exists(),"CAPTURE_NOT_PRESENT_"+str(idx))
        with Image.open(png) as im:
            need(im.size==(512,384),"CAPTURE_SIZE_DRIFT")
            rgba=ImageOps.flip(im.convert("RGBA")).tobytes()
        variant=idx;mat=("ceramic","gel","metal","paper")[variant//2]
        file=baseline/f"state4-{mat}-frame{variant%2}-dpr2.gpu-rgba.bin"
        expected=file.read_bytes()
        need(rgba==expected,f"COMPOSITOR_PIXEL_MISMATCH_{idx}")
        logged=recorded["samples"][idx]
        need(logged["target_seq"]==seq and logged["variant"]==idx and
             logged["png_sha256"]==sha(png.read_bytes()) and
             logged["expected_sha256"]==sha(expected) and
             logged["normalized_sha256"]==sha(rgba),
             f"CAPTURE_EVIDENCE_TAMPERING_{idx}")
        sample.append({"index":idx,"target_seq":seq,"capture_sha256":sha(png.read_bytes()),
                       "gpu_sha256":sha(expected),"pixel_differences":0})
    return {"schema":"gnu6.qchain.cpi02_independent_oracle.v1",
      "verdict":"QCHAIN_CPJA4_120_GPU_STREAM_8_WESTON_SAMPLE_EXACT_PASS",
      "rendered_frames":120,"sealed_memfd_transport_frames":120,
      "wgpu_present_call_count":120,"exact_compositor_samples":8,
      "pixels_compared":8*512*384,"pixel_differences":0,
      "unique_frame_pixel_sha256":len(unique_hashes),
      "application_submit_interval_us":{"median":statistics.median(intervals),
          "p95":percentile(intervals,.95),"p99":percentile(intervals,.99),
          "maximum":max(intervals)},
      "received_to_submit_us":{"median":statistics.median(latency),
          "p95":percentile(latency,.95)},
      "source_timeline_sha256":sha((root/"engine-ledger/timeline.json").read_bytes()),
      "sampled_captures":sample,
      "wayland_presentation_feedback_per_frame":"NOT_RUN",
      "fps_60":"NOT_QUALIFIED",
      "gpu_zero_copy":False,"photon_capture":"NOT_RUN"}

def main():
    p=argparse.ArgumentParser()
    for f in ("run","baseline","receipt","out"):
        p.add_argument("--"+f,type=Path,required=True)
    a=p.parse_args()
    need(not a.out.exists(),"REFUSE_OVERWRITE")
    report=verify(a.run,a.baseline,a.receipt)
    a.out.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"frames",report["rendered_frames"],
          "samples",report["exact_compositor_samples"],
          "median_submit_ms",report["application_submit_interval_us"]["median"]/1000)
if __name__=="__main__":main()
