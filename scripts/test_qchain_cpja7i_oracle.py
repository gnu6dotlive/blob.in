#!/usr/bin/env python3
"""Mutate private copied evidence, never mutate original files."""
import shutil,tempfile
from pathlib import Path
from qchain_cpja7i_independent_oracle import verify
E=Path("/mnt/workbench/evidence/runs/qchain-cpja7i-20261012-01")
SRC=E/"runs/baseline-33-02"
def reject(name,call):
    try:call()
    except (AssertionError,RuntimeError,ValueError,KeyError,OSError) as error:
        print("CPJA7I_ADVERSARY_REJECTED",name,str(error)[:66],flush=True)
        return
    raise AssertionError("FALSE_ACCEPT_"+name)
def edit_line(file,word,replacement=None):
    lines=file.read_text(errors="replace").splitlines()
    for i,line in enumerate(lines):
        if word in line:
            if replacement is None:lines.pop(i)
            else:lines[i]=replacement(line)
            file.write_text("\n".join(lines)+"\n")
            return
    raise RuntimeError("MUTATION_NOT_FOUND_"+word)
def attack(name,modify):
    with tempfile.TemporaryDirectory(prefix="cpja7i-attack-") as d:
        root=Path(d)
        for fname in ("viewer.stdout","viewer.stderr","source.stdout",
                      "weston.stdout","weston-timeline-proto.log",
                      "gpu-query-raw.bin"):
            shutil.copy2(SRC/fname,root/fname)
        (root/"engine-ledger").mkdir()
        shutil.copy2(SRC/"engine-ledger/engine.stderr",
                     root/"engine-ledger/engine.stderr")
        for frame in SRC.glob("sample-*.png"):
            (root/frame.name).symlink_to(frame)
        modify(root)
        reject(name,lambda:verify(root,33))
def altered_pixel(root):
    from PIL import Image
    p=root/"sample-04.png"
    p.unlink()
    shutil.copy2(SRC/p.name,p)
    with Image.open(p) as image:
        rgba=image.convert("RGBA")
        rgba.putpixel((100,700),(255,0,255,255))
        rgba.save(p)
def raw_corrupt(root):
    p=root/"gpu-query-raw.bin";b=bytearray(p.read_bytes())
    b[100]^=0x80;p.write_bytes(b)
def main():
    assert verify(SRC,33)["frames"]==1200
    attack("missing_gpu_query_raw",lambda r:(r/"gpu-query-raw.bin").unlink())
    attack("corrupt_gpu_query_raw",raw_corrupt)
    attack("missing_gpu_capability",lambda r:edit_line(r/"viewer.stdout",
        "CPJA7I_GPU_QUERY_CAPABILITY"))
    attack("fake_gpu_period",lambda r:edit_line(r/"viewer.stdout",
        "CPJA7I_GPU_QUERY_COMPLETE",lambda s:s.replace("period_ns=1 ","period_ns=2 ")))
    attack("fake_gpu_sum",lambda r:edit_line(r/"viewer.stdout",
        "CPJA7I_GPU_QUERY_COMPLETE",lambda s:s.replace("primary_total_ns=",
            "primary_total_ns=99999999999 bogus=")))
    attack("missing_causal_frame",lambda r:edit_line(r/"viewer.stdout",
        "CPJA7I_FRAME_CAUSAL seq=100 "))
    attack("forged_causal_sequence",lambda r:edit_line(r/"viewer.stdout",
        "CPJA7I_FRAME_CAUSAL seq=101 ",lambda s:s.replace("seq=101 ","seq=999 ")))
    attack("bad_requested_interval",lambda r:edit_line(r/"viewer.stdout",
        "CPJA7I_FRAME_CAUSAL seq=102 ",lambda s:s.replace(
            "requested_interval_us=33000","requested_interval_us=16000")))
    attack("missing_real_gpu_wait",lambda r:edit_line(r/"viewer.stderr",
        "CPJA7DB_WORKER_WAIT_SUCCESS generation=1 present_id=15"))
    attack("missing_weston_presented",lambda r:edit_line(
        r/"weston-timeline-proto.log",".presented("))
    attack("altered_compositor_pixel",altered_pixel)
    print("CPJA7I_ADVERSARIAL_11_OF_11_PASS",flush=True)
if __name__=="__main__":main()
