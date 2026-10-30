#!/usr/bin/env python3
"""CP-JA7D-B runtime qualification: real Vulkan wait successes, reordered delivery."""
from collections import Counter
import json
import re
import time

def require(ok,reason):
    if not ok:raise RuntimeError(reason)

def records(text,key):
    p={
      "issue":r"CPJA7DB_ASYNC_ISSUED generation=(\d+) present_id=(\d+) pending=(\d+) cap=2",
      "wait":r"CPJA7DB_WORKER_WAIT_SUCCESS generation=(\d+) present_id=(\d+) observation=(\d+)",
      "delivery":r"CPJA7DB_WORKER_DELIVER generation=(\d+) present_id=(\d+) arrival=(\d+)",
      "ack":r"CPJA7DB_ASYNC_TYPED_ACK generation=(\d+) present_id=(\d+) pending=(\d+)",
      "reordered":r"CPJA7DB_OUT_OF_ORDER_TYPED_ACK generation=(\d+) present_id=(\d+) previous_oldest=Some\((\d+)\)",
      "batch":r"CPJA7DB_DELIVERY_REORDERED generation=(\d+) old=(\d+) new=(\d+) proof=two_real_vk_wait_success"
    }[key]
    return [tuple(map(int,x)) for x in re.findall(p,text)]

