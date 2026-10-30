#!/usr/bin/env python3
"""BLOB-AC-03 qualification gates with reproducible local evidence.
Never injects host desktop input. Requires a private user+network namespace.
"""
import hashlib,json,os,shlex,subprocess,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"evidence/runs/blob-ac03-20261012"
SOURCES=[
 "contracts/BLOB-AC-03-COMPOSITOR-GESTURE-E2E-20261012.md",
 "docs/BLOB-AC-03-QUALIFICATION-20261012.md",
 "docs/PROGRAM-INTEGRATION-SPINE-20261012.md",
 "crates/showcase/src/bin/blobin_ui_ac02_wayland.rs",
 "crates/showcase/src/ac02_scene.rs",
 "scripts/blob_ac03_weston_test_input.c",
 "scripts/blob_ac03_isolated_e2e.py",
 "scripts/blob_ac03_verify.py",
]
COMMANDS=[
 ["rustfmt","--edition","2021","--check","crates/showcase/src/bin/blobin_ui_ac02_wayland.rs"],
 ["cargo","clippy","--offline","-p","blobin-showcase","--lib","--bin","blobin_ui_ac02_wayland","--","-D","warnings"],
 ["cargo","test","--offline","-p","blobin-showcase","--lib","ac02_scene"],
 ["cargo","test","--offline","-p","blobin-ui-core","--all-targets"],
 ["cargo","test","--offline","--workspace","--lib"],
 ["cargo","build","--offline","-p","blobin-showcase","--bin","blobin_ui_ac02_wayland"],
]
def sha(path):
 return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def git(*args):
 return subprocess.run(["git",*args],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
def run_step(n,cmd):
 res=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=150)
 out=OUT/f"gate-{n:02d}.stdout.txt"
 err=OUT/f"gate-{n:02d}.stderr.txt"
 out.write_text(res.stdout.rstrip("\n")+("\n" if res.stdout else ""),encoding="utf-8")
 err.write_text(res.stderr.rstrip("\n")+("\n" if res.stderr else ""),encoding="utf-8")
 print(f"AC03-G{n:02d} {'PASS' if res.returncode==0 else 'FAIL'} - {' '.join(map(str,cmd))}",flush=True)
 return {
  "argv":list(map(str,cmd)), "exit_code":res.returncode,
  "stdout":str(out.relative_to(ROOT)),"stdout_sha256":sha(out),
  "stderr":str(err.relative_to(ROOT)),"stderr_sha256":sha(err),
 }
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 pkg=subprocess.run(["cargo","metadata","--offline","--no-deps","--format-version","1"],
     cwd=ROOT,capture_output=True,text=True,check=True)
 target=Path(json.loads(pkg.stdout)["target_directory"])
 binary=target/"debug/blobin_ui_ac02_wayland"
 ledger={
  "gate":"BLOB-AC-03",
  "utc":datetime.now(timezone.utc).isoformat(),
  "git_baseline":git("rev-parse","HEAD"),
  "branch":git("branch","--show-current"),
  "origin":git("remote","get-url","origin"),
  "sources":{p:sha(ROOT/p) for p in SOURCES},
  "commands":[],
  "safe_scope":"Weston 15 private seat and private user+network namespace. No active-desktop input, no host network server.",
  "pixel_scope":"actual GPU window swapchain COPY_SRC before present; no compositor presentation feedback",
  "physical_HID":False,"compositor_presentation_feedback":False,
  "cp03_hybrid_60":"UNQUALIFIED",
 }
 ok=ledger["branch"]=="main" and ledger["origin"]=="https://github.com/tension-atoi/blob.in-showcase.git"
 for i,cmd in enumerate(COMMANDS,1):
  item=run_step(i,cmd)
  ledger["commands"].append(item)
  if item["exit_code"]!=0:
   ok=False
   break
 if ok:
  with tempfile.TemporaryDirectory(prefix="blob-ac03-compiled-") as temp:
   mod=Path(temp)/"blob_ac03_input_module.so"
   flags=subprocess.run(["pkg-config","--cflags","libweston-15"],capture_output=True,text=True,check=True)
   libs=subprocess.run(["pkg-config","--libs","libweston-15"],capture_output=True,text=True,check=True)
   cmd=["cc","-std=gnu11","-Wall","-Wextra","-Werror","-shared","-fPIC","-O2",
     *shlex.split(flags.stdout),"scripts/blob_ac03_weston_test_input.c","-o",str(mod),*shlex.split(libs.stdout)]
   item=run_step(7,cmd)
   ledger["commands"].append(item)
   if item["exit_code"]==0:
    ledger["test_module_sha256"]=sha(mod)
    ledger["native_binary_sha256"]=sha(binary)
    cmd=[sys.executable,"scripts/blob_ac03_isolated_e2e.py","--out",str(OUT/"isolated"),
       "--binary",str(binary),"--module",str(mod)]
    item=run_step(8,cmd)
    ledger["commands"].append(item)
    ok=item["exit_code"]==0
    if ok:
     native=json.loads((OUT/"isolated/isolated-receipt.json").read_text())
     ok=(native.get("verdict")=="COMPOSITOR_DELIVERED_GESTURE_PLUS_GPU_CLIENT_PIXEL_PASS" and
       native.get("ingress_count")==6 and native.get("router_receipts")==6 and
       native.get("commits")==1 and native.get("frame_submissions",0)>=4 and
       native.get("physical_HID") is False and
       native.get("compositor_presentation_feedback") is False and
       native.get("weston_module_sha256")==sha(mod) and
       native.get("client_binary_sha256")==sha(binary))
     ledger["witness"]=native
     ledger["witness_sha256"]=sha(OUT/"isolated/isolated-receipt.json")
   else:ok=False
 else:ok=False
 ledger["result"]="SCOPED_PASS_COMPOSITOR_INPUT_CLIENT_GPU_PIXELS" if ok else "HOLD"
 path=OUT/"qualification.json"
 path.write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("BLOB_AC03_"+ledger["result"],flush=True)
 return 0 if ok else 1
if __name__=="__main__":
 sys.exit(main())
