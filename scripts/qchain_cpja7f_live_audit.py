#!/usr/bin/env python3
"""CP-JA7F in-flight read-only prefix verifier; never grants final admission."""
import argparse,hashlib,json,re
from pathlib import Path
from qchain_cpja7f_validate import sensor_analysis,process_analysis,stream

def need(ok,msg):
    if not ok:raise AssertionError(msg)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",required=True,type=Path)
    args=p.parse_args()
    root=args.evidence
    run=root/"runs/resident-20min-02"
    app=(run/"viewer.stdout").read_text(errors="replace")
    client=(run/"viewer.stderr").read_text(errors="replace")
    receiver=json.loads(Path(
        "/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json"
    ).read_text())["stages"]
    refs=[]
    base=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
    for material in ("ceramic","gel","metal","paper"):
        for i in (0,1):
            f=base/f"state4-{material}-frame{i}-dpr2.gpu-rgba.bin"
            refs.append(hashlib.sha256(f.read_bytes()).hexdigest())
    records=re.findall(
      r"CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+) stage=(\d+) elapsed_us=(\d+)"
      r" received_to_submit_us=(\d+) epoch=(\d+) scene_sha256=([0-9a-f]{64})"
      r" rgba_sha256=([0-9a-f]{64}) dimensions=(\d+)x(\d+)",app)
    n=len(records)
    need(n>0 and [int(x[0]) for x in records]==list(range(n)),
         "PREFIX_SEQUENCE_MISSING_DUPLICATE_OR_GAP")
    for rec in records:
        seq=int(rec[0]);stage=min(seq,4)
        need(int(rec[1])==stage and rec[5]==receiver[stage]["scene_sha256"]
             and rec[-2:]==("512","384"),"PREFIX_SCENE_FAULT")
        if seq>=5:
            need(rec[6]==refs[((seq-5)//12)%8],
                 "PREFIX_RGBA_SOURCE_WRONG")
    issued=re.findall(r"CPJA7DB_ASYNC_ISSUED generation=(\d+) present_id=(\d+)",client)
    acknowledged=re.findall(r"CPJA7DB_ASYNC_TYPED_ACK generation=(\d+) present_id=(\d+)",client)
    need(len(issued)>=2*n-2 and len(issued)<=2*n+2,
         "WSI_SOURCE_DISCREPANCY_LIVE")
    need(len(set(issued))==len(issued) and len(set(acknowledged))==len(acknowledged)
         and set(acknowledged).issubset(set(issued)),
         "DUPLICATE_OR_UNISSUED_TYPED_ACK")
    need("CPJA7C_RECOVERY_BEGIN" not in app and
         "CPJA7CB_LOADER_INJECTED" not in client,
         "UNAUTHORIZED_RECOVERY_OR_FAULT")
    need(app.count("CPJA7F_RESIDENT_DEVICE_CREATED epoch=0")==1 and
         "CPJA7F_RESIDENT_DEVICE_CREATED epoch=1" not in app,
         "DISCONTINUOUS_LOGICAL_DEVICE")
    sensor=sensor_analysis(stream(root/"bench/resident-20min-02.thermal.jsonl"),False)
    process=process_analysis(stream(root/"telemetry/residency-process-witness.jsonl"),False)
    report={"schema":"gnu6.qchain.cpja7f_live_prefix.v1",
            "provisional_not_final":True,
            "frames":n,"issued":len(issued),"typed_acks":len(acknowledged),
            "sensor_records":sensor["samples"],
            "sensor_temp_max":sensor["temp_max_c"],
            "sensor_power_max":sensor["power_max_w"],
            "viewer_pid":process["viewer_pid"],
            "weston_pid":process["weston_pid"]}
    print("CPJA7F_LIVE_PREFIX_PASS",json.dumps(report))
if __name__=="__main__":main()
