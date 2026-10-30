#!/usr/bin/env python3
"""Reject manufactured evidence on temporary copies: never modify the canonical run."""
from pathlib import Path
import re
import shutil
import tempfile
import numpy as np
from PIL import Image, ImageOps
from qchain_cpja7db_independent_oracle import audit

E=Path("/mnt/workbench/evidence/runs/qchain-cpja7db-20261011-01")
B=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
C=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json")
LOSS=E/"runs/final-loss-01"
NORMAL=E/"runs/final-normal-01"
FILES=("viewer.stdout","viewer.stderr","weston.stdout","weston-timeline-proto.log")

def fixture(root,origin=LOSS):
    root.mkdir()
    for name in FILES:
        shutil.copy2(origin/name,root/name)
    for p in origin.glob("sample-*.png"):
        shutil.copy2(p,root/p.name)

def edit(root,file,func):
    target=root/file
    old=target.read_text()
    new=func(old)
    if old==new:
        raise AssertionError("ADVERSARIAL_MUTATION_WAS_NO_OP")
    target.write_text(new)

def replace(root,file,a,b):
    edit(root,file,lambda s:s.replace(a,b,1))

def omit_line(root,file,fragment):
    def mutate(s):
        ls=s.splitlines()
        for i,x in enumerate(ls):
            if fragment in x:
                del ls[i]
                return "\n".join(ls)+"\n"
        return s
    edit(root,file,mutate)

def mutate_pixel(root,alias=False):
    path=root/("sample-01.png" if alias else "sample-05.png")
    with Image.open(path) as im:
        pixels=np.asarray(ImageOps.flip(im.convert("RGBA"))).copy()
    if alias:
        pixels[190:574,810:1322]=pixels[190:574,92:604].copy()
    else:
        pixels[230,150,0]=(int(pixels[230,150,0])+45)%256
    ImageOps.flip(Image.fromarray(pixels)).save(path)

def change_frame_hash(root):
    edit(root,"viewer.stdout",
         lambda s:re.sub(r"(CPI02_WGPU_PRESENT_SUBMITTED seq=45 .*?rgba_sha256=)[0-9a-f]{64}",
                         lambda m:m.group(1)+"0"*64,s,count=1))

def reorder_ack(root):
    def mutate(s):
        a="CPJA7DB_ASYNC_TYPED_ACK generation=3 present_id=20 pending=1"
        b="CPJA7DB_ASYNC_TYPED_ACK generation=3 present_id=21 pending=0"
        if a not in s or b not in s:return s
        return s.replace(a,"TEMP_REORDER",1).replace(b,a,1).replace("TEMP_REORDER",b,1)
    edit(root,"viewer.stderr",mutate)

def delete_five_feedbacks(root):
    def mutate(s):
        lines=s.splitlines()
        count=0
        out=[]
        for line in lines:
            if count<5 and "ev wp_presentation_feedback@" in line and ".presented(" in line:
                count+=1
            else:out.append(line)
        if count!=5:return s
        return "\n".join(out)+"\n"
    edit(root,"weston-timeline-proto.log",mutate)

def run_control(name,mutate,origin=LOSS):
    with tempfile.TemporaryDirectory(prefix="cpja7d-oracle-control-") as tmp:
        root=Path(tmp)/"test"
        fixture(root,origin)
        mutate(root)
        try:
            audit(root,B,C)
        except (AssertionError,RuntimeError) as error:
            print("ADVERSARY_REJECTED",name,str(error),flush=True)
            return
        raise AssertionError("ORACLE_FALSE_ACCEPT_"+name)