def assess(root,samples,mode):
    client=(root/"viewer.stderr").read_text(errors="replace")
    app=(root/"viewer.stdout").read_text()
    server=(root/"weston-timeline-proto.log").read_text(errors="replace")
    issued=records(client,"issue")
    waited=records(client,"wait")
    delivered=records(client,"delivery")
    ack=records(client,"ack")
    reordered=records(client,"reordered")
    batches=records(client,"batch")
    generations={1:120,2:120} if mode=="normal" else {1:40,2:40,3:80,4:80}
    require(len(issued)==240 and len(waited)==240 and len(delivered)==240,
            "REAL_ASYNC_WSI_AUTHORITY_COUNTS_INVALID")
    require(all(p in (1,2) for _,_,p in issued)
            and sum(p==2 for _,_,p in issued)==120,
            "TWO_OUTSTANDING_WSI_DEPTH_UNPROVEN")
    for generation,n in generations.items():
        require([i for g,i,_ in issued if g==generation]==list(range(1,n+1)),
                f"ISSUE_SEQUENCE_UNTRUSTWORTHY_{generation}")
        require(sorted(i for g,i,_ in waited if g==generation)==list(range(1,n+1)),
                f"VULKAN_WAIT_SUCCESS_ID_SET_UNEXPECTED_{generation}")
        require([i for g,i,_ in delivered if g==generation]==
                [v for k in range(1,n+1,2) for v in (k+1,k)],
                f"COMPLETION_DELIVERY_NOT_REORDERED_{generation}")
        require([old for g,old,new in batches if g==generation]==
                list(range(1,n+1,2)) and
                [new for g,old,new in batches if g==generation]==
                list(range(2,n+1,2)),
                f"REAL_WAIT_PAIR_PROOF_MISSING_{generation}")
    require(len(batches)==120,"ASYNCHRONOUS_BATCH_COUNT_UNPROVEN")
    sets={
      key:{(g,i) for g,i,_ in records(client,key)}
      for key in ("issue","wait","delivery","ack")
    }
    require(sets["issue"]==sets["wait"]==sets["delivery"] and
            len(sets["issue"])==240,"SOURCE_WSI_WAIT_DELIVERY_IDS_DIVERGE")
    require(len(sets["ack"])==len(ack) and sets["ack"].issubset(sets["wait"]),
            "ACK_MISSING_REAL_VK_WAIT_OR_DUPLICATE")
    require(all(new>old for g,new,old in reordered),
            "REORDERED_ACK_OLDER_THAN_PRIOR_PENDING")
    require(90<=len(reordered)<=120,"ACTUAL_OUT_OF_ORDER_ACCEPTANCE_UNPROVEN")
    if mode=="normal":
        require(len(ack)==240 and len(reordered)==120
                and len(sets["issue"]-sets["ack"])==0,
                "NORMAL_ASYNC_ACK_NOT_COMPLETE")
        require("CPJA7CB_LOADER_INJECTED" not in client
                and "CPJA7C_RECOVERY_BEGIN" not in app,
                "NORMAL_RUN_HAD_LOSS")
        require(client.count("CPJA7DB_WORKER_STOP")==2
                and "CPJA7DB_DEVICE_LOST_DRAIN_REVOKED" not in client,
                "NORMAL_WORKER_CLEANUP_FAILED")
    else:
        require(client.count("CPJA7CB_LOADER_INJECTED_VK_ERROR_DEVICE_LOST")==1
                and client.count("CPJA7C_WGPU_DEVICE_LOST_CALLBACK reason=Unknown")==1
                and "CPJA7C_RECOVERY_COMPLETE epochs=1 submitted=120" in app,
                "LOADER_DEVICE_LOSS_RECOVERY_NOT_OBSERVED")
        require(client.count("CPJA7DB_DEVICE_LOST_DRAIN_REVOKED")==2
                and client.count("CPJA7D_DEVICE_WIDE_DRAIN_DENIED")==2
                and client.count("CPJA7DB_WORKER_STOP")==4,
                "DEVICE_GLOBAL_CANCELLATION_OR_THREAD_JOIN_MISSING")
        unacked=sets["issue"]-sets["ack"]
        require(unacked and len(unacked)<=4 and
                unacked.issubset({(1,39),(1,40),(2,39),(2,40)})
                and {(2,39),(2,40)}.issubset(unacked),
                "LOST_GENERATION_UNACKNOWLEDGED_BOUND_INVALID")
        cutoff=client.index("CPJA7D_LOSS_INVALIDATES_UNACKED")
        require(not re.search(
            r"CPJA7DB_ASYNC_TYPED_ACK generation=[12] present_id=\d+",
            client[cutoff:]),
            "OLD_GENERATION_ACK_AFTER_DEVICE_LOSS")
        require((1,41) not in sets["issue"] and (1,41) not in sets["ack"],
                "FAILED_PRESENT_FALSLY_ACKED")
    require("CPI02_WGPU_STREAM_COMPLETE submitted=120" in app,
            "FRAMES_NOT_COMPLETED")
    cp=re.findall(r"wp_presentation_feedback#\d+\.presented\(([^)]*)\)",client)
    sp=re.findall(r"ev wp_presentation_feedback@\d+\.presented\(([^)]*)\)",server)
    cd=re.findall(r"wp_presentation_feedback#\d+\.discarded\(",client)
    sd=re.findall(r"ev wp_presentation_feedback@\d+\.discarded\(",server)
    require(len(sp)==240 and not cd and not sd and
            not (Counter(cp)-Counter(sp)),"CLIENT_SERVER_FEEDBACK_DIVERGENCE")
    deficit=len(sp)-len(cp)
    require(deficit==0 if mode=="normal" else deficit<=2,
            "WAYLAND_FEEDBACK_CLIENT_UNDELIVERED_OVERBOUND")
    require(len(samples)==8 and all(
        s["primary"]["pixels_over_rgb3"]==s["secondary"]["pixels_over_rgb3"]==0
        and s["primary"]["pixels_alpha_mismatch"]==s["secondary"]["pixels_alpha_mismatch"]==0
        for s in samples),"COMPOSITOR_RGBA_BOUND_NOT_OBSERVED")
    return {
      "mode":mode,"frames":120,"swapchain_generations":generations,
      "issue_count":len(issued),"wait_success_count":len(waited),
      "worker_deliveries":len(delivered),"typed_acks":len(ack),
      "reorder_batches":len(batches),"out_of_order_acks":len(reordered),
      "unacknowledged":sorted([list(x) for x in sets["issue"]-sets["ack"]]),
      "maximum_inflight":2,
      "wayland_server_presented":len(sp),"wayland_client_presented":len(cp),
      "wayland_unreceived_by_client":deficit,"compositor_samples":len(samples),
      "real_vk_wait_proofs":True,"delivery_order_intentionally_reordered":True,
      "physical_present_order_reordered":False,"driver_device_loss":False,
      "zero_copy":False,"cp03_hybrid60":False
    }

def qualify(root,samples,started,mode):
    r=assess(root,samples,mode)
    r["schema"]="gnu6.qchain.cpja7db_async_wsi.v1"
    r["verdict"]="CPJA7DB_ASYNC_OUT_OF_ORDER_"+(
        "DEVICE_LOSS_RECOVERY_PASS" if mode=="loader-recovery"
        else "NORMAL_PASS")
    r["wall_seconds"]=round(time.monotonic()-started,3)
    r["samples"]=samples
    out=root/"run-verdict.json"
    require(not out.exists(),"REFUSE_REPLACE_POSITIVE_RECEIPT")
    out.write_text(json.dumps(r,indent=2)+"\n")
    print(r["verdict"],"ack",r["typed_acks"],"out_of_order",r["out_of_order_acks"],
          "revoked",r["unacknowledged"],flush=True)
