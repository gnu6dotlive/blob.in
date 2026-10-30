#!/usr/bin/env python3
"""Reproducible UI-G04/A headless qualification. No Wayland E2E claim."""
from pathlib import Path
import subprocess,re,json,hashlib,sys
root=Path(__file__).resolve().parents[1]
out=root/"evidence/runs/blob-ui-g04a-20261012"
out.mkdir(parents=True,exist_ok=True)
checks={
"format":["cargo","fmt","-p","blobin-ui-core","--","--check"],
"core":["cargo","test","--offline","-p","blobin-ui-core","--all-targets"],
"clippy":["cargo","clippy","--offline","-p","blobin-ui-core","--all-targets","--","-D","warnings"],
"dependencies":["cargo","tree","--offline","-p","blobin-ui-core"],
"consumer":["cargo","run","--offline","-p","blobin-ui-core","--example","input_workbench"],
"workspace":["cargo","test","--offline","--workspace","--lib"],
}
results={}
for label,cmd in checks.items():
    run=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=120)
    output=run.stdout+"\n"+run.stderr
    (out/(label+".log")).write_text(output)
    passed=sum(map(int,re.findall(r"test result: ok\. (\d+) passed;",output)))
    valid=run.returncode==0
    if label=="core": valid=valid and passed>=65 and "overlapping_nodes_route_to_last_painted_target ... ok" in output
    if label=="workspace": valid=valid and passed>=51
    if label=="consumer": valid=valid and "BLOBIN_UI_G04_HEADLESS_OK" in output
    if label=="dependencies": valid=valid and len(output.strip().splitlines())==1
    results[label]={"pass":valid,"exit":run.returncode,"test_count":passed,"sha256":hashlib.sha256(output.encode()).hexdigest()}
    print(label,valid,passed,flush=True)
sources=["crates/blobin-ui-core/src/input.rs","crates/blobin-ui-core/src/lib.rs",
 "crates/blobin-ui-core/tests/input_routing.rs",
 "crates/blobin-ui-core/examples/input_workbench.rs",
 "docs/BLOB-UI-G04A-HEADLESS-INPUT-20261012.md","scripts/blobin_ui_g04a_verify.py"]
receipt={"gate":"UI-G04/A","verdict":"SCOPED_PASS" if all(v["pass"] for v in results.values()) else "FAIL",
 "baseline":"5cf1ece9e140a7cfb91d105868041ba6c59bf5ff",
 "checks":results,"sha256":{x:hashlib.sha256((root/x).read_bytes()).hexdigest() for x in sources},
 "input_e2e_native_verified":False,"g04b_full_pass":False,"cp03_hybrid60_pass":False}
(out/"qualification.json").write_text(json.dumps(receipt,indent=2)+"\n")
print("UI_G04A_"+receipt["verdict"])
sys.exit(0 if receipt["verdict"]=="SCOPED_PASS" else 1)
