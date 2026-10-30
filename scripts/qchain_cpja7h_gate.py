#!/usr/bin/env python3
"""CP-JA7E-C: test-run admission for 300 continuous canonical frames."""
import json
import re
import time
from collections import Counter

def need(ok,why):
    if not ok: raise RuntimeError(why)
def items(text,pattern):
    return [tuple(map(int,x)) for x in re.findall(pattern,text)]
def qualify(root,samples,started,mode,profile,interval_ms,frames):
    need(mode=="normal","300_FRAME_RUN_MUST_HAVE_NO_FAULT")
    stderr=(root/"viewer.stderr").read_text(errors="replace")
    stdout=(root/"viewer.stdout").read_text(errors="replace")
    server=(root/"weston-timeline-proto.log").read_text(errors="replace")
    issued=items(stderr,r"CPJA7DB_ASYNC_ISSUED generation=(\d+) present_id=(\d+) pending=(\d+) cap=2")
    waits=items(stderr,r"CPJA7DB_WORKER_WAIT_SUCCESS generation=(\d+) present_id=(\d+) observation=(\d+)")
    deliveries=items(stderr,r"CPJA7DB_WORKER_DELIVER generation=(\d+) present_id=(\d+) arrival=(\d+)")
    ack=items(stderr,r"CPJA7DB_ASYNC_TYPED_ACK generation=(\d+) present_id=(\d+) pending=(\d+)")
    unordered=items(stderr,r"CPJA7DB_OUT_OF_ORDER_TYPED_ACK generation=(\d+) present_id=(\d+) previous_oldest=Some\((\d+)\)")
    need(len(issued)==len(waits)==len(deliveries)==len(ack)==2*frames,
         "VULKAN_ISSUE_WAIT_DELIVERY_ACK_NOT_600")
    expected={(g,i) for g in (1,2) for i in range(1,frames+1)}
    for name,values in (("issued",issued),("waits",waits),
                        ("delivered",deliveries),("ack",ack)):
        ids={(g,i) for g,i,_ in values}
        need(ids==expected and len(values)==len(ids),
             "MISSING_DUPLICATE_OR_EXTRA_"+name)
    need(all(p in (1,2) for _,_,p in issued),"DEPTH_EXCEEDED")
    need(len(unordered)==frames and all(i>prior for _,i,prior in unordered),
         "OUT_OF_ORDER_ACKS_NOT_300")
    for g in (1,2):
        need([i for gen,i,_ in issued if gen==g]==list(range(1,frames+1)),
             "PRESENT_IDS_NOT_MONOTONIC")
        need([i for gen,i,_ in deliveries if gen==g]==
             [v for odd in range(1,frames+1,2) for v in (odd+1,odd)],
             "EXPECTED_OUT_OF_ORDER_DELIVERY_NOT_OBSERVED")
    need(f"CPI02_WGPU_STREAM_COMPLETE submitted={frames}" in stdout,
         "RENDER_NOT_300_FRAMES")
    need("CPJA7C_RECOVERY_BEGIN" not in stdout and
         "CPJA7CB_LOADER_INJECTED" not in stderr,
         "UNEXPECTED_DEVICE_LOSS")
    client=re.findall(r"wp_presentation_feedback#\d+\.presented\(([^)]*)\)",stderr)
    serverp=re.findall(r"ev wp_presentation_feedback@\d+\.presented\(([^)]*)\)",server)
    need(len(client)==len(serverp)==2*frames and
         Counter(client)==Counter(serverp) and
         ".discarded(" not in stderr and
         "ev wp_presentation_feedback@" in server,
         "WAYLAND_FEEDBACK_RECONCILIATION")
    need(len(samples)==8 and all(x["primary"]["pixels_over_rgb3"]==0
        and x["secondary"]["pixels_over_rgb3"]==0
        and x["primary"]["pixels_alpha_mismatch"]==0
        and x["secondary"]["pixels_alpha_mismatch"]==0 for x in samples),
         "COMPOSITOR_VISUAL_NOT_VERIFIED")
    records=items(stdout,r"CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+) stage=(\d+) elapsed_us=(\d+) received_to_submit_us=(\d+) epoch=(\d+)")
    need(len(records)==frames and [x[0] for x in records]==list(range(frames)),
         "SOURCE_STREAM_SEQUENCE_INVALID")
    warm=sorted(x[3] for x in records if x[0]>=5)
    def percentile(q):
        pos=(len(warm)-1)*q
        i=int(pos)
        return round(warm[i]*(1-pos+i)+warm[min(i+1,len(warm)-1)]*(pos-i),2)
    p95,p99=percentile(.95),percentile(.99)
    elapsed=[x[2] for x in records]
    gaps=[v-u for u,v in zip(elapsed,elapsed[1:])]
    need(len(gaps)==frames-1 and all(g>0 for g in gaps),
         "RESIDENT_SUBMISSIONS_NONMONOTONIC")
    longest=0
    streak=0
    for gap in gaps:
        streak=streak+1 if 3_000_000<=gap<=6_000_000 else 0
        longest=max(longest,streak)
    elapsed_sec=(elapsed[-1]-elapsed[0])/1e6
    intervals_20_100=sum(20_000<=gap<=100_000 for gap in gaps)
    intervals_20_100_fraction=intervals_20_100/len(gaps)
    intervals_sorted=sorted(gaps)
    p99_interval=intervals_sorted[min(len(gaps)-1,int(len(gaps)*.99))]
    if frames==1200:
        need(elapsed_sec >= (17 if interval_ms<=16 else 35)
             and elapsed_sec <= 100,
             "HYBRID_PREQUALIFIED_FRAME_SPAN_OUT_OF_BOUNDS")
        need(intervals_20_100_fraction>=.90 and p99_interval<=250_000,
             "ACTIVE_PACING_NOT_QUALIFIED")
    need(stdout.count("CPJA7F_RESIDENT_DEVICE_CREATED epoch=0") == 0
         and "CPJA7C_RECOVERY_BEGIN" not in stdout,
         "ACTIVE_UNEXPECTED_DEVICE_REBUILD")
    need(f"CPJA7F_RESIDENCY_COMPLETE frames={frames} interval_ms={interval_ms}" in stdout,
         "RESIDENT_END_MARKER_MISSING")
    metrics=re.findall(r"CPJA7E_WORKER_METRICS ([^\n]+)",stderr)
    need(len(metrics)==2 and
         all("profile="+profile+" " in x for x in metrics),
         "WORKER_METRICS_NOT_TWO_PROFILE")
    need(stderr.count("CPJA7DB_WORKER_STOP generation=")==2,
         "WORKER_THREADS_NOT_STOPPED")
    result={
        "schema":"gnu6.qchain.cpja7h_attribution.v1",
        "verdict":"CPJA7H_NATIVE_TIMING_1200_PASS",
        "profile":profile,"mode":mode,
        "frames":frames,"issued":frames*2,"typed_wait_success":frames*2,
        "typed_ack":frames*2,"out_of_order_ack":frames,
        "wayland_server_presented":frames*2,
        "wayland_client_received":len(client),"max_inflight":2,
        "captures":8,"received_to_submit_p95_us":p95,
        "received_to_submit_p99_us":p99,
        "intentional_preload_wait_not_a_gpu_latency": True,
        "present_interval_ms":interval_ms,
        "elapsed_between_first_last_us":elapsed[-1]-elapsed[0],
        "cadence_gaps_in_3_to_6_seconds":sum(3_000_000<=g<=6_000_000 for g in gaps),
        "longest_consecutive_cadence_streak":longest,
        "active_frame_interval_20_100_fraction":intervals_20_100_fraction,
        "active_frame_interval_p99_us":p99_interval,
        "active_duration_s":elapsed_sec,
        "minimum_20_minute_residency":False,
        "max_interframe_gap_us":max(gaps),
        "wall_seconds":round(time.monotonic()-started,3),
        "samples":samples,
    }
    need(interval_ms in (16,33),"UNSAFE_PACING")
    path=root/"run-verdict.json"
    need(not path.exists(),"REFUSE_OVERWRITE_E2E")
    path.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],"profile",profile,"p95",p95,"p99",p99,flush=True)
