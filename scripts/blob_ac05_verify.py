#!/usr/bin/env python3
"""BLOB-AC-05 offline qualification: source regression, compiled module,
real-production captured evidence revalidation. NO live Weston input replay.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,shlex,subprocess,sys,tempfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"evidence/runs/blob-ac05-20261012"
SOURCES=[
 "contracts/BLOB-AC-05-PRODUCTION-NATIVE-E2E-20261012.md",
 "docs/BLOB-AC-05-PRODUCTION-NATIVE-QUALIFICATION-20261012.md",
 "docs/PROGRAM-INTEGRATION-SPINE-20261012.md",
 "crates/showcase/src/app.rs",
 "scripts/blob_ac05_weston_test_input.c",
 "scripts/blob_ac05_private_preflight.py",
 "scripts/blob_ac05_qualify_capture.py",
 "scripts/blob_ac05_revalidate.py",
 "scripts/blob_ac05_verify.py",
]
COMMANDS=[
 ["cargo","test","--offline","-p","blobin-showcase","--lib","ac04_production_input_tests"],
 ["cargo","test","--offline","-p","blobin-showcase","--lib"],
 ["cargo","test","--offline","--workspace","--lib"],
 ["cargo","clippy","--offline","-p","blobin-showcase","--lib","--bin","blobin-showcase","--","-D","warnings"],
 ["cargo","build","--offline","-p","blobin-showcase","--bin","blobin-showcase"],
 [sys.executable,"-m","py_compile","scripts/blob_ac05_private_preflight.py",
  "scripts/blob_ac05_qualify_capture.py","scripts/blob_ac05_revalidate.py",
  "scripts/blob_ac05_verify.py"],
 [sys.executable,"scripts/blob_ac05_revalidate.py","--evidence",
  "evidence/runs/blob-ac05-20261012/qualified"],
 ["git","diff","--check"],
]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def git(*args):
 return subprocess.run(["git",*args],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
def run(n,argv):
 p=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=180)
 out=OUT/f"gate-{n:02d}.stdout.txt";err=OUT/f"gate-{n:02d}.stderr.txt"
 out.write_text(p.stdout.rstrip("\n")+("\n" if p.stdout else ""))
 err.write_text(p.stderr.rstrip("\n")+("\n" if p.stderr else ""))
 print(f"AC05-G{n:02d} {'PASS' if p.returncode==0 else 'HOLD'}",flush=True)
 return {
  "argv":argv,"exit_code":p.returncode,
  "stdout":str(out.relative_to(ROOT)),"stderr":str(err.relative_to(ROOT)),
  "stdout_sha256":sha(out),"stderr_sha256":sha(err)}
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 ledger={
  "contract":"BLOB-AC-05","utc":datetime.now(timezone.utc).isoformat(),
  "branch":git("branch","--show-current"),"baseline":git("rev-parse","HEAD"),
  "origin":git("remote","get-url","origin"),
  "source_sha256":{p:sha(ROOT/p) for p in SOURCES},
  "method":"offline regression and independent revalidation of previously executed genuine private Weston production CPU-renderd capture",
  "e2e_capture":"SCOPED PASS subject to independent saved oracle",
  "new_automated_isolated_replay":"HOLD (namespace check / environment execution restriction)",
  "renderer":"real blobin_renderd CPU backend; CPU_LOCAL_PREVIEW_NOT_GPU_QUALIFIED",
  "compositor_presentation_feedback":False,"physical_hid":False,
  "cp03_hybrid60":"NOT_PASS",
  "commands":[]
 }
 ok=ledger["branch"]=="main" and ledger["origin"]=="https://github.com/tension-atoi/blob.in-showcase.git"
 for i,argv in enumerate(COMMANDS,1):
  result=run(i,argv);ledger["commands"].append(result)
  if result["exit_code"]:
   ok=False
   break
 if ok:
  with tempfile.TemporaryDirectory(prefix="blob-ac05-module-") as td:
   target=Path(td)/"blob_ac05_weston_test_input.so"
   flags=subprocess.run(["pkg-config","--cflags","libweston-15"],cwd=ROOT,capture_output=True,text=True,check=True)
   libs=subprocess.run(["pkg-config","--libs","libweston-15"],cwd=ROOT,capture_output=True,text=True,check=True)
   argv=["cc","-std=gnu11","-Wall","-Wextra","-Werror","-shared","-fPIC","-O2",
         *shlex.split(flags.stdout),"scripts/blob_ac05_weston_test_input.c",
         "-o",str(target),*shlex.split(libs.stdout)]
   result=run(9,argv);ledger["commands"].append(result)
   if result["exit_code"]==0:ledger["test_module_sha256"]=sha(target)
   else:ok=False
 witness=OUT/"qualified/capture-qualification.json"
 if witness.exists():
  captured=json.loads(witness.read_text())
  ledger["captured_run_verdict"]=captured["verdict"]
  ledger["captured_run_receipt_sha256"]=sha(witness)
  ledger["captured_run_frames"]=captured.get("source_frames")
  ledger["captured_run_commits"]=captured.get("semantic_commits")
  ok=ok and captured["verdict"]=="SCOPED_PASS_EXISTING_PRIVATE_WESTON_REAL_CPU_SDF_PIXELS"
 else:ok=False
 ledger["result"]="SCOPED_PASS_SAVED_REAL_CPU_SDF_E2E_OFFLINE_REVALIDATED_LIVE_REPLAY_HOLD" if ok else "HOLD"
 (OUT/"qualification.json").write_text(json.dumps(ledger,indent=2,ensure_ascii=False)+"\n")
 print("BLOB_AC05_"+ledger["result"],flush=True)
 return 0 if ok else 1
if __name__=="__main__":
 sys.exit(main())
