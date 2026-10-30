#!/usr/bin/env python3
"""CP-JA7D: exact two-in-flight Vulkan present IDs, typed retire/drain, loss fence."""
import json
from collections import Counter
import re
import time

def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)

def parse(root):
    client=(root/"viewer.stderr").read_text(errors="replace")
    app=(root/"viewer.stdout").read_text()
    server=(root/"weston-timeline-proto.log").read_text(errors="replace")
    issue=[tuple(map(int,x)) for x in re.findall(
        r"CPJA7D_INFLIGHT_ISSUED generation=(\d+) present_id=(\d+) pending=(\d+) cap=2",client)]
    retire=[tuple(map(int,x)) for x in re.findall(
        r"CPJA7D_TYPED_RETIRE generation=(\d+) present_id=(\d+) pending=(\d+)",client)]
    drain=[tuple(map(int,x)) for x in re.findall(
        r"CPJA7D_DRAIN_TYPED_ACK generation=(\d+) present_id=(\d+) pending=(\d+)",client)]
    return client,app,server,issue,retire,drain

def qualify(root,samples,started,mode):
    client,app,server,issue,retire,drain=parse(root)
    require(len(samples)==8 and all(
        s["primary"]["pixels_over_rgb3"]==s["secondary"]["pixels_over_rgb3"]==0
        and s["primary"]["pixels_alpha_mismatch"]==0
        and s["secondary"]["pixels_alpha_mismatch"]==0 for s in samples),
        "COMPOSITOR_PIXEL_OR_ALPHA_DIFFERENCE")
    require(all(1<=pending<=2 for _,_,pending in issue)
            and any(p==2 for _,_,p in issue), "MULTI_INFLIGHT_DEPTH_NOT_OBSERVED")
    expected={1:120,2:120} if mode=="normal" else {1:40,2:40,3:80,4:80}
    for g,n in expected.items():
        require([i for gen,i,_ in issue if gen==g]==list(range(1,n+1)),
                f"ISSUED_ID_GAP_GENERATION_{g}")
    require(len(issue)==240,"ISSUED_FRAME_COUNT_NOT_240")
    require(all(p==1 for _,_,p in retire),"RETIRE_WINDOW_NOT_SHRINKING")
    require(all(p in (0,1) for _,_,p in drain),"DRAIN_WINDOW_INVALID")
    acknowledged={(g,i) for g,i,_ in retire+drain}
    require(len(acknowledged)==len(retire)+len(drain),
            "DUPLICATE_TYPED_ACKNOWLEDGEMENT")
    require(all((g,i) in {(h,j) for h,j,_ in issue} for g,i in acknowledged),
            "ACK_FOR_UNISSUED_ID")
    primary_fault="CPJA7D_LOSS_INVALIDATES_UNACKED generation=1 pending=2 failed_present=41"
    if mode=="normal":
        require(len(retire)==236 and len(drain)==4,"NORMAL_RETIRE_DRAIN_COUNT")
        require(all((g,i) in acknowledged for g,i,_ in issue),
                "UNRESOLVED_PRESENTATION_IN_NORMAL_MODE")
        require(primary_fault not in client and "CPJA7CB_LOADER_INJECTED" not in client,
                "NO_FAULT_MODE_CONTAMINATED")
        require("CPJA7C_RECOVERY_BEGIN" not in app,"SPURIOUS_RECOVERY")
    else:
        require(client.count(primary_fault)==1 and
                client.count("CPJA7CB_LOADER_INJECTED_VK_ERROR_DEVICE_LOST")==1 and
                client.count("CPJA7C_WGPU_DEVICE_LOST_CALLBACK reason=Unknown")==1,
                "LOADER_FAULT_OR_WGPU_CALLBACK_MISSING")
        require("CPJA7C_RECOVERY_COMPLETE epochs=1 submitted=120" in app and
                "CPJA7C_RECOVERY_BEGIN old_epoch=0 completed=40" in app,
                "IN_PROCESS_RECOVERY_NOT_COMPLETE")
        require(client.count("CPJA7D_DEVICE_WIDE_DRAIN_DENIED")==2,
                "DEVICE_WIDE_OLD_SWAPCHAIN_DRAIN_NOT_DENIED")
        require([i for g,i,_ in retire if g==1]==list(range(1,40)) and
                [i for g,i,_ in retire if g==2]==list(range(1,39)),
                "PRELOSS_ACK_BOUNDARY_INVALID")
        require([i for g,i,_ in drain if g in (1,2)]==[],
                "FORGED_OLD_DEVICE_DRAIN_ACK")
        require([i for g,i,_ in retire if g==3]==list(range(1,79)) and
                [i for g,i,_ in retire if g==4]==list(range(1,79)),
                "RECOVERED_DEVICE_RETIRE_DRIFT")
        require([i for g,i,_ in drain if g==3]==[79,80] and
                [i for g,i,_ in drain if g==4]==[79,80],
                "RECOVERED_DEVICE_DRAIN_DRIFT")
        require((1,40) not in acknowledged and
                (2,39) not in acknowledged and
                (2,40) not in acknowledged and
                (1,41) not in acknowledged,
                "UNSAFE_ACK_OF_LOST_DEVICE_PRESENT")
    c_presented=re.findall(r"wp_presentation_feedback#\d+\.presented\(([^)]*)\)",client)
    s_presented=re.findall(r"ev wp_presentation_feedback@\d+\.presented\(([^)]*)\)",server)
    c_discarded=re.findall(r"wp_presentation_feedback#\d+\.discarded\(",client)
    s_discarded=re.findall(r"ev wp_presentation_feedback@\d+\.discarded\(",server)
    require(not c_discarded and not s_discarded,
            "WAYLAND_DISCARDED_NOT_ALLOWED")
    # A released old wl_surface may have server-confirmed feedback that its
    # client never reads. No server event may be forged by the client.
    require(not (Counter(c_presented)-Counter(s_presented)),
            "CLIENT_FEEDBACK_NOT_PRESENT_IN_SERVER")
    require(len(s_presented)==240,"WAYLAND_SERVER_PRESENTATION_COUNT_INVALID")
    missing=len(s_presented)-len(c_presented)
    require(missing==0 if mode=="normal" else 0<=missing<=2,
            "UNDELIVERED_CLIENT_FEEDBACK_BOUNDARY_INVALID")
    report={
        "schema":"gnu6.qchain.cpja7d_two_in_flight.v1",
        "verdict":"CPJA7D_NORMAL_TWO_IN_FLIGHT_VISIBLE_PASS" if mode=="normal"
                  else "CPJA7D_LOADER_LOSS_WITH_PENDING_IDS_VISIBLE_RECOVERY_PASS",
        "mode":mode,"frames":120,"inflight_cap":2,
        "generations":expected,"issued":len(issue),
        "retired":len(retire),"drained":len(drain),
        "typed_ack":len(acknowledged),
        "not_acknowledged":[[g,i] for g,i,_ in issue if (g,i) not in acknowledged],
        "max_outstanding":max(p for _,_,p in issue),
        "wayland_presented":len(s_presented),
        "wayland_client_received":len(c_presented),
        "wayland_server_not_received_by_client":missing,
        "wayland_discarded":0,
        "compositor_samples":len(samples),"physical_device_lost":False,
        "layer_synthetic_fault":mode=="loader-recovery",
        "source_is_canonical":True,"no_false_ack":True,
        "cp03_hybrid60":False,"zero_copy":False,
        "wall_seconds":round(time.monotonic()-started,3),
        "samples":samples
    }
    dest=root/"run-verdict.json"
    require(not dest.exists(),"REFUSE_OVERWRITE")
    dest.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"typed_ack",report["typed_ack"],
          "pending_not_acknowledged",report["not_acknowledged"],flush=True)
