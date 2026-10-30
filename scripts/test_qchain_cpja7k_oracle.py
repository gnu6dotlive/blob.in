#!/usr/bin/env python3
"""Adversarial copy-GPU timestamp and WSI oracle falsification tests."""
import shutil,tempfile
from pathlib import Path
from qchain_cpja7k_oracle import verify
E=Path("/mnt/workbench/evidence/runs/qchain-cpja7k-20261012-01")
R=E/"runs/f4-copy-1200"
def reject(name,mutate,native=False):
    with tempfile.TemporaryDirectory(prefix="cpja7k-negative-") as folder:
        root=Path(folder);(root/"engine-ledger").mkdir()
        shutil.copy2(R/"f4-copy-query.bin",root/"f4-copy-query.bin")
        shutil.copy2(R/"engine-ledger/engine.stderr",root/"engine-ledger/engine.stderr")
        if native:
            for namefile in ("viewer.stdout","viewer.stderr","source.stdout",
                             "weston.stdout","weston-timeline-proto.log",
                             "gpu-query-raw.bin"):
                shutil.copy2(R/namefile,root/namefile)
            for pic in R.glob("sample-*.png"):(root/pic.name).symlink_to(pic)
        mutate(root)
        try:verify(root,1200,native)
        except (AssertionError,RuntimeError,ValueError,KeyError,OSError) as error:
            print("CPJA7K_ADVERSARY_REJECTED",name,str(error)[:70],flush=True)
            return
        raise AssertionError("FALSELY_ACCEPTED_"+name)
def edit(root,pattern,replacement):
    path=root/"engine-ledger/engine.stderr"
    source=path.read_text()
    assert pattern in source
    path.write_text(source.replace(pattern,replacement,1))
def tamper_raw(root):
    p=root/"f4-copy-query.bin";b=bytearray(p.read_bytes())
    b[20]=0;b[21]=0;b[22]=0;b[23]=0
    p.write_bytes(b)
def pixel(root):
    from PIL import Image
    pic=root/"sample-04.png";pic.unlink();shutil.copy2(R/pic.name,pic)
    with Image.open(pic) as frame:
        rgba=frame.convert("RGBA")
        rgba.putpixel((180,710),(255,0,255,255))
        rgba.save(pic)
def remove_row(root,file,needle):
    p=root/file
    s=p.read_text(errors="replace").splitlines()
    for i,row in enumerate(s):
        if needle in row:
            s.pop(i);p.write_text("\n".join(s)+"\n");return
    raise AssertionError("MUTATION_LINE_MISSING_"+needle)
def main():
    assert verify(R)["frame_count"]==1200
    reject("missing_raw",lambda r:(r/"f4-copy-query.bin").unlink())
    reject("short_raw",lambda r:(r/"f4-copy-query.bin").write_bytes(
        (r/"f4-copy-query.bin").read_bytes()[:-8]))
    reject("corrupt_raw",tamper_raw)
    reject("wrong_gpu_copy_duration",lambda r:edit(r,"rgba_ns=","rgba_ns=999999 ghost="))
    reject("wrong_period",lambda r:edit(r,"CPJA7K_F4_GPU_COPY_TIMING seq=0 period_ns=1",
                       "CPJA7K_F4_GPU_COPY_TIMING seq=0 period_ns=2"))
    reject("missing_copy_witness",lambda r:edit(r,"CPJA7K_F4_GPU_COPY_TIMING seq=0",
                            "CPJA7K_COPY_MISSING seq=0"))
    reject("fake_source_device",lambda r:edit(r,"frames=1200 device=1",
                                  "frames=1200 device=2"))
    reject("missing_gpu_completion",lambda r:edit(r,"CPJA7K_F4_QUERY_STREAM_COMPLETE",
                                  "CPJA7K_NOT_COMPLETE"))
    reject("missing_shader_witness",lambda r:edit(r,"CPJA7JC_F4_KERNEL_TIMING seq=0",
                                      "CPJA7JC_BAD_KERNEL seq=0"))
    reject("missing_vk_wait",lambda r:remove_row(r,"viewer.stderr",
           "CPJA7DB_WORKER_WAIT_SUCCESS generation=1 present_id=7"),True)
    reject("missing_wayland_feedback",lambda r:remove_row(r,"weston-timeline-proto.log",
           ".presented("),True)
    reject("corrupt_visual_pixel",pixel,True)
    print("CPJA7K_ADVERSARIAL_12_OF_12_PASS",flush=True)
if __name__=="__main__":main()
