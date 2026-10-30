#!/usr/bin/env python3
"""CP-JA7F independent best-effort residency PID and CPU18 load witness."""
import argparse,json,os,subprocess,time
from pathlib import Path
def read(cmd):
    r=subprocess.run(["ps","-eo","pid=,ppid=,comm=,args="],
                     capture_output=True,text=True,timeout=2)
    if r.returncode:raise RuntimeError("PS_STATUS_NONZERO")
    rows=[]
    for line in r.stdout.splitlines():
        p=line.strip().split(None,3)
        if len(p)!=4:continue
        pid,ppid,comm,command=p
        if not pid.isdigit():continue
        if comm=="weston" and "-S cpja7f-w-2850796" in command:
            kind="weston"
        elif comm=="qchain_cpja7_du" and command.startswith(
            "/mnt/workbench/evidence/runs/qchain-cpja7f-20261012-01/preflight/bin/qchain_cpja7_dual_viewer "):
            kind="viewer"
        elif comm.startswith("stress-ng") and "stress-ng" in command:
            kind="stress"
        else:continue
        try:
            affinity=sorted(os.sched_getaffinity(int(pid)))
            stat=Path(f"/proc/{pid}/stat").read_text().split(") ",1)[1].split()
            ticks=int(stat[11])+int(stat[12])
        except (OSError,IndexError,ValueError):
            continue
        rows.append({"kind":kind,"pid":int(pid),"ppid":int(ppid),
                     "cpu_affinity":affinity,"cpu_ticks":ticks})
    return rows
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",required=True,type=Path)
    a=ap.parse_args()
    p=a.root/"telemetry/residency-process-witness.jsonl"
    if p.exists():raise RuntimeError("PID_WITNESS_REFUSE_OVERWRITE")
    deadline=time.monotonic()+1480
    normal_exit=False
    samples=0
    with p.open("x") as f:
        while time.monotonic()<deadline:
            proc=read(None)
            viewer=[x for x in proc if x["kind"]=="viewer"]
            weston=[x for x in proc if x["kind"]=="weston"]
            events={"monotonic_ns":time.monotonic_ns(),
                    "viewer":viewer,"weston":weston,
                    "stress":[x for x in proc if x["kind"]=="stress"]}
            f.write(json.dumps(events)+"\n")
            f.flush()
            samples+=1
            if not viewer or not weston:
                normal_exit=True
                break
            time.sleep(2)
    print("CPJA7F_PID_WATCH_EXIT",json.dumps({
      "samples":samples,"stop_on_process_exit":normal_exit,
      "timeout":not normal_exit}),flush=True)
if __name__=="__main__":main()
