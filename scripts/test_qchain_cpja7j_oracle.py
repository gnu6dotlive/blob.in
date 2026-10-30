#!/usr/bin/env python3
"""Fail-closed factorial fraud tests on disposable copied source artifacts."""
import json,shutil,tempfile
from pathlib import Path
from qchain_cpja7j_independent_oracle import verify
ROOT=Path("/mnt/workbench/evidence/runs/qchain-cpja7j-20261012-01")
GOOD=ROOT/"runs/control-a"
def reject(name,fn):
    try:fn()
    except (AssertionError,RuntimeError,ValueError,KeyError,FileNotFoundError) as err:
        print("CPJA7J_ADVERSARY_REJECTED",name,str(err)[:75],flush=True)
        return
    raise AssertionError("FALSELY_ACCEPTED_"+name)
def mutate_line(path,needle,fn=None):
    rows=path.read_text(errors="replace").splitlines()
    for i,row in enumerate(rows):
        if needle in row:
            if fn is None:rows.pop(i)
            else:rows[i]=fn(row)
            path.write_text("\n".join(rows)+"\n")
            return
    raise AssertionError("SOURCE_TO_MUTATE_MISSING_"+needle)
def payload(name,mutator):
    with tempfile.TemporaryDirectory(prefix="cpja7j-adversarial-") as folder:
        d=Path(folder)
        for file in ("viewer.stdout","viewer.stderr","source.stdout",
                     "weston.stdout","weston-timeline-proto.log",
                     "gpu-query-raw.bin"):
            shutil.copy2(GOOD/file,d/file)
        (d/"engine-ledger").mkdir()
        for file in ("engine.stderr","timeline.json"):
            shutil.copy2(GOOD/"engine-ledger"/file,d/"engine-ledger"/file)
        for img in GOOD.glob("sample-*.png"):
            (d/img.name).symlink_to(img)
        mutator(d)
        reject(name,lambda:verify(d,65536,0))
def corrupt_json(root,modify):
    p=root/"engine-ledger/timeline.json"
    data=json.loads(p.read_text())
    modify(data)
    p.write_text(json.dumps(data)+"\n")
def corrupt_bytes(root):
    p=root/"gpu-query-raw.bin";raw=bytearray(p.read_bytes())
    raw[17]^=0x80;p.write_bytes(raw)
def alter_capture(root):
    from PIL import Image
    p=root/"sample-04.png";p.unlink()
    shutil.copy2(GOOD/p.name,p)
    with Image.open(p) as im:
        image=im.convert("RGBA")
        image.putpixel((100,700),(255,0,255,255))
        image.save(p)
def main():
    assert verify(GOOD,65536,0)["gpu_compute_frames"]==1200
    payload("pipe_capacity_claim",lambda d:mutate_line(
      d/"source.stdout","CPJA7J_INTERVENTION_CONFIG",
      lambda s:s.replace("pipe_bytes=65536","pipe_bytes=1048576")))
    payload("cache_mode_claim",lambda d:mutate_line(
      d/"source.stdout","CPJA7J_INTERVENTION_CONFIG",
      lambda s:s.replace("canonical_cache=0","canonical_cache=1")))
    payload("removed_full_equality_marker",lambda d:mutate_line(
      d/"source.stdout","CPJA7J_FULL_BYTE_COMPARE seq=90 "))
    payload("fabricated_equality_digest",lambda d:mutate_line(
      d/"source.stdout","CPJA7J_FULL_BYTE_COMPARE seq=120 ",
      lambda s:s.replace("reference_sha256=","reference_sha256="+("0"*64)+" forged=")))
    payload("fake_pipe_timeline",lambda d:corrupt_json(d,
      lambda x:x.__setitem__("cpja7j_pipe_bytes",1048576)))
    payload("fake_full_byte_count",lambda d:corrupt_json(d,
      lambda x:x.__setitem__("cpja7j_full_byte_comparisons",1199)))
    payload("wrong_reference_hash",lambda d:corrupt_json(d,
      lambda x:x["cpja7j_reference_sha256"].__setitem__(
        sorted(x["cpja7j_reference_sha256"])[0],"0"*64)))
    payload("ghost_source_sha",lambda d:corrupt_json(d,
      lambda x:x["frames"][50].__setitem__("pixel_sha256","f"*64)))
    payload("forged_gpu_timestamp_raw",corrupt_bytes)
    payload("missing_vulkan_ack",lambda d:mutate_line(
      d/"viewer.stderr","CPJA7DB_WORKER_WAIT_SUCCESS generation=1 present_id=22"))
    payload("missing_wayland_feedback",lambda d:mutate_line(
      d/"weston-timeline-proto.log",".presented("))
    payload("compositor_pixel_corrupted",alter_capture)
    print("CPJA7J_ADVERSARIAL_12_OF_12_PASS",flush=True)
if __name__=="__main__":main()

