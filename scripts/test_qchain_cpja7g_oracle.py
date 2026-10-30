#!/usr/bin/env python3
"""CP-JA7G adversarial evidence: temp copies only, all falsifications fail closed."""
import copy,json,shutil,tempfile
from pathlib import Path
from qchain_cpja7g_independent_oracle import verify
from qchain_cpja7g_validate import BASE,RECEIPT,check_sensors
ROOT=Path("/mnt/workbench/evidence/runs/qchain-cpja7g-20261012-01")
NAME="active-balanced-3600-02"
def require(ok,msg):
    if not ok:raise RuntimeError(msg)
def reject(name,call):
    try:call()
    except (AssertionError,RuntimeError,ValueError,KeyError,TypeError) as error:
        print("CPJA7G_ADVERSARY_REJECTED",name,str(error)[:58],flush=True)
        return
    raise AssertionError("FALSELY_ACCEPTED_"+name)
def thermal(name,mutate):
    summary=json.loads((ROOT/"bench"/(NAME+".safety.json")).read_text())
    samples=[json.loads(x) for x in
             (ROOT/"bench"/(NAME+".thermal.jsonl")).read_text().splitlines()]
    mutate(summary,samples)
    reject(name,lambda:check_sensors(NAME,"balanced",summary,samples))
def modify_line(path,term,replacement=None):
    rows=path.read_text(errors="replace").splitlines()
    for i,line in enumerate(rows):
        if term in line:
            if replacement is None:rows.pop(i)
            else:rows[i]=replacement(line)
            path.write_text("\n".join(rows)+"\n")
            return
    raise RuntimeError("ADVERSARIAL_SOURCE_NOT_FOUND_"+term)
def fake_wsi(name,mutate):
    with tempfile.TemporaryDirectory(prefix="cpja7g-adversarial-") as d:
        p=Path(d);original=ROOT/"runs"/NAME
        for name_file in ("viewer.stdout","viewer.stderr",
                          "weston.stdout","weston-timeline-proto.log"):
            shutil.copy2(original/name_file,p/name_file)
        (p/"engine-ledger").mkdir()
        shutil.copy2(original/"engine-ledger/engine.stderr",
                     p/"engine-ledger/engine.stderr")
        for f in original.glob("sample-*.png"):
            (p/f.name).symlink_to(f)
        mutate(p)
        reject(name,lambda:verify(p,BASE,RECEIPT))
def tamper_pixel(p):
    from PIL import Image
    file=p/"sample-04.png"
    file.unlink()
    shutil.copy2(ROOT/"runs"/NAME/file.name,file)
    with Image.open(file) as image:
        copy=image.convert("RGBA")
        copy.putpixel((100,700),(255,0,255,255))
        copy.save(file)
def main():
    unaltered=verify(ROOT/"runs"/NAME,BASE,RECEIPT)
    require(unaltered["source_frames"]==3600,"ORIGINAL_NOT_VALID")
    thermal("temperature_breach",lambda a,s:s[20].__setitem__("temp_c",75.0))
    thermal("board_power_breach",lambda a,s:s[21].__setitem__("power_w",180.0))
    thermal("sensor_gap",lambda a,s:s[22].__setitem__(
       "monotonic_ns",s[21]["monotonic_ns"]+4_000_000_000))
    thermal("thermometer_wrong_run",lambda a,s:s[24].__setitem__("test_name","forged"))
    thermal("fake_sensor_summary",lambda a,s:a.__setitem__("temp_max_c",0.0))
    thermal("fake_gpu_activity",lambda a,s:a.__setitem__("gpu_util_max_pct",101))
    thermal("temperature_baseline_hot",lambda a,s:s[0].__setitem__("temp_c",66.0))
    thermal("missing_sensor_rows",lambda a,s:s.__delitem__(slice(90,None)))
    thermal("fake_gpu_power_attribution",
            lambda a,s:a.__setitem__("host_power_attributable_to_app",True))
    fake_wsi("missing_real_vk_wait",lambda p:modify_line(
        p/"viewer.stderr","CPJA7DB_WORKER_WAIT_SUCCESS generation=1 present_id=2"))
    fake_wsi("ghost_vulkan_ack",lambda p:(
        p/"viewer.stderr").open("a").write(
            "CPJA7DB_ASYNC_TYPED_ACK generation=1 present_id=3601 pending=0\n"))
    fake_wsi("missing_submit",lambda p:modify_line(
        p/"viewer.stderr","CPJA7DB_ASYNC_ISSUED generation=2 present_id=56"))
    fake_wsi("source_sha_mutated",lambda p:modify_line(
        p/"viewer.stdout","CPI02_WGPU_PRESENT_SUBMITTED seq=100 ",
        lambda line:line.replace("rgba_sha256=",
            "rgba_sha256="+("0"*64)+" fabricated=")))
    fake_wsi("missing_gpu_compute",lambda p:modify_line(
        p/"engine-ledger/engine.stderr","CPJA7G_GPU_COMPUTED seq=300 "))
    fake_wsi("false_gpu_session",lambda p:modify_line(
        p/"engine-ledger/engine.stderr","CPJA7G_GPU_STREAM_COMPLETE",
        lambda line:line.replace("device=1","device=2")))
    fake_wsi("missing_wayland_presented",lambda p:modify_line(
        p/"weston-timeline-proto.log",".presented("))
    fake_wsi("visual_pixel_corruption",tamper_pixel)
    print("CPJA7G_ADVERSARIAL_17_OF_17_PASS",flush=True)
if __name__=="__main__":main()
