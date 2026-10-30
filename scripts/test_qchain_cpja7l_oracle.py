#!/usr/bin/env python3
"""Adversarial copied-evidence attacks against pipe, GPU, Vulkan and screenshots."""
import json,shutil,tempfile
from pathlib import Path
from qchain_cpja7j_independent_oracle import verify as transport
from qchain_cpja7k_oracle import gpu_verify
E=Path("/mnt/workbench/evidence/runs/qchain-cpja7l-20261012-01")
R=E/"runs/pipe-a1"
def need(ok,why):
    if not ok:raise AssertionError(why)
def reject(name,mutate,which):
    with tempfile.TemporaryDirectory(prefix="cpja7l-adversarial-") as d:
        root=Path(d);(root/"engine-ledger").mkdir()
        for f in ("source.stdout","viewer.stdout","viewer.stderr",
                  "weston.stdout","weston-timeline-proto.log",
                  "gpu-query-raw.bin","f4-copy-query.bin"):
            shutil.copy2(R/f,root/f)
        for f in ("timeline.json","engine.stderr"):
            shutil.copy2(R/"engine-ledger"/f,root/"engine-ledger"/f)
        for p in R.glob("sample-*.png"):(root/p.name).symlink_to(p)
        mutate(root)
        try:
            if which=="transport":transport(root,65536,0)
            else:gpu_verify(root,1200)
        except (AssertionError,ValueError,KeyError,OSError,RuntimeError) as err:
            print("CPJA7L_FALSE_EVIDENCE_REJECTED",name,str(err)[:70],flush=True)
            return
        raise AssertionError("FALSIFIED_EVIDENCE_ACCEPTED_"+name)
def alter_text(path,old,new):
    s=path.read_text(errors="replace")
    need(old in s,"MUTATION_TARGET_NOT_FOUND_"+old)
    path.write_text(s.replace(old,new,1))
def altered_pixel(root):
    from PIL import Image
    p=root/"sample-04.png";p.unlink();shutil.copy2(R/p.name,p)
    with Image.open(p) as frame:
        rgba=frame.convert("RGBA")
        rgba.putpixel((180,710),(255,0,255,255))
        rgba.save(p)
def main():
    assert transport(R,65536,0)["gpu_compute_frames"]==1200
    assert gpu_verify(R,1200)["gpu_query_count"]==21600
    reject("wrong_actual_pipe_size",
         lambda p:alter_text(p/"source.stdout","pipe_bytes=65536","pipe_bytes=1048576"),
         "transport")
    reject("wrong_pipe_timeline",
         lambda p:alter_text(p/"engine-ledger/timeline.json",
                    '"cpja7j_pipe_bytes": 65536','"cpja7j_pipe_bytes": 1048576'),
         "transport")
    reject("false_canonical_cache",
         lambda p:alter_text(p/"source.stdout","canonical_cache=0","canonical_cache=1"),
         "transport")
    reject("wrong_reference_hash",
         lambda p:alter_text(p/"source.stdout","reference_sha256=",
              "reference_sha256="+("0"*64)+" ghost="),"transport")
    reject("missing_source_frame",
         lambda p:alter_text(p/"viewer.stdout","CPI02_WGPU_PRESENT_SUBMITTED seq=89 ",
                       "CPI02_BAD_FRAME seq=89 "),"transport")
    reject("missing_vulkan_wait",
         lambda p:alter_text(p/"viewer.stderr",
              "CPJA7DB_WORKER_WAIT_SUCCESS generation=1 present_id=17",
              "CPJA7DB_INVALID_WAIT generation=1 present_id=17"),"transport")
    reject("missing_weston_feedback",
         lambda p:alter_text(p/"weston-timeline-proto.log",".presented(",
                            ".not_presented("),"transport")
    reject("changed_compositor_pixel",altered_pixel,"transport")
    reject("truncated_gpu_raw",
         lambda p:(p/"f4-copy-query.bin").write_bytes(
           (p/"f4-copy-query.bin").read_bytes()[:-8]),"gpu")
    reject("fake_copy_duration",
         lambda p:alter_text(p/"engine-ledger/engine.stderr",
             "CPJA7K_F4_GPU_COPY_TIMING seq=12 period_ns=1 ",
             "CPJA7K_F4_GPU_COPY_TIMING seq=12 period_ns=2 "),"gpu")
    reject("missing_gpu_witness",
         lambda p:alter_text(p/"engine-ledger/engine.stderr",
             "CPJA7K_F4_GPU_COPY_TIMING seq=22",
             "CPJA7K_F4_INVALID_TIMING seq=22"),"gpu")
    reject("invalid_host_readback_poll",
         lambda p:alter_text(p/"engine-ledger/engine.stderr",
             "host_readback_wait_us=","host_readback_wait_us=9999999 fake="),"gpu")
    print("CPJA7L_ADVERSARIAL_12_OF_12_PASS",flush=True)
if __name__=="__main__":main()
