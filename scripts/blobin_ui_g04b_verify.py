#!/usr/bin/env python3
"""Reproducible G04/B native launch qualification. Does NOT fake input E2E."""
from pathlib import Path
import subprocess,json,hashlib,re,sys
root=Path(__file__).resolve().parents[1]
out=root/"evidence/runs/blob-ui-g04b-20261012"
out.mkdir(parents=True,exist_ok=True)
checks={
"rustfmt":["rustfmt","--edition","2024","--check",
    "crates/showcase/src/bin/blobin_ui_g04b_wayland.rs"],
"clippy":["cargo","clippy","--offline","-p","blobin-showcase",
    "--bin","blobin_ui_g04b_wayland","--","-D","warnings"],
"native-build":["cargo","build","--offline","-p","blobin-showcase",
    "--bin","blobin_ui_g04b_wayland"],
"core-regression":["cargo","test","--offline","-p","blobin-ui-core","--all-targets"],
"workspace-lib":["cargo","test","--offline","--workspace","--lib"],
}
receipts={}
for label,cmd in checks.items():
    run=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=120)
    output=run.stdout+"\n"+run.stderr
    (out/(label+".log")).write_text(output)
    total=sum(int(x) for x in re.findall(r"test result: ok\. (\d+) passed;",output))
    valid=run.returncode==0
    if label=="core-regression":valid=valid and total>=65
    if label=="workspace-lib":valid=valid and total>=51
    receipts[label]={"pass":valid,"exit":run.returncode,
        "passed":total,"sha256":hashlib.sha256(output.encode()).hexdigest()}
    print(label,valid,total,flush=True)
metadata=json.loads(subprocess.check_output(
    ["cargo","metadata","--offline","--no-deps","--format-version","1"],cwd=root))
binary=Path(metadata["target_directory"])/"debug/blobin_ui_g04b_wayland"
native_output=out/"native-headless"
if receipts["native-build"]["pass"]:
    cmd=["python3",str(root/"scripts/blobin_ui_g04b_native_smoke.py"),
        "--output",str(native_output),"--binary",str(binary)]
    run=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=40)
    output=run.stdout+"\n"+run.stderr
    (out/"native-smoke.log").write_text(output)
    native=run.returncode==0 and (native_output/"native-smoke.json").exists()
    receipts["native-smoke"]={"pass":native,"exit":run.returncode,
        "sha256":hashlib.sha256(output.encode()).hexdigest()}
    print("native-smoke",native,flush=True)
else:
    receipts["native-smoke"]={"pass":False,"exit":-1,"reason":"native-build-failed"}
attempts=[]
base=Path("/mnt/workbench/evidence/runs/blob-ui-g04b-20261012-01")
for name in ("rdp-e2e-weston-gl","rdp-e2e-tls-only","rdp-e2e-rdp4","rdp-e2e-legacy-only"):
    path=base/name/"e2e-verdict.json"
    if path.exists():
        report=json.loads(path.read_text())
        attempts.append({"name":name,"verdict":report.get("verdict"),
            "rdp_connected":report.get("rdp_connected"),
            "compositor_winit_ingress":report.get("winit_ingress",0),
            "activation_count":report.get("activation_count",0),
            "gpu_frame_submissions":report.get("frame_submissions",0)})
sources=[
    "crates/showcase/Cargo.toml","Cargo.lock",
    "crates/showcase/src/bin/blobin_ui_g04b_wayland.rs",
    "scripts/blobin_ui_g04b_native_smoke.py",
    "scripts/blobin_ui_g04b_rdp_e2e.py",
    "scripts/blobin_ui_g04b_rdp_inject.c",
    "scripts/blobin_ui_g04b_verify.py",
    "docs/BLOB-UI-G04B-NATIVE-WAYLAND-INTEGRATION-20261012.md"]
valid=all(v["pass"] for v in receipts.values())
report={"gate":"UI-G04/B","date":"2026-10-12",
    "verdict":"NATIVE_WAYLAND_SCOPED_PASS_INPUT_E2E_HOLD" if valid else "FAIL",
    "native_launch_qualified":valid,
    "compositor_delivered_input_qualified":False,"ui_g04_full_pass":False,
    "no_desktop_injection_performed":True,
    "compositor_presentation_feedback_verified":False,
    "cp03_hybrid60_pass":False,
    "rdp_attempts":attempts,"checks":receipts,
    "sha256":{s:hashlib.sha256((root/s).read_bytes()).hexdigest() for s in sources}}
(out/"qualification.json").write_text(json.dumps(report,indent=2)+"\n")
print("UI_G04B_"+report["verdict"],flush=True)
sys.exit(0 if valid else 1)