def main():
    assert audit(LOSS,B,C)["mode"]=="loader-recovery"
    assert audit(NORMAL,B,C)["mode"]=="normal"
    controls=[
        ("missing_loader_fault",lambda r:omit_line(r,"viewer.stderr",
             "CPJA7CB_LOADER_INJECTED_VK_ERROR_DEVICE_LOST")),
        ("missing_device_callback",lambda r:omit_line(r,"viewer.stderr",
             "CPJA7C_WGPU_DEVICE_LOST_CALLBACK")),
        ("missing_secondary_global_fence",lambda r:omit_line(r,"viewer.stderr",
             "CPJA7D_DEVICE_WIDE_DRAIN_DENIED generation=2")),
        ("forged_ack_after_secondary_poison",lambda r:edit(r,"viewer.stderr",
             lambda s:s+"\nCPJA7DB_ASYNC_TYPED_ACK generation=2 present_id=40 pending=0\n")),
        ("forged_ack_of_failed_present",lambda r:edit(r,"viewer.stderr",
             lambda s:s+"\nCPJA7DB_ASYNC_TYPED_ACK generation=1 present_id=41 pending=1\n")),
        ("missing_final_rebuilt_ack",lambda r:omit_line(r,"viewer.stderr",
             "CPJA7DB_ASYNC_TYPED_ACK generation=4 present_id=80")),
        ("duplicated_inflight_issue",lambda r:edit(r,"viewer.stderr",
             lambda s:s+"\nCPJA7DB_ASYNC_ISSUED generation=3 present_id=2 pending=2 cap=2\n")),
        ("window_depth_exceeded",lambda r:replace(r,"viewer.stderr",
             "pending=2 cap=2","pending=3 cap=2")),
        ("out_of_order_typed_ack",reorder_ack),
        ("missing_recovery_complete",lambda r:omit_line(r,"viewer.stdout",
             "CPJA7C_RECOVERY_COMPLETE")),
        ("duplicate_source_sequence",lambda r:replace(r,"viewer.stdout",
             "CPI02_WGPU_PRESENT_SUBMITTED seq=119 ",
             "CPI02_WGPU_PRESENT_SUBMITTED seq=118 ")),
        ("canonical_sha_forged",change_frame_hash),
        ("compositor_pixel_corruption",lambda r:mutate_pixel(r,False)),
        ("secondary_surface_aliased",lambda r:mutate_pixel(r,True)),
        ("server_presented_removed",delete_five_feedbacks),
        ("loader_negotiation_missing",lambda r:omit_line(r,"viewer.stderr",
             "CPJA7CB_LOADER_NEGOTIATED interface=2")),
        ("fake_hal_fault_witness",lambda r:edit(r,"viewer.stderr",
             lambda s:s+"\nCPJA7C_INJECTED_VK_ERROR_DEVICE_LOST generation=1 present_id=41\n")),
        ("client_feedback_forged",lambda r:edit(r,"viewer.stderr",
             lambda s:s+"\nwp_presentation_feedback#999999.presented(7, 8, 9, 10, 11, 12, 13)\n")),
        ("missing_actual_vk_wait",lambda r:omit_line(r,"viewer.stderr",
             "CPJA7DB_WORKER_WAIT_SUCCESS generation=3 present_id=2")),
        ("fabricated_wait_on_failed_id",lambda r:edit(r,"viewer.stderr",
             lambda s:s+"\nCPJA7DB_WORKER_WAIT_SUCCESS generation=1 present_id=41 observation=99\n")),
        ("missing_delivery_observation",lambda r:omit_line(r,"viewer.stderr",
             "CPJA7DB_WORKER_DELIVER generation=3 present_id=2")),
        ("missing_deliberate_pair_witness",lambda r:omit_line(r,"viewer.stderr",
             "CPJA7DB_DELIVERY_REORDERED generation=3 old=1 new=2")),
        ("missing_worker_join",lambda r:omit_line(r,"viewer.stderr",
             "CPJA7DB_WORKER_STOP generation=1")),
        ("misattributed_generation_ack",lambda r:replace(r,"viewer.stderr",
             "CPJA7DB_ASYNC_TYPED_ACK generation=3 present_id=2",
             "CPJA7DB_ASYNC_TYPED_ACK generation=4 present_id=2")),
    ]
    for name,mutation in controls:
        run_control(name,mutation)
    run_control("normal_missing_last_drain",
                lambda r:omit_line(r,"viewer.stderr",
                "CPJA7DB_ASYNC_TYPED_ACK generation=2 present_id=120"),NORMAL)
    print(f"CPJA7DB_ORACLE_ADVERSARIAL_{len(controls)+1}_OF_{len(controls)+1}_PASS")

if __name__=="__main__":
    main()
