#!/usr/bin/env python3
"""CP-JA7: same-device dual swapchain authority, compositor visibility kept separate."""
import argparse,hashlib,json,re
from pathlib import Path
from PIL import Image,ImageOps
import qchain_cpi02_independent_oracle as prior

def need(v,e):
    if not v:raise ValueError(e)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def analyze(run,baseline,receipt,mode):
    app=(run/"viewer.stdout").read_text()
    client=(run/"viewer.stderr").read_text()
    server=(run/"weston-timeline-proto.log").read_text()
    need("CPJA7_TWO_SWAPS_ONE_DEVICE" in app,"TWO_WINDOW_SINGLE_DEVICE_NOT_PROVEN")
    primary=[int(x) for x in re.findall(r"CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+)",app)]
    secondary=[int(x) for x in re.findall(r"CPJA7_SECONDARY_PRESENT seq=(\d+)",app)]
    need(primary==list(range(120)),"PRIMARY_SOURCE_FRAME_SEQUENCE")
    expected_secondary=120 if mode=="dual" else 60
    need(secondary==list(range(expected_secondary)),"SECONDARY_SOURCE_FRAME_SEQUENCE")
    ack=[(int(g),int(i)) for g,i in re.findall(
       r"CPJA6_TYPED_ACK generation=(\d+) present_id=(\d+) status=VK_SUCCESS",client)]
    gens=sorted({g for g,_ in ack})
    need(len(gens)==2,"EXACTLY_TWO_SWAPCHAIN_GENERATIONS_REQUIRED")
    need([i for g,i in ack if g==gens[0]]==list(range(1,121)),
         "PRIMARY_SWAPCHAIN_TYPED_ACK_DRIFT")
    need([i for g,i in ack if g==gens[1]]==list(range(1,expected_secondary+1)),
         "SECONDARY_SWAPCHAIN_TYPED_ACK_DRIFT")
    need(len(ack)==120+expected_secondary,"TOTAL_TYPED_ACK_COUNT")
    need("CPJA5_HAL_PRESENT_WAIT_TIMEOUT" not in client and "CPJA6_SWAPCHAIN_POISONED" not in client,
         "UNQUALIFIED_WSI_TIMEOUT")
    presented=re.findall(r"wp_presentation_feedback#\d+\.presented\(([^)]*)\)",client)
    discarded=re.findall(r"wp_presentation_feedback#\d+\.discarded\(",client)
    server_presented=re.findall(r"ev wp_presentation_feedback@\d+\.presented\(([^)]*)\)",server)
    server_discarded=re.findall(r"ev wp_presentation_feedback@\d+\.discarded\(",server)
    need(presented==server_presented and len(discarded)==len(server_discarded),
         "WAYLAND_CLIENT_SERVER_DISAGREEMENT")
    need(len(presented)+len(discarded)==len(ack),
         "COMPOSITOR_OUTCOME_NOT_ACCOUNTED")
    samples=[]
    for idx in range(8):
        p=run/f"sample-{idx:02}.png"
        need(p.exists(),"MISSING_COMPOSITOR_SAMPLE")
        with Image.open(p) as image:
            need(image.size==(512,384),"UNEXPECTED_SAMPLE_DIMENSIONS")
            actual=ImageOps.flip(image.convert("RGBA")).tobytes()
        mat=("ceramic","gel","metal","paper")[idx//2]
        ref=baseline/f"state4-{mat}-frame{idx%2}-dpr2.gpu-rgba.bin"
        expected=ref.read_bytes()
        diff=sum(actual[i:i+4]!=expected[i:i+4] for i in range(0,len(actual),4))
        samples.append(diff)
    if mode=="dual":
        need(all(x==0 for x in samples),"DUAL_VISIBLE_COMPOSITOR_SAMPLE_MISMATCH")
        prior.verify(run,baseline,receipt)
        need("CPJA7_SECONDARY_RELEASE" not in app,"UNEXPECTED_SECONDARY_DROP")
        verdict="CPJA7_SAME_DEVICE_DUAL_VK_WAIT_2X120_PASS_KIOSK_OCCLUSION_NOTED"
    else:
        need("CPJA7_SECONDARY_RELEASE after_seq=59 primary_preserved=1" in app,
             "SECONDARY_CLEAN_RELEASE_WITNESS_MISSING")
        need(samples[:5]==[0]*5 and any(x>0 for x in samples[5:]),
             "DROPPED_WINDOW_VISIBILITY_DISCREPANCY_NOT_REPRODUCED")
        need(not (run/"run-verdict.json").exists(),"MISMATCH_MUST_NOT_RECEIVE_PASS")
        verdict="CPJA7_DROP_SECONDARY_VK_180_ACK_PASS_VISUAL_RECOVERY_HOLD"
    return dict(schema="gnu6.qchain.cpja7_independent_oracle.v1",verdict=verdict,
        mode=mode,one_vulkan_device=True,swapchain_generations=gens,
        source_gpu_frames=120,primary_vk_wait_success=120,
        secondary_vk_wait_success=expected_secondary,
        client_presented=len(presented),server_presented=len(server_presented),
        client_discarded=len(discarded),server_discarded=len(server_discarded),
        screenshot_pixel_differences=samples,
        both_windows_confirmed_visually=False,
        visible_window_samples_exact=all(x==0 for x in samples),
        client_trace_sha256=sha(run/"viewer.stderr"),
        server_trace_sha256=sha(run/"weston-timeline-proto.log"),
        zero_copy=False,hybrid_60=False,device_loss_recovery_tested=False)

def main():
    p=argparse.ArgumentParser()
    for n in ("run","baseline","receipt","out"):
        p.add_argument("--"+n,required=True,type=Path)
    p.add_argument("--mode",required=True,choices=["dual","drop"])
    a=p.parse_args()
    need(not a.out.exists(),"REFUSE_OVERWRITE")
    report=analyze(a.run,a.baseline,a.receipt,a.mode)
    a.out.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],"gpu_typed_acks",report["primary_vk_wait_success"]+
          report["secondary_vk_wait_success"])
if __name__=="__main__":main()
