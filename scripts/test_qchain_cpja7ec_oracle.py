#!/usr/bin/env python3
"""E2E oracle and thermal-guard falsification on isolated temporary copies."""
import copy
import json
import shutil
import tempfile
from pathlib import Path
from qchain_cpja7ec_validate import check_safety,check_stress
from qchain_cpja7ec_independent_oracle import verify

E=Path("/mnt/workbench/evidence/runs/qchain-cpja7ec-20261012-01")
BASE=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
RECEIPT=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json")
NAME="pilot-balanced-03"
def need(ok,msg):
    if not ok:raise RuntimeError(msg)
def refuse(name,call):
    try:call()
    except (AssertionError,RuntimeError,ValueError,KeyError) as error:
        print("CPJA7EC_ADVERSARIAL_REJECTED",name,str(error)[:76])
        return
    raise AssertionError("ORACLE_FALSE_ACCEPT_"+name)
def check_mod(name,change):
    report=json.loads((E/"bench"/(NAME+".safety.json")).read_text())
    samples=[json.loads(line) for line in
             (E/"bench"/(NAME+".thermal.jsonl")).read_text().splitlines()]
    change(report,samples)
    refuse(name,lambda:check_safety(NAME,"balanced",False,report,samples))
def copy_run(temp):
    original=E/"runs"/NAME
    for name in ("viewer.stdout","viewer.stderr","weston.stdout",
                 "weston-timeline-proto.log"):
        shutil.copy2(original/name,temp/name)
    for p in original.glob("sample-*.png"):shutil.copy2(p,temp/p.name)
def run_oracle_corruption(name,change):
    with tempfile.TemporaryDirectory(prefix="cpja7ec-oracle-false-") as d:
        root=Path(d)
        copy_run(root)
        change(root)
        refuse(name,lambda:verify(root,BASE,RECEIPT))
def omit_line(path,needle):
    rows=path.read_text().splitlines()
    for i,row in enumerate(rows):
        if needle in row:
            rows.pop(i)
            path.write_text("\n".join(rows)+"\n")
            return
    raise AssertionError("MUTATION_SOURCE_NOT_FOUND_"+needle)
def replace_first(path,old,new):
    s=path.read_text()
    need(old in s,"NO_OCCURRENCE_FOR_MUTATION")
    path.write_text(s.replace(old,new,1))
def pixel_corrupt(root):
    from PIL import Image
    p=root/"sample-04.png"
    with Image.open(p) as im:
        im=im.convert("RGBA")
        im.putpixel((100,700),(255,0,200,255))
        im.save(p)
def main():
    check_mod("temperature_ceiling",
              lambda r,s:s[2].__setitem__("temp_c",75.0))
    check_mod("power_ceiling",
              lambda r,s:s[3].__setitem__("power_w",180.0))
    check_mod("sensor_gap",
              lambda r,s:s[3].__setitem__("monotonic_ns",s[2]["monotonic_ns"]+4_000_000_000))
    check_mod("reversed_sensor_order",
              lambda r,s:s.reverse())
    check_mod("forged_summary_max_temp",
              lambda r,s:r.__setitem__("temp_max_c",74.0))
    check_mod("baseline_too_hot",
              lambda r,s:s[0].__setitem__("temp_c",65.0))
    check_mod("fabricated_success",
              lambda r,s:r.__setitem__("verdict","FABRICATED_SUCCESS"))
    check_mod("lost_samples",
              lambda r,s:s.__delitem__(slice(4,None)))
    check_mod("wrong_host_power_attribution",
              lambda r,s:r.__setitem__("host_power_attributable_to_app",True))
    check_mod("false_affinity",
              lambda r,s:r.__setitem__("runner_affinity",[0,1]))
    check_mod("wrong_profile",
              lambda r,s:r.__setitem__("profile","eco"))
    check_mod("wrong_stress_flag",
              lambda r,s:r.__setitem__("stress_cpu_18",True))
    check_mod("nonzero_runner_exit",
              lambda r,s:r.__setitem__("runner_exit",1))
    check_mod("wrong_sample_owner",
              lambda r,s:s[1].__setitem__("test_name","another-run"))
    cpu_name="pressure-proof-eco"
    cpu_report=json.loads((E/"bench"/(cpu_name+".cpu-witness.json")).read_text())
    cpu_rows=[json.loads(line) for line in
              (E/"bench"/(cpu_name+".cpu-witness.jsonl")).read_text().splitlines()]
    cpu_report["max_tick_growth"]=999999
    refuse("fabricated_cpu_activity",
           lambda:check_stress(cpu_name,cpu_report,cpu_rows))
    run_oracle_corruption("missing_vulkan_wait",
        lambda root:omit_line(root/"viewer.stderr",
                              "CPJA7DB_WORKER_WAIT_SUCCESS generation=1 present_id=2"))
    run_oracle_corruption("forged_vulkan_ack",
        lambda root:(root/"viewer.stderr").open("a").write(
                    "CPJA7DB_ASYNC_TYPED_ACK generation=2 present_id=301 pending=0\n"))
    run_oracle_corruption("source_sha_falsification",
        lambda root:replace_first(root/"viewer.stdout","rgba_sha256=",
                                   "rgba_sha256="+("0"*64)+" isolated="))
    run_oracle_corruption("server_feedback_missing",
        lambda root:omit_line(root/"weston-timeline-proto.log",
                              ".presented("))
    run_oracle_corruption("pixel_corrupted",pixel_corrupt)
    print("CPJA7EC_ADVERSARIAL_20_OF_20_PASS",flush=True)
if __name__=="__main__":main()
