#!/usr/bin/env python3
"""Adversarial temporary-copy tests; canonical evidence never mutated."""
import hashlib
import re
import shutil
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
from qchain_cpja7cb_independent_oracle import audit

E=Path("/mnt/workbench/evidence/runs/qchain-cpja7cb-20261011-01")
B=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
RECEIPT=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json")
GOOD=E/"runs/loader-recovery-02"
LOGS=("viewer.stdout","viewer.stderr","weston.stdout","weston-timeline-proto.log")

def fixture(root):
    root.mkdir()
    for name in LOGS:shutil.copy2(GOOD/name,root/name)
    for p in GOOD.glob("sample-*.png"):shutil.copy2(p,root/p.name)

def change_log(root,name,replace):
    f=root/name
    before=f.read_text()
    after=replace(before)
    if before==after:raise AssertionError("TEST_MUTATION_WAS_NO_OP")
    f.write_text(after)

def missing_fault(root):
    change_log(root,"viewer.stderr",lambda s:s.replace(
        "CPJA7CB_LOADER_INJECTED_VK_ERROR_DEVICE_LOST","CPJA7CB_FAKE_INJECT_LOG",1))

def missing_callback(root):
    change_log(root,"viewer.stderr",lambda s:s.replace(
        "CPJA7C_WGPU_DEVICE_LOST_CALLBACK","CPJA7C_CALLBACK_REMOVED",1))

def missing_new_ack(root):
    change_log(root,"viewer.stderr",lambda s:"\n".join(
        x for x in s.splitlines() if
        "CPJA6_TYPED_ACK generation=4 present_id=80 " not in x)+"\n")

def forge_bad_ack(root):
    change_log(root,"viewer.stderr",lambda s:s+
        "\nCPJA6_TYPED_ACK generation=1 present_id=41 status=VK_SUCCESS\n")

def remove_ready(root):
    change_log(root,"viewer.stdout",lambda s:"\n".join(
        x for x in s.splitlines() if "CPJA7C_RECOVERY_READY " not in x)+"\n")

def duplicate_final_seq(root):
    change_log(root,"viewer.stdout",lambda s:s.replace(
        "CPI02_WGPU_PRESENT_SUBMITTED seq=119 ",
        "CPI02_WGPU_PRESENT_SUBMITTED seq=118 ",1))

def bad_pixel(root):
    p=root/"sample-05.png"
    with Image.open(p) as img:
        flipped=np.asarray(ImageOps.flip(img.convert("RGBA"))).copy()
    flipped[230,150,0]=(int(flipped[230,150,0])+45)%256
    ImageOps.flip(Image.fromarray(flipped,"RGBA")).save(p)

def surface_alias(root):
    p=root/"sample-01.png"
    with Image.open(p) as img:
        flipped=np.asarray(ImageOps.flip(img.convert("RGBA"))).copy()
    flipped[190:574,810:1322]=flipped[190:574,92:604].copy()
    ImageOps.flip(Image.fromarray(flipped,"RGBA")).save(p)

def delete_presented(root):
    def mutate(s):
        lines=s.splitlines()
        for i,line in enumerate(lines):
            if "ev wp_presentation_feedback@" in line and ".presented(" in line:
                del lines[i]
                return "\n".join(lines)+"\n"
        return s
    change_log(root,"weston-timeline-proto.log",mutate)

def corrupt_canonical_sha(root):
    def mutate(s):
        lines=s.splitlines()
        for i,line in enumerate(lines):
            if "CPI02_WGPU_PRESENT_SUBMITTED seq=45 " in line:
                lines[i]=re.sub(r"rgba_sha256=[0-9a-f]{64}",
                                "rgba_sha256="+"0"*64,line,count=1)
                break
        return "\n".join(lines)+"\n"
    change_log(root,"viewer.stdout",mutate)

def missing_layer_negotiation(root):
    change_log(root,"viewer.stderr",lambda s:s.replace(
        "CPJA7CB_LOADER_NEGOTIATED","CPJA7CB_LAYER_NOT_NEGOTIATED",1))

def missing_dispatch_forward(root):
    change_log(root,"viewer.stderr",lambda s:s.replace(
        "CPJA7CB_LOADER_FIRST_FORWARD","CPJA7CB_DISPATCH_NOT_OBSERVED",1))

def forge_old_hal_event(root):
    change_log(root,"viewer.stderr",lambda s:s+
        "\nCPJA7C_INJECTED_VK_ERROR_DEVICE_LOST generation=1 present_id=41\n")

def main():
    require=audit(GOOD,B,RECEIPT)
    assert require["verdict"].endswith("_PASS")
    cases=(
        ("missing_fault",missing_fault,"LOADER_FAULT_BOUNDARY_OR_WITNESS_NOT_EXACT"),
        ("missing_callback",missing_callback,"REAL_WGPU_DEVICE_LOST_CALLBACK_NOT_OBSERVED"),
        ("missing_new_ack",missing_new_ack,"VK_TYPED_ACK_TOTAL_MISMATCH"),
        ("forged_failed_present_ack",forge_bad_ack,"VK_TYPED_ACK_TOTAL_MISMATCH"),
        ("missing_recovery_ready",remove_ready,"LOSS_RECOVERY_EVENT_ORDER_INVALID"),
        ("duplicate_source_sequence",duplicate_final_seq,"SOURCE_SEQUENCE_GAP_DUPLICATE"),
        ("post_recovery_pixel_corruption",bad_pixel,"COMPOSITOR_PIXEL_BOUNDS_EXCEEDED_5"),
        ("surfaces_aliased",surface_alias,"COMPOSITOR_PIXEL_BOUNDS_EXCEEDED_1"),
        ("missing_server_presented",delete_presented,"COMPOSITOR_PRESENTATION_EVENTS_DIVERGE"),
        ("corrupt_canonical_frame_digest",corrupt_canonical_sha,"CANONICAL_FRAME_SHA_MISMATCH"),
        ("missing_loader_negotiation",missing_layer_negotiation,"ACTUAL_VULKAN_LOADER_LAYER_DISPATCH_NOT_RECONCILED"),
        ("missing_dispatch_forward",missing_dispatch_forward,"ACTUAL_VULKAN_LOADER_LAYER_DISPATCH_NOT_RECONCILED"),
        ("forged_old_hal_event",forge_old_hal_event,"HAL_SIDE_SYNTHETIC_INJECTION_NOT_ALLOWED"),
    )
    with tempfile.TemporaryDirectory(prefix="cpja7c-negative-oracle-") as tmp:
        for name,mutate,expected in cases:
            fixture_root=Path(tmp)/name
            fixture(fixture_root)
            mutate(fixture_root)
            try:audit(fixture_root,B,RECEIPT)
            except AssertionError as error:
                if str(error)!=expected:
                    raise AssertionError(f"{name}: GOT {error}, EXPECTED {expected}")
                print("ADVERSARY_REJECTED",name)
            else:raise AssertionError(f"ORACLE_FALSE_ACCEPT_{name}")
    print(f"CPJA7CB_ORACLE_NEGATIVE_{len(cases)}_OF_{len(cases)}_PASS")

if __name__=="__main__":
    main()
