#!/usr/bin/env python3
"""Adversarial falsifications of the preregistered statistical summary."""
import copy
import json
import tempfile
from pathlib import Path
from qchain_cpja7eb_analyze import analyze

ROOT=Path("/mnt/workbench/evidence/runs/qchain-cpja7eb-20261012-01")
def must_reject(name,change):
    with tempfile.TemporaryDirectory(prefix="cpja7eb-false-") as td:
        root=Path(td)
        (root/"bench").mkdir()
        (root/"oracle").mkdir()
        for key in ("plan.json","normal-metrics.json"):
            (root/"bench"/key).write_bytes((ROOT/"bench"/key).read_bytes())
        for p in (ROOT/"oracle").glob("r??-*.json"):
            (root/"oracle"/p.name).write_bytes(p.read_bytes())
        change(root)
        try:
            analyze(root)
        except (RuntimeError,AssertionError,KeyError,ZeroDivisionError) as error:
            print("CPJA7EB_ADVERSARY_REJECTED",name,str(error)[:65])
            return
        raise AssertionError("FORGED_RESULT_ACCEPTED_"+name)
def mutate_data(root,change):
    path=root/"bench/normal-metrics.json"
    rows=json.loads(path.read_text())
    change(rows)
    path.write_text(json.dumps(rows))
def mutate_plan(root,change):
    path=root/"bench/plan.json"
    j=json.loads(path.read_text())
    change(j)
    path.write_text(json.dumps(j))
def mutate_oracle(root,change):
    path=next((root/"oracle").glob("r01-*.json"))
    j=json.loads(path.read_text())
    change(j)
    path.write_text(json.dumps(j))
def require_held(name,change,gate):
    with tempfile.TemporaryDirectory(prefix="cpja7eb-gate-") as td:
        root=Path(td)
        (root/"bench").mkdir()
        (root/"oracle").mkdir()
        for key in ("plan.json","normal-metrics.json"):
            (root/"bench"/key).write_bytes((ROOT/"bench"/key).read_bytes())
        for p in (ROOT/"oracle").glob("r??-*.json"):
            (root/"oracle"/p.name).write_bytes(p.read_bytes())
        change(root)
        result=analyze(root)
        if result[gate]:
            raise AssertionError("FALSE_PASS_"+name)
        print("CPJA7EB_ADVERSARY_HELD",name,gate)
def main():
    positive=analyze(ROOT)
    assert positive["total_runs"]==15 and positive["preregistered_latency_gate_pass"]
    cases=[
        ("plan_seed",lambda r:mutate_plan(r,lambda p:p.__setitem__("seed",123))),
        ("plan_order",lambda r:mutate_plan(r,lambda p:p["schedule"].reverse())),
        ("duplicate_round",lambda r:mutate_data(r,lambda d:d.__setitem__(1,copy.deepcopy(d[0])))),
        ("missing_run",lambda r:mutate_data(r,lambda d:d.pop())),
        ("wrong_profile",lambda r:mutate_data(r,lambda d:d[0].__setitem__("profile","latency" if d[0]["profile"]!="latency" else "eco"))),
        ("bad_worker_count",lambda r:mutate_data(r,lambda d:d[0].__setitem__("worker_context_records",0))),
        ("no_idle",lambda r:mutate_data(r,lambda d:d[0].__setitem__("idle_markers_complete",False))),
        ("fake_oracle_ack",lambda r:mutate_oracle(r,lambda d:d.__setitem__("acknowledged",239))),
        ("missing_screenshot",lambda r:mutate_oracle(r,lambda d:d["screenshots"].pop())),
        ("wrong_oracle_verdict",lambda r:mutate_oracle(r,lambda d:d.__setitem__("verdict","FABRICATED_PASS"))),
    ]
    for name,action in cases:must_reject(name,action)
    require_held("unsafe_latency",
        lambda r:mutate_data(r,lambda d:d[0].__setitem__("latency_gate_pass",False)),
        "preregistered_latency_gate_pass")
    require_held("fabricated_eco_cpu_advantage",
        lambda r:mutate_data(r,lambda d:[
            row.__setitem__("worker_cpu_us",200000)
            for row in d if row["profile"]=="eco"]),
        "scoped_cost_improvement_gate_pass")
    print("CPJA7EB_ADVERSARIAL_12_OF_12_PASS")
if __name__=="__main__":main()
