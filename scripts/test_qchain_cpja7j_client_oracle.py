#!/usr/bin/env python3
"""Client materialization mode cannot be spoofed without oracle rejection."""
import json,shutil,tempfile
from pathlib import Path
from qchain_cpja7j_client_oracle import verify
E=Path("/mnt/workbench/evidence/runs/qchain-cpja7j-20261012-01")
SRC=E/"runs/client-copy-a"
def reject(name,call):
    try:call()
    except (AssertionError,ValueError,RuntimeError,KeyError,FileNotFoundError) as exc:
        print("CPJA7J_CLIENT_ADVERSARY_REJECTED",name,str(exc)[:70],flush=True)
        return
    raise AssertionError("FALSE_ACCEPT_"+name)
def edit_line(p,needle,replacement=None):
    lines=p.read_text(errors="replace").splitlines()
    for i,line in enumerate(lines):
        if needle in line:
            if replacement is None:lines.pop(i)
            else:lines[i]=replacement(line)
            p.write_text("\n".join(lines)+"\n")
            return
    raise AssertionError("SOURCE_MISSING_"+needle)
def attack(name,modify):
    with tempfile.TemporaryDirectory(prefix="cpja7j-client-attack-") as t:
        p=Path(t)
        for filename in ("viewer.stdout","viewer.stderr","source.stdout",
                         "weston.stdout","weston-timeline-proto.log",
                         "gpu-query-raw.bin"):
            shutil.copy2(SRC/filename,p/filename)
        (p/"engine-ledger").mkdir()
        for filename in ("engine.stderr","timeline.json"):
            shutil.copy2(SRC/"engine-ledger"/filename,p/"engine-ledger"/filename)
        for screenshot in SRC.glob("sample-*.png"):
            (p/screenshot.name).symlink_to(screenshot)
        modify(p)
        reject(name,lambda:verify(p,"copy"))
def corrupt_timestamp(p):
    f=p/"gpu-query-raw.bin";raw=bytearray(f.read_bytes())
    raw[13]^=0x40;f.write_bytes(raw)
def main():
    assert verify(SRC,"copy")["frames"]==1200
    attack("missing_mode",lambda p:edit_line(p/"viewer.stdout","CPJA7J_CLIENT_OWNERSHIP"))
    attack("falsely_declared_mmap",lambda p:edit_line(
        p/"viewer.stdout","CPJA7J_CLIENT_OWNERSHIP",lambda x:x.replace("mode=copy","mode=mmap")))
    attack("missing_mode_sample",lambda p:edit_line(
        p/"viewer.stdout","CPJA7J_CLIENT_PIXEL_MODE seq=90 "))
    attack("wrong_mode_sample",lambda p:edit_line(
        p/"viewer.stdout","CPJA7J_CLIENT_PIXEL_MODE seq=120 ",
        lambda x:x.replace("mode=copy","mode=mmap")))
    attack("wrong_pixel_hash",lambda p:edit_line(
        p/"viewer.stdout","CPJA7J_CLIENT_PIXEL_MODE seq=150 ",
        lambda x:x.replace("source_sha256=","source_sha256="+("0"*64)+" fake=")))
    attack("removed_source_full_byte_check",lambda p:edit_line(
        p/"source.stdout","CPJA7J_FULL_BYTE_COMPARE seq=180 "))
    attack("altered_gpu_timestamp",corrupt_timestamp)
    attack("missing_vulkan_wait",lambda p:edit_line(
        p/"viewer.stderr","CPJA7DB_WORKER_WAIT_SUCCESS generation=1 present_id=18"))
    print("CPJA7J_CLIENT_ADVERSARIAL_8_OF_8_PASS",flush=True)
if __name__=="__main__":main()

