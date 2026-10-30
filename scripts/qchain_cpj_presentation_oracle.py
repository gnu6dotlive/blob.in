#!/usr/bin/env python3
"""Independent CP-J Wayland wp_presentation feedback reconciliation.

Wayland CLOCK_MONOTONIC_RAW (id 4) is directly comparable with Rust
clock_gettime(CLOCK_MONOTONIC_RAW), not with wall-clock log prefixes.
"""
import argparse,bisect,hashlib,json,math,re,statistics
from pathlib import Path
def need(ok,why):
    if not ok:raise ValueError(why)
def sha(b):return hashlib.sha256(b).hexdigest()
def pct(a,p):
    v=sorted(a);return v[max(0,min(len(v)-1,math.ceil(len(v)*p)-1))]
def verify(run):
    app=(run/"viewer.stdout").read_text()
    wire=(run/"viewer.stderr").read_text()
    weston=(run/"weston-timeline-proto.log").read_text()
    source=json.loads((run/"engine-ledger/timeline.json").read_text())
    prior=json.loads((run/"run-verdict.json").read_text())
    need(source["engine_exit"]==0 and len(source["frames"])==120,"GPU_SOURCE_INCOMPLETE")
    need(prior["viewer_exit"]==prior["source_exit"]==0,"PROCESSES_FAILED")
    need(len(prior["samples"])==8 and all(x["pixel_differences"]==0 for x in prior["samples"]),
         "COMPOSITOR_CAPTURES_INEXACT")
    need("presentation clock: CLOCK_MONOTONIC_RAW, id 4" in (run/"weston.log").read_text(),
         "WESTON_CLOCK_NOT_MONOTONIC_RAW")
    need(re.search(r"wp_presentation#\d+\.clock_id\(4\)",wire) is not None,
         "CLIENT_PRESENTATION_CLOCK_MISMATCH")

    a=re.findall(r"CPJ_RAW_PRESENT seq=(\d+) monotonic_raw_ns=(\d+)",app)
    need(len(a)==120 and [int(x[0]) for x in a]==list(range(120)),"RAW_APP_CLOCK_INCOMPLETE")
    submits=[int(x[1]) for x in a]
    need(all(x<y for x,y in zip(submits,submits[1:])),"APP_RAW_CLOCK_NONMONOTONIC")
    phased=re.findall(r"CPJ_WGPU_PHASES seq=(\d+) acquire_us=(\d+) queue_us=(\d+) present_call_us=(\d+) draw_total_us=(\d+)",app)
    need(len(phased)==120 and [int(x[0]) for x in phased]==list(range(120)),
         "WGPU_TIMING_PHASES_MISSING")
    callback_requests=re.findall(r" -> wl_surface#\d+\.frame\(new id wl_callback#\d+\)",wire)
    feedback_requests=re.findall(r" -> wp_presentation#\d+\.feedback\(wl_surface#\d+, new id wp_presentation_feedback#\d+\)",wire)
    raw_presented=re.findall(r"wp_presentation_feedback#\d+\.presented\((\d+), (\d+), (\d+), (\d+), (\d+), (\d+), (\d+)\)",wire)
    discarded=re.findall(r"wp_presentation_feedback#\d+\.discarded\(\)",wire)
    need(len(callback_requests)==120 and len(feedback_requests)==120,
         "PROTOCOL_FEEDBACK_REQUEST_COUNT")
    need(len(discarded)==0,"COMPOSITOR_DISCARDED_FRAME")
    need(len(raw_presented)>=1 and len(raw_presented)<=120,"PROTOCOL_PRESENTATION_COUNT")
    from_server=re.findall(r"ev wp_presentation_feedback@\d+\.presented\((\d+), (\d+), (\d+), (\d+), (\d+), (\d+), (\d+)\)",weston)
    need(len(from_server)==120 and raw_presented==from_server[:len(raw_presented)],
         "COMPOSITOR_SOURCE_LOG_DISAGREEMENT")
    confirmations=[]
    for hi,lo,nsec,refresh,seq_hi,seq_lo,flags in from_server:
        ns=((int(hi)<<32)+int(lo))*1_000_000_000+int(nsec)
        need(int(nsec)<1_000_000_000 and int(refresh)>0,"INVALID_PRESENTATION_TIMESTAMP")
        index=bisect.bisect_right(submits,ns)-1
        need(index>=0 and index<120,"PRESENTATION_CLOCK_CANNOT_BE_ATTRIBUTED")
        latency=ns-submits[index]
        need(0<=latency<=200_000_000,"PRESENTATION_LATENCY_OUT_OF_SCOPE")
        confirmations.append({"seq":index,"gpu_to_feedback_clock_ns":latency,
          "feedback_clock_ns":ns,"refresh_ns":int(refresh),"flags":int(flags)})

    found=[x["seq"] for x in confirmations]
    need(len(found)==len(set(found)) and all(a<b for a,b in zip(found,found[1:])),
         "DUPLICATE_OR_REORDERED_PRESENTATION")
    callback_done=re.findall(r"wl_callback#\d+\.done\((\d+)\)",wire)
    frame_done=[int(x) for x in callback_done if int(x)>1000]
    need(len(frame_done)==120,"CLIENT_FRAME_CALLBACK_COUNT_DIFFERENT")
    intervals=[(y["feedback_clock_ns"]-x["feedback_clock_ns"])/1e6
       for x,y in zip(confirmations,confirmations[1:])]
    delay=[x["gpu_to_feedback_clock_ns"]/1e6 for x in confirmations]
    phase_acquire=[int(x[1])/1000 for x in phased]
    phase_submit=[int(x[2])/1000 for x in phased]
    phase_present=[int(x[3])/1000 for x in phased]
    missing=sorted(set(range(120))-set(found))
    client_confirmed=list(range(len(raw_presented)))
    need(len(raw_presented)==119 and client_confirmed==list(range(119))
         and missing==[],"FINAL_CLIENT_DRAIN_PATTERN_CHANGED")
    return {"schema":"gnu6.qchain.cpj_presentation_oracle.v1",
        "verdict":"QCHAIN_CPJ_WESTON_SERVER_120_PRESENTED_CLIENT_119_DRAIN_HOLD",
        "source":"Wayland client protocol log confirmed by isolated Weston proto log",
        "clock_id":4,"clock":"CLOCK_MONOTONIC_RAW",
        "app_gpu_frames":120,"wp_feedback_requests":120,
        "wp_feedback_presented_by_compositor":len(confirmations),
        "wp_feedback_received_by_viewer":len(raw_presented),"wp_feedback_discarded":0,
        "frame_callbacks_done":len(frame_done),
        "server_confirmed_seq":found,"server_unconfirmed_seq":missing,
        "client_confirmed_seq":client_confirmed,"client_unconfirmed_seq":[119],
        "feedback_latency_ms":{"median":statistics.median(delay),
            "p95":pct(delay,.95),"p99":pct(delay,.99),"max":max(delay)},
        "presented_intervals_ms":{"median":statistics.median(intervals),
            "p95":pct(intervals,.95),"p99":pct(intervals,.99),"max":max(intervals)},
        "presented_feedback_rate_hz":(len(intervals)*1000/sum(intervals)),
        "wgpu_acquire_ms":{"median":statistics.median(phase_acquire),"p95":pct(phase_acquire,.95)},
        "wgpu_queue_ms":{"median":statistics.median(phase_submit),"p95":pct(phase_submit,.95)},
        "wgpu_present_call_ms":{"median":statistics.median(phase_present),"p95":pct(phase_present,.95)},
        "sampling_captures":8,"samples_pixel_exact":True,
        "refresh_period_ns_declared":16666666,
        "presentation_flags":[x["flags"] for x in confirmations],
        "actual_physical_display":"NONE_HEADLESS",
        "all_120_presented_on_server":True,
        "all_120_received_by_client":False,"cp03_hybrid60":"OPEN",
        "wall_log_sha256":sha(wire.encode()),"compositor_proto_sha256":sha(weston.encode())}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--run",type=Path,required=True)
    a.add_argument("--out",type=Path,required=True)
    args=a.parse_args()
    need(not args.out.exists(),"REFUSE_OVERWRITE")
    r=verify(args.run)
    args.out.write_text(json.dumps(r,indent=2)+"\n")
    print(r["verdict"],r["wp_feedback_presented_by_compositor"],"of",r["wp_feedback_requests"],
       "median_feedback_latency_ms",r["feedback_latency_ms"]["median"])
if __name__=="__main__":main()
