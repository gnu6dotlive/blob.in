"""Independent low-level Vulkan/Wayland ledger audit; never imports production gates."""
from collections import Counter
import re

def require(ok,code):
    if not ok:
        raise AssertionError(code)

def events(client,label):
    pat={
      "issue":r"CPJA7D_INFLIGHT_ISSUED generation=(\d+) present_id=(\d+) pending=(\d+) cap=2",
      "retire":r"CPJA7D_TYPED_RETIRE generation=(\d+) present_id=(\d+) pending=(\d+)",
      "drain":r"CPJA7D_DRAIN_TYPED_ACK generation=(\d+) present_id=(\d+) pending=(\d+)"
    }[label]
    return [tuple(int(z) for z in rec) for rec in re.findall(pat,client)]

def verify_native(root,client,app,server,compositor,samples):
    fault="CPJA7CB_LOADER_INJECTED_VK_ERROR_DEVICE_LOST primary=1 present_id=41"
    mode="loader-recovery" if fault in client else "normal"
    issued=events(client,"issue")
    retired=events(client,"retire")
    drained=events(client,"drain")
    acknowledgements=[(g,i) for g,i,_ in retired+drained]
    issued_set={(g,i) for g,i,_ in issued}
    require(len(issued)==240 and max(p for _,_,p in issued)==2,
            "NOT_240_WSI_SUBMISSIONS_WITH_TWO_OUTSTANDING")
    require(all(1<=p<=2 for _,_,p in issued), "INVALID_INFLIGHT_DEPTH")
    require(len(acknowledgements)==len(set(acknowledgements)),
            "DUPLICATE_VULKAN_ACK")
    require(set(acknowledgements).issubset(issued_set),"ACK_WITHOUT_ISSUE")
    require(all(p==1 for _,_,p in retired),"RETIRE_NOT_BOUNDED")
    require(all(p in (0,1) for _,_,p in drained),"DRAIN_UNSAFE_DEPTH")
    require("CPI02_WGPU_STREAM_COMPLETE submitted=120" in app,
            "STREAM_COMPLETE_NOT_OBSERVED")
    generations={1:120,2:120} if mode=="normal" else {1:40,2:40,3:80,4:80}
    for g,n in generations.items():
        require([i for gen,i,_ in issued if gen==g]==list(range(1,n+1)),
                f"ISSUED_SEQ_INVALID_GEN_{g}")
    if mode=="normal":
        require(len(retired)==236 and len(drained)==4,
                "NORMAL_RETIRE_DRAIN_SPLIT_INVALID")
        require(set(acknowledgements)==issued_set,"NORMAL_UNACKED_PRESENT")
        require(len(re.findall(r"CPJA7D_DEVICE_WIDE_DRAIN_DENIED",client))==0,
                "SPURIOUS_DEVICE_LOSS")
        require("CPJA7C_RECOVERY_BEGIN" not in app,"SPURIOUS_DEVICE_REBUILD")
    else:
        require(client.count(fault)==1 and
                client.count("CPJA7C_WGPU_DEVICE_LOST_CALLBACK reason=Unknown")==1 and
                client.count("CPJA7D_LOSS_INVALIDATES_UNACKED generation=1 pending=2 failed_present=41")==1,
                "INJECTED_VULKAN_FAULT_CHAIN_INVALID")
        require(client.count("CPJA7D_DEVICE_WIDE_DRAIN_DENIED")==2 and
                "CPJA7D_DEVICE_WIDE_DRAIN_DENIED generation=2 pending=2" in client,
                "SECONDARY_UNACKED_IDS_NOT_POISONED")
        require(len(retired)==233 and len(drained)==4,
                "RECOVERY_RETIRE_DRAIN_SPLIT_INVALID")
        unconfirmed=issued_set-set(acknowledgements)
        require(unconfirmed=={(1,40),(2,39),(2,40)},
                "LOST_DEVICE_UNACKED_IDS_MISATTRIBUTED")
        require("CPJA7C_RECOVERY_BEGIN old_epoch=0 completed=40 pending_seq=Some(40)" in app and
                "CPJA7C_RECOVERY_READY new_epoch=1 completed=40 pending_seq=Some(40)" in app and
                "CPJA7C_RECOVERY_COMPLETE epochs=1 submitted=120" in app,
                "RECOVERY_HANDOFF_NOT_SEALED")
        require(client.count("CPJA7CB_LOADER_NEGOTIATED interface=2")==2 and
                client.count("CPJA7CB_DEVICE_CREATED dispatch=1")==2 and
                client.count("CPJA7CB_LOADER_FIRST_FORWARD success_path=1")==2,
                "RECOVERED_VULKAN_LOADER_DISPATCH_MISSING")
        require("CPJA7C_INJECTED_VK_ERROR_DEVICE_LOST" not in client,
                "PREVIOUS_HAL_FAULT_HOOK_NOT_ALLOWED")
    for g in generations:
        ids=[i for gen,i in acknowledgements if gen==g]
        require(ids==sorted(ids) and len(ids)==len(set(ids)),
                f"NONMONOTONIC_OR_DUPLICATE_ACK_GEN_{g}")
    requests=re.findall(
        r"wp_presentation#\d+\.feedback\(wl_surface#(\d+), new id wp_presentation_feedback#\d+\)",client)
    resources=list(dict.fromkeys(requests))
    expected_counts=[120,120] if mode=="normal" else [40,40,80,80]
    require(len(resources)==len(expected_counts) and
            [requests.count(k) for k in resources]==expected_counts,
            "WAYLAND_SURFACE_IDS_OR_FEEDBACK_REQUESTS_INVALID")
    if mode=="loader-recovery":
        require(all(r in resources[:2] for r in requests[:80]) and
                all(r in resources[2:] for r in requests[80:]),
                "OLD_WAYLAND_SURFACE_USED_AFTER_LOSS")
    cp=re.findall(r"wp_presentation_feedback#\d+\.presented\(([^)]*)\)",client)
    sp=re.findall(r"ev wp_presentation_feedback@\d+\.presented\(([^)]*)\)",server)
    cd=re.findall(r"wp_presentation_feedback#\d+\.discarded\(",client)
    sd=re.findall(r"ev wp_presentation_feedback@\d+\.discarded\(",server)
    require(not cd and not sd and not (Counter(cp)-Counter(sp)),
            "UNTRUSTWORTHY_COMPOSITOR_FEEDBACK")
    deficit=len(sp)-len(cp)
    require(len(sp)==240 and (deficit==0 if mode=="normal" else 0<=deficit<=2),
            "WAYLAND_FEEDBACK_UNDELIVERED_BOUND_EXCEEDED")
    require("CPJA7B_TILE_PLUGIN_ACTIVE" in compositor and
            "CPJA7B_TILE_VIEWS count=2" in compositor,
            "PRIVATE_WESTON_WITNESS_ABSENT")
    require(len(samples)==8 and
            all(max(s["primary_max_rgba_delta"][:3])<=3 and
                max(s["secondary_max_rgba_delta"][:3])<=3 and
                s["primary_max_rgba_delta"][3]==0 and
                s["secondary_max_rgba_delta"][3]==0
                for s in samples),"POSTED_PIXELS_NOT_BOUNDED")
    return {
      "schema":"gnu6.qchain.cpja7d_independent_oracle.v1",
      "verdict":"CPJA7D_INDEPENDENT_TWO_INFLIGHT_WITH_RECOVERY_PASS",
      "mode":mode,
      "source_frames":120,
      "issued":len(issued),
      "typed_acks":len(acknowledgements),
      "retired":len(retired),"drained":len(drained),
      "unacknowledged":sorted([list(z) for z in issued_set-set(acknowledgements)]),
      "depth_per_surface":2,"generations":generations,
      "client_received_wayland_feedback":len(cp),
      "server_wayland_presented":len(sp),
      "server_wayland_discarded":len(sd),
      "server_delivered_but_not_client_observed":deficit,
      "screenshots":samples,
      "actual_vendor_device_lost":False,
      "physical_display_qualified":False,
      "cp03_hybrid60":False,
      "multiple_acks_out_of_order_qualified":False
    }
