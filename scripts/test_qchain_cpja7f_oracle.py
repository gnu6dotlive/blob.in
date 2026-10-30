#!/usr/bin/env python3
"""CP-JA7F adversarial mutagenesis: isolated files only; never edits canonical evidence."""
import copy,json,shutil,tempfile
from pathlib import Path
from qchain_cpja7f_validate import sensor_analysis,process_analysis,stream,validate,NAME,BASE,CPU
from qchain_cpja7f_independent_oracle import verify
E=Path("/mnt/workbench/evidence/runs/qchain-cpja7f-20261012-01")
def need(v,msg):
    if not v:raise AssertionError(msg)
def reject(name,fn):
    try:fn()
    except (AssertionError,RuntimeError,ValueError,TypeError,KeyError) as exc:
        print("CPJA7F_ADVERSARY_REJECTED",name,type(exc).__name__,str(exc)[:68])
        return
    raise AssertionError("CPJA7F_FALSE_POSITIVE_"+name)
def fake_sensor(name,alter):
    data=copy.deepcopy(stream(E/"bench"/(NAME+".thermal.jsonl")))
    alter(data)
    reject(name,lambda:sensor_analysis(data,True))
def fake_pid(name,alter):
    data=copy.deepcopy(stream(E/"telemetry/residency-process-witness.jsonl"))
    alter(data)
    reject(name,lambda:process_analysis(data,True))
def remove_first(path,needle):
    lines=path.read_text(errors="replace").splitlines()
    for i,line in enumerate(lines):
        if needle in line:
            lines.pop(i)
            path.write_text("\n".join(lines)+"\n")
            return
    raise AssertionError("MUTATOR_WITNESS_NOT_PRESENT_"+needle)
def replace_first(path,old,new):
    text=path.read_text(errors="replace")
    need(old in text,"MUTATOR_WITNESS_NOT_PRESENT")
    path.write_text(text.replace(old,new,1))
def fake_wsi(name,alter):
    with tempfile.TemporaryDirectory(prefix="cpja7f-forged-") as directory:
        root=Path(directory)
        source=E/"runs"/NAME
        for item in ("viewer.stdout","viewer.stderr","weston.stdout",
                     "weston-timeline-proto.log"):
            shutil.copy2(source/item,root/item)
        for item in source.glob("sample-*.png"):
            (root/item.name).symlink_to(item)
        alter(root)
        reject(name,lambda:verify(root,BASE,CPU))
def pixel_mutate(root):
    from PIL import Image
    file=root/"sample-04.png"
    file.unlink()
    shutil.copy2(E/"runs"/NAME/file.name,file)
    with Image.open(file) as image:
        rgba=image.convert("RGBA")
        rgba.putpixel((100,700),(255,31,255,255))
        rgba.save(file)
def main():
    original=validate(
       Path("/home/tension_atoi/Projects/.worktrees/blobin-showcase-qcja7f-20261012"),E)
    need(original["native"]["source_frames"]==300,"ORIGINAL_NOT_VALIDATED")
    fake_sensor("critical_temperature",lambda d:d[170].__setitem__("temp_c",75.0))
    fake_sensor("critical_power",lambda d:d[200].__setitem__("power_w",180.0))
    fake_sensor("sensor_gap",lambda d:d[40].__setitem__(
        "monotonic_ns",d[39]["monotonic_ns"]+4_000_000_000))
    fake_sensor("reversed_sensor_clock",lambda d:d.reverse())
    fake_sensor("missing_long_interval",lambda d:d.__delitem__(slice(800,None)))
    fake_sensor("fake_baseline",lambda d:d[0].__setitem__("temp_c",66.0))
    fake_sensor("sensor_owner",lambda d:d[19].__setitem__("test_name","wrong-run"))
    fake_sensor("sensor_power_negative",lambda d:d[41].__setitem__("power_w",-5))
    fake_sensor("gpu_util_impossible",lambda d:d[42].__setitem__("gpu_util_pct",101))
    fake_sensor("fan_impossible",lambda d:d[43].__setitem__("fan_pct",180))
    fake_sensor("measurement_timeout",lambda d:d[44].__setitem__("query_duration_ms",3500))
    fake_sensor("sensor_nonnumber",lambda d:d[20].__setitem__("temp_c",float("nan")))
    fake_pid("pid_changed",lambda d:d[22]["viewer"][0].__setitem__("pid",999999))
    fake_pid("weston_replaced",lambda d:d[28]["weston"][0].__setitem__("pid",999998))
    fake_pid("affinity_broken",lambda d:d[13]["viewer"][0].__setitem__("cpu_affinity",[0,1]))
    fake_pid("missing_weston",lambda d:d[20]["weston"].clear())
    fake_pid("process_series_truncated",lambda d:d.__delitem__(slice(150,None)))
    fake_pid("missing_stress",lambda d:[row["stress"].clear() for row in d])
    fake_wsi("vulkan_wait_dropped",
             lambda r:remove_first(r/"viewer.stderr","CPJA7DB_WORKER_WAIT_SUCCESS generation=1 present_id=2"))
    fake_wsi("nonfifo_ack_missing",
             lambda r:remove_first(r/"viewer.stderr","CPJA7DB_OUT_OF_ORDER_TYPED_ACK generation=1 present_id=2"))
    fake_wsi("ghost_success_ack",
             lambda r:(r/"viewer.stderr").open("a").write(
                 "CPJA7DB_ASYNC_TYPED_ACK generation=1 present_id=301 pending=0\n"))
    fake_wsi("wrong_device_lifetime",
             lambda r:replace_first(r/"viewer.stdout",
                 "CPJA7F_RESIDENT_DEVICE_CREATED epoch=0",
                 "CPJA7F_RESIDENT_DEVICE_CREATED epoch=1"))
    fake_wsi("wrong_native_pacing",
             lambda r:replace_first(r/"viewer.stdout","elapsed_us=","elapsed_us=999999999999 "))
    fake_wsi("source_rgba_corrupt",
             lambda r:replace_first(r/"viewer.stdout","rgba_sha256=",
                      "rgba_sha256="+("f"*64)+" fabricated="))
    fake_wsi("compositor_ack_dropped",
             lambda r:remove_first(r/"weston-timeline-proto.log",
                      ".presented("))
    fake_wsi("visual_pixel_corruption",pixel_mutate)
    print("CPJA7F_ADVERSARIAL_26_OF_26_PASS")
if __name__=="__main__":main()
