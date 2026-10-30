#!/usr/bin/env python3
"""Supplemental direct /proc CPU stimulus witness, not in preregistered six."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
def require(x,msg):
    if not x:raise RuntimeError(msg)
def snapshot():
    lines=subprocess.run(["ps","-eo","pid=,ppid=,args="],
                         capture_output=True,text=True,timeout=2).stdout.splitlines()
    rows=[]
    for line in lines:
        parts=line.strip().split(None,2)
        if len(parts)<3:continue
        pid_s,ppid_s,cmd=parts
        # Target the actual stress-ng process, never a shell holding the argv as text.
        if not (cmd.startswith("stress-ng --cpu ") or
                cmd.startswith("stress-ng-cpu")):continue
        try:
            pid=int(pid_s)
            fields=Path(f"/proc/{pid}/stat").read_text().split(") ",1)[1].split()
            ticks=int(fields[11])+int(fields[12])
            affinity=sorted(os.sched_getaffinity(pid))
        except (OSError,ValueError,IndexError):continue
        rows.append({"pid":pid,"ppid":int(ppid_s),
                     "ticks":ticks,"affinity":affinity,"argv":cmd})
    return rows
def main():
    p=argparse.ArgumentParser()
    for field in ("repo","evidence"):p.add_argument("--"+field,required=True,type=Path)
    p.add_argument("--profile",required=True,choices=["balanced","eco"])
    x=p.parse_args()
    repo=x.repo.resolve();e=x.evidence.resolve()
    name="pressure-proof-"+x.profile
    telemetry=e/"bench"/(name+".cpu-witness.jsonl")
    result=e/"bench"/(name+".cpu-witness.json")
    require(not telemetry.exists() and not result.exists(),"REPEAT_DENIED")
    with (e/"bench"/(name+".launcher.log")).open("xb") as output:
        runner=subprocess.Popen([
            sys.executable,str(repo/"scripts/qchain_cpja7ec_safety.py"),
            "--repo",str(repo),"--evidence",str(e),
            "--name",name,"--profile",x.profile,"--stress"
        ],stdout=output,stderr=subprocess.STDOUT)
        rows=[]
        deadline=time.monotonic()+75
        with telemetry.open("x") as witness:
            while runner.poll() is None and time.monotonic()<deadline:
                row={"monotonic_ns":time.monotonic_ns(),"processes":snapshot()}
                rows.append(row)
                witness.write(json.dumps(row)+"\n")
                witness.flush()
                time.sleep(.35)
        if runner.poll() is None:
            runner.terminate()
            runner.wait(timeout=7)
        exit_code=runner.wait(timeout=7)
    matched={}
    for row in rows:
        for process in row["processes"]:
            if process["affinity"]==[18]:
                matched.setdefault(process["pid"],[]).append(process["ticks"])
    active={pid:{"observed_samples":len(ticks),
                 "observed_tick_growth":max(ticks)-min(ticks)}
            for pid,ticks in matched.items() if len(ticks)>=3}
    require(exit_code==0,"STRESS_GUARDED_RUN_NONZERO")
    require(len(rows)>=8 and active,"STRESS_ACTIVITY_NOT_OBSERVED")
    max_ticks=max(x["observed_tick_growth"] for x in active.values())
    require(max_ticks>=40,"STRESS_CPU_TIME_NOT_MEASURABLE")
    report={"schema":"gnu6.qchain.cpja7ec_cpu_stress_witness.v1",
            "run":name,"profile":x.profile,
            "samplings":len(rows),"cpu_affinity":[18],
            "proc_pids":active,"max_tick_growth":max_ticks,
            "launcher_exit":exit_code,
            "verdict":"CPJA7EC_STRESS_CPU18_LIVE_WITNESS_PASS",
            "whole_machine_stress":False}
    result.write_text(json.dumps(report,indent=2)+"\n")
    print(report["verdict"],name,"samples",len(rows),
          "ticks_growth",max_ticks,flush=True)
if __name__=="__main__":main()
