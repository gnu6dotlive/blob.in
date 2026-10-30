"""Independent CP-JA7D-B authority reconstitution: source logs, Vulkan IDs, screenshots."""
from collections import Counter
import re

def require(ok,code):
    if not ok:raise AssertionError(code)

def matches(src,expression):
    return [tuple(map(int,m)) for m in re.findall(expression,src)]

def verify_native(root,client,app,server,compositor,samples):
    issue=matches(client,r"CPJA7DB_ASYNC_ISSUED generation=(\d+) present_id=(\d+) pending=(\d+) cap=2")
    wait=matches(client,r"CPJA7DB_WORKER_WAIT_SUCCESS generation=(\d+) present_id=(\d+) observation=(\d+)")
    delivered=matches(client,r"CPJA7DB_WORKER_DELIVER generation=(\d+) present_id=(\d+) arrival=(\d+)")
    accepted=matches(client,r"CPJA7DB_ASYNC_TYPED_ACK generation=(\d+) present_id=(\d+) pending=(\d+)")
    reorders=matches(client,r"CPJA7DB_OUT_OF_ORDER_TYPED_ACK generation=(\d+) present_id=(\d+) previous_oldest=Some\((\d+)\)")
    batches=matches(client,r"CPJA7DB_DELIVERY_REORDERED generation=(\d+) old=(\d+) new=(\d+) proof=two_real_vk_wait_success")
    fault="CPJA7CB_LOADER_INJECTED_VK_ERROR_DEVICE_LOST primary=1 present_id=41"
    mode="loader-recovery" if fault in client else "normal"
    expected={1:120,2:120} if mode=="normal" else {1:40,2:40,3:80,4:80}
    require(len(issue)==len(wait)==len(delivered)==240,
            "ASYNC_WSI_COUNT_MISMATCH")
    require(len(batches)==120 and max(p for _,_,p in issue)==2,
            "NOT_TWO_IN_FLIGHT_AND_PAIRED")
    require(all(p in (1,2) for _,_,p in issue),"BAD_CAP")
    seen_issues={(g,i) for g,i,p in issue}
    seen_waits={(g,i) for g,i,o in wait}
    seen_deliveries={(g,i) for g,i,o in delivered}
    seen_ack={(g,i) for g,i,p in accepted}
    require(len(seen_issues)==len(seen_waits)==len(seen_deliveries)==240 and
            seen_issues==seen_waits==seen_deliveries,
            "VULKAN_RETURNED_SUCCESS_WITNESS_MISSING")
    require(len(accepted)==len(seen_ack) and seen_ack.issubset(seen_waits),
            "ACK_UNBACKED_BY_ACTUAL_WAIT")
    for g,n in expected.items():
        require([i for gen,i,p in issue if gen==g]==list(range(1,n+1)),
                f"ISSUE_IDS_NOT_CONTINUOUS_GEN_{g}")
        require(sorted(i for gen,i,_ in wait if gen==g)==list(range(1,n+1)),
                f"VK_WAIT_IDS_NOT_CONTINUOUS_GEN_{g}")
        require([i for gen,i,_ in delivered if gen==g]==
                [z for odd in range(1,n+1,2) for z in (odd+1,odd)],
                f"DELIVERY_NOT_REVERSED_GEN_{g}")
        require([(odd,new) for gen,odd,new in batches if gen==g]==
                [(odd,odd+1) for odd in range(1,n+1,2)],
                f"PAIR_REORDER_UNPROVEN_GEN_{g}")
        require([seq for gen,_,seq in delivered if gen==g]==list(range(1,n+1)),
                f"DELIVERY_OBSERVATION_SEQUENCE_INVALID_GEN_{g}")
    require(all(i>prior for g,i,prior in reorders),
            "DECLARED_NONFIFO_ACCEPT_NOT_NONFIFO")
    for g in expected:
        accepted_order=[i for gen,i,_ in accepted if gen==g]
        delivery_ack_order=[i for gen,i,_ in delivered
                            if gen==g and (g,i) in seen_ack]
        require(accepted_order==delivery_ack_order,
                f"ACK_ORDER_NOT_OBSERVED_WORKER_DELIVERY_GEN_{g}")
    expected_reorders={(g,odd+1,odd) for g,n in expected.items()
        for odd in range(1,n+1,2)
        if (g,odd+1) in seen_ack and (g,odd) in seen_ack}
    require(len(reorders)==len(set(reorders)) and
            set(reorders)==expected_reorders and len(reorders)>=100,
            "REORDERED_AUTHORITY_NOT_EXACT")
    missing=seen_issues-seen_ack
    if mode=="normal":
        require(len(accepted)==240 and len(reorders)==120 and not missing,
                "NORMAL_VALIDATED_ACK_INCOMPLETE")
        require(client.count("CPJA7DB_WORKER_STOP")==2 and
                "CPJA7DB_DEVICE_LOST_DRAIN_REVOKED" not in client and
                "CPJA7C_RECOVERY_BEGIN" not in app,
                "SPURIOUS_RECOVERY_OR_WORKER_LEAK")
    else:
        require(client.count(fault)==1 and
                client.count("CPJA7C_WGPU_DEVICE_LOST_CALLBACK reason=Unknown")==1 and
                "CPJA7C_RECOVERY_COMPLETE epochs=1 submitted=120" in app,
                "LOSS_SIGNAL_OR_RECONSTRUCTION_MISSING")
        require(client.count("CPJA7CB_LOADER_NEGOTIATED interface=2")==2 and
                client.count("CPJA7CB_DEVICE_CREATED dispatch=1")==2 and
                client.count("CPJA7CB_LOADER_FIRST_FORWARD success_path=1")==2,
                "LOADER_DISPATCH_NOT_QUALIFIED")
        require("CPJA7C_INJECTED_VK_ERROR_DEVICE_LOST" not in client,
                "OLD_HAL_SIDE_FAULT_NOT_ALLOWED")
        require(client.count("CPJA7D_LOSS_INVALIDATES_UNACKED")==1 and
                client.count("CPJA7D_DEVICE_WIDE_DRAIN_DENIED")==2 and
                client.count("CPJA7DB_DEVICE_LOST_DRAIN_REVOKED")==2 and
                client.count("CPJA7DB_WORKER_STOP")==4,
                "DEVICE_WIDE_WORKER_CANCELLATION_MISSING")
        require(missing and len(missing)<=4 and
                missing.issubset({(1,39),(1,40),(2,39),(2,40)}) and
                {(2,39),(2,40)}.issubset(missing),
                "LOST_SWAPCHAIN_UNACKNOWLEDGED_IDS_WRONG")
        cutoff=client.find("CPJA7D_LOSS_INVALIDATES_UNACKED")
        require(cutoff>0 and not re.search(
            r"CPJA7DB_ASYNC_TYPED_ACK generation=[12] present_id=\d+",
            client[cutoff:]),"LATE_OLD_DEVICE_ACK_AFTER_LOSS")
        require((1,41) not in seen_issues and (1,41) not in seen_ack,
                "FAILED_PRESENT_FABRICATED_SUCCESS")
    require("CPI02_WGPU_STREAM_COMPLETE submitted=120" in app,
            "CANONICAL_SOURCE_DID_NOT_COMPLETE")
    requests=re.findall(
        r"wp_presentation#\d+\.feedback\(wl_surface#(\d+), new id wp_presentation_feedback#\d+\)",client)
    resources=list(dict.fromkeys(requests))
    expected_counts=[120,120] if mode=="normal" else [40,40,80,80]
    require(len(resources)==len(expected_counts) and
            [requests.count(i) for i in resources]==expected_counts,
            "WAYLAND_SURFACE_RESOURCE_OR_REQUEST_MISMATCH")
    observed_client=re.findall(
        r"wp_presentation_feedback#\d+\.presented\(([^)]*)\)",client)
    observed_server=re.findall(
        r"ev wp_presentation_feedback@\d+\.presented\(([^)]*)\)",server)
    require(len(observed_server)==240 and
            not (Counter(observed_client)-Counter(observed_server)) and
            not re.search(r"wp_presentation_feedback#\d+\.discarded\(",client) and
            not re.search(r"ev wp_presentation_feedback@\d+\.discarded\(",server),
            "COMPOSITOR_RECEIPT_DIVERGENCE")
    unmatched=len(observed_server)-len(observed_client)
    require(unmatched==0 if mode=="normal" else 0<=unmatched<=2,
            "COMPOSITOR_CLIENT_LOSS_OVERBOUND")
    require("CPJA7B_TILE_PLUGIN_ACTIVE" in compositor and
            "CPJA7B_TILE_VIEWS count=2" in compositor,
            "PRIVATE_COMPOSITOR_INDEPENDENCE_MISSING")
    require(len(samples)==8 and all(
        max(s["primary_max_rgba_delta"][:3])<=3 and
        max(s["secondary_max_rgba_delta"][:3])<=3 and
        s["primary_max_rgba_delta"][3]==s["secondary_max_rgba_delta"][3]==0
        for s in samples),"VISUAL_RGBA_DRIFT")
    return {
        "schema":"gnu6.qchain.cpja7db_independent_oracle.v1",
        "verdict":"CPJA7DB_INDEPENDENT_ASYNC_OUT_OF_ORDER_AUTHORITY_PASS",
        "mode":mode,"source_frames":120,"issued":len(issue),
        "typed_vk_wait_success":len(wait),"out_of_order_deliveries":len(batches),
        "acknowledged":len(accepted),"out_of_order_acknowledged":len(reorders),
        "unacknowledged":sorted([list(v) for v in missing]),
        "max_outstanding_per_swapchain":2,
        "server_wayland_presented":len(observed_server),
        "client_wayland_presented":len(observed_client),
        "server_unreceived_by_client":unmatched,
        "screenshots":samples,
        "synthetic_loader_fault":mode=="loader-recovery",
        "real_vendor_device_loss":False,
        "actual_present_order_reversed":False,
        "real_vulkan_wait_status_for_each_ack":True,
        "cp03_hybrid60":False
    }
