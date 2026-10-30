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
def qualify(root,samples,started,mode,profile):
    need(mode=="normal","300_FRAME_RUN_MUST_HAVE_NO_FAULT")
    stderr=(root/"viewer.stderr").read_text(errors="replace")
    stdout=(root/"viewer.stdout").read_text(errors="replace")
    server=(root/"weston-timeline-proto.log").read_text(errors="replace")
    issued=items(stderr,r"CPJA7DB_ASYNC_ISSUED generation=(\d+) present_id=(\d+) pending=(\d+) cap=2")
    waits=items(stderr,r"CPJA7DB_WORKER_WAIT_SUCCESS generation=(\d+) present_id=(\d+) observation=(\d+)")
    deliveries=items(stderr,r"CPJA7DB_WORKER_DELIVER generation=(\d+) present_id=(\d+) arrival=(\d+)")
    ack=items(stderr,r"CPJA7DB_ASYNC_TYPED_ACK generation=(\d+) present_id=(\d+) pending=(\d+)")
    unordered=items(stderr,r"CPJA7DB_OUT_OF_ORDER_TYPED_ACK generation=(\d+) present_id=(\d+) previous_oldest=Some\((\d+)\)")
    need(len(issued)==len(waits)==len(deliveries)==len(ack)==600,
         "VULKAN_ISSUE_WAIT_DELIVERY_ACK_NOT_600")
    expected={(g,i) for g in (1,2) for i in range(1,301)}
    for name,values in (("issued",issued),("waits",waits),
                        ("delivered",deliveries),("ack",ack)):
        ids={(g,i) for g,i,_ in values}
        need(ids==expected and len(values)==len(ids),
             "MISSING_DUPLICATE_OR_EXTRA_"+name)
    need(all(p in (1,2) for _,_,p in issued),"DEPTH_EXCEEDED")
    need(len(unordered)==300 and all(i>prior for _,i,prior in unordered),
         "OUT_OF_ORDER_ACKS_NOT_300")
    for g in (1,2):
        need([i for gen,i,_ in issued if gen==g]==list(range(1,301)),
             "PRESENT_IDS_NOT_MONOTONIC")
        need([i for gen,i,_ in deliveries if gen==g]==
             [v for odd in range(1,301,2) for v in (odd+1,odd)],
             "EXPECTED_OUT_OF_ORDER_DELIVERY_NOT_OBSERVED")
    need("CPI02_WGPU_STREAM_COMPLETE submitted=300" in stdout,
         "RENDER_NOT_300_FRAMES")
    need("CPJA7C_RECOVERY_BEGIN" not in stdout and
         "CPJA7CB_LOADER_INJECTED" not in stderr,
         "UNEXPECTED_DEVICE_LOSS")
    client=re.findall(r"wp_presentation_feedback#\d+\.presented\(([^)]*)\)",stderr)
    serverp=re.findall(r"ev wp_presentation_feedback@\d+\.presented\(([^)]*)\)",server)
    need(len(client)==len(serverp)==600 and
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
    need(len(records)==300 and [x[0] for x in records]==list(range(300)),
         "SOURCE_STREAM_SEQUENCE_INVALID")
    warm=sorted(x[3] for x in records if x[0]>=5)
    def percentile(q):
        pos=(len(warm)-1)*q
        i=int(pos)
        return round(warm[i]*(1-pos+i)+warm[min(i+1,len(warm)-1)]*(pos-i),2)
    p95,p99=percentile(.95),percentile(.99)
    metrics=re.findall(r"CPJA7E_WORKER_METRICS ([^\n]+)",stderr)
    need(len(metrics)==2 and
         all("profile="+profile+" " in x for x in metrics),
         "WORKER_METRICS_NOT_TWO_PROFILE")
    need(stderr.count("CPJA7DB_WORKER_STOP generation=")==2,
         "WORKER_THREADS_NOT_STOPPED")
    result={
        "schema":"gnu6.qchain.cpja7ec_300_frame.v1",
        "verdict":"CPJA7EC_NATIVE_300FRAME_DUAL_WSI_PASS",
        "profile":profile,"mode":mode,
        "frames":300,"issued":600,"typed_wait_success":600,
        "typed_ack":600,"out_of_order_ack":300,
        "wayland_server_presented":600,
        "wayland_client_received":len(client),"max_inflight":2,
        "captures":8,"received_to_submit_p95_us":p95,
        "received_to_submit_p99_us":p99,
        "latency_gate_pass":p95<=100000 and p99<=200000,
        "wall_seconds":round(time.monotonic()-started,3),
        "samples":samples,
    }
    need(result["latency_gate_pass"],"SUSTAINED_LATENCY_GATE_EXCEEDED")
    path=root/"run-verdict.json"
    need(not path.exists(),"REFUSE_OVERWRITE_E2E")
    path.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],"profile",profile,"p95",p95,"p99",p99,flush=True)
