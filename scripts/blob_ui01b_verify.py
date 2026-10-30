#!/usr/bin/env python3
"""BLOB-UI-RUNTIME-01B: reproducible private Weston+renderer CPU and GPU-client pixel gates.
Only first-party source; preserves G04B/H unpublished files on canonical main.
"""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,shlex,subprocess,sys,tempfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"evidence/runs/blob-ui-runtime-01b-20261012"
SOURCES=[
 "contracts/BLOB-UI-RUNTIME-01B-CONTRAT-20261012.md",
 "docs/BLOB-UI-RUNTIME-01B-QUALIFICATION-20261012.md",
 "docs/PROGRAM-INTEGRATION-SPINE-20261012.md",
 "crates/blobin-ui-scene/src/lib.rs",
 "crates/showcase/src/ac01a_native_gpu.rs",
 "crates/showcase/src/ac01a_toggle.rs",
 "crates/showcase/src/ac01b_action.rs",
 "crates/showcase/src/ac01b_control_layout.rs",
 "crates/showcase/src/app.rs","crates/showcase/src/lib.rs",
 "scripts/blob_ui01a_native_smoke.py",
 "scripts/blob_ui01b_native_smoke.py",
 "scripts/blob_ui01b_test_input.c",
 "scripts/blob_ui01b_oracle.py","scripts/blob_ui01b_verify.py",
]
COMMANDS=[
 ["rustfmt","--edition","2021","--check",
  "crates/blobin-ui-scene/src/lib.rs","crates/showcase/src/ac01a_native_gpu.rs",
  "crates/showcase/src/ac01a_toggle.rs","crates/showcase/src/ac01b_action.rs",
  "crates/showcase/src/ac01b_control_layout.rs"],
 ["cargo","tree","--offline","-p","blobin-ui-scene"],
 ["cargo","test","--offline","-p","blobin-ui-scene","--all-targets"],
 ["cargo","test","--offline","-p","blobin-showcase","--lib","ac01b_control_layout"],
 ["cargo","test","--offline","-p","blobin-showcase","--lib","ac01b_action"],
 ["cargo","test","--offline","-p","blobin-showcase","--lib","ac01a_toggle"],
 ["cargo","test","--offline","-p","blobin-showcase","--lib","ui01b_egui_real_distance_action_then_toggle_separate_authorities"],
 ["cargo","test","--offline","-p","blobin-showcase","--lib","ui01a_egui_entire_label_and_thumb_both_activate_once"],
 ["cargo","test","--offline","--workspace","--lib"],
 ["cargo","clippy","--offline","-p","blobin-ui-scene","--all-targets","--","-D","warnings"],
 ["cargo","clippy","--offline","-p","blobin-showcase","--lib","--bin","blobin-showcase","--","-D","warnings"],
 ["cargo","build","--offline","-p","blobin-showcase","--bin","blobin-showcase"],
 [sys.executable,"scripts/blob_ui01a_oracle.py","--source",
  "evidence/runs/blob-ui-runtime-01a-20261012/native"],
 ["git","diff","--check"],
]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def hashlib_text(s):return hashlib.sha256(s.encode()).hexdigest()
def git(*cmd):
 return subprocess.run(["git",*cmd],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
def step(index,cmd,timeout=180):
 try:
  p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
 except subprocess.TimeoutExpired as e:
  p=subprocess.CompletedProcess(cmd,124,e.stdout.decode(errors="replace") if isinstance(e.stdout,bytes) else (e.stdout or ""),
     e.stderr.decode(errors="replace") if isinstance(e.stderr,bytes) else (e.stderr or "TIMEOUT"))
 out=OUT/f"gate-{index:02d}.stdout.txt"
 err=OUT/f"gate-{index:02d}.stderr.txt"
 out.write_text(p.stdout.rstrip("\n")+("\n" if p.stdout else ""))
 err.write_text(p.stderr.rstrip("\n")+("\n" if p.stderr else ""))
 record={"argv":[str(x) for x in cmd],"exit_code":p.returncode,
  "stdout":str(out.relative_to(ROOT)),"stdout_sha256":sha(out),
  "stderr":str(err.relative_to(ROOT)),"stderr_sha256":sha(err)}
 print(f"UI01B-G{index:02d} {'PASS' if p.returncode==0 else 'HOLD'} - {' '.join(map(str,cmd))}",flush=True)
 return record
def compile_module(number,source,path):
 flags=subprocess.run(["pkg-config","--cflags","libweston-15"],capture_output=True,text=True,check=True)
 libs=subprocess.run(["pkg-config","--libs","libweston-15"],capture_output=True,text=True,check=True)
 return step(number,["cc","-std=gnu11","-Wall","-Wextra","-Werror","-shared","-fPIC","-O2",
   *shlex.split(flags.stdout),source,"-o",str(path),*shlex.split(libs.stdout)])
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 dirty="crates/showcase/src/bin/blobin_ui_g04b_wayland.rs"
 initial=git("diff","HEAD","--",dirty)
 initial_status=git("status","--porcelain")
 record={
  "program":"BLOB-UI-RUNTIME-01B",
  "utc":datetime.now(timezone.utc).isoformat(),
  "baseline":git("rev-parse","HEAD"),
  "branch":git("branch","--show-current"),
  "origin":git("remote","get-url","origin"),
  "source_sha256":{p:sha(ROOT/p) for p in SOURCES},
  "g04b_dirty_before_sha256":hashlib_text(initial),
  "g04b_dirty_paths":[p for p in initial_status.splitlines() if "g04b" in p.lower()],
  "scope":"2 native UI controls, shared G02/G03, one wgpu swapchain and persistent uniform buffer/group",
  "runtime":"actual blobin_renderd CPU through BLOB-FRAME-v1",
  "compositor_present_feedback":False,"physical_hid":False,
  "cp03_hybrid60":"NOT_PASS","p1_complete":False,
  "commands":[],
 }
 valid=record["branch"]=="main" and record["origin"]=="https://github.com/tension-atoi/blob.in-showcase.git"
 for i,command in enumerate(COMMANDS,1):
  a=step(i,command);record["commands"].append(a)
  if a["exit_code"]!=0:valid=False;break
  if i==2:
   deps=(OUT/"gate-02.stdout.txt").read_text().lower()
   if "blobin-ui-core" not in deps or any(x in deps for x in ("egui","wgpu","gpui","wayland")):
    valid=False;record["dependency_barrier"]="HOLD";break
   record["dependency_barrier"]="PASS scene depends only on blobin-ui-core"
 if valid:
  with tempfile.TemporaryDirectory(prefix="blob-ui01b-private-") as tmp:
   work=Path(tmp)
   native_mod=work/"ui01b_weston.so"
   old_mod=work/"ui01a_weston.so"
   a=compile_module(15,"scripts/blob_ui01b_test_input.c",native_mod)
   record["commands"].append(a)
   if a["exit_code"]:valid=False
   else:
    record["native_weston_module_sha256"]=sha(native_mod)
    raw=work/"native"
    a=step(16,[sys.executable,"scripts/blob_ui01b_native_smoke.py",
          "--out",str(raw),"--module",str(native_mod)],70)
    record["commands"].append(a)
    if a["exit_code"]:valid=False
    else:
     a=step(17,[sys.executable,"scripts/blob_ui01b_oracle.py",
          "--source",str(raw),"--destination",str(OUT/"native")],35)
     record["commands"].append(a)
     if a["exit_code"]:valid=False
   if valid:
    a=compile_module(18,"scripts/blob_ui01a_test_input.c",old_mod)
    record["commands"].append(a)
    if a["exit_code"]:valid=False
    else:
     record["legacy_weston_module_sha256"]=sha(old_mod)
     raw_old=work/"legacy01a"
     a=step(19,[sys.executable,"scripts/blob_ui01a_native_smoke.py",
            "--out",str(raw_old),"--module",str(old_mod)],70)
     record["commands"].append(a)
     if a["exit_code"]:valid=False
     else:
      a=step(20,[sys.executable,"scripts/blob_ui01a_oracle.py",
        "--source",str(raw_old),"--destination",str(OUT/"legacy01a")],30)
      record["commands"].append(a)
      if a["exit_code"]:valid=False
 if valid:
  for i,extra in [(21,[]),(22,["--negative","sdf"]),(23,["--negative","png"])]:
   a=step(i,[sys.executable,"scripts/blob_ui01b_oracle.py",
            "--source",str(OUT/"native"),*extra],30)
   record["commands"].append(a)
   if a["exit_code"]!=0:valid=False;break
 if valid:
  result=json.loads((OUT/"native/native-qualification.json").read_text())
  prior=json.loads((OUT/"legacy01a/native-qualification.json").read_text())
  valid=(result["verdict"]=="SCOPED_PASS_01B_REAL_UI_ACTION_AND_RENDERER_CPU_GPU_CLIENT_PIXELS"
    and result["input_releases"]==2 and result["sdf_requests"]==2
    and prior["verdict"]=="SCOPED_PASS_REAL_EDITOR_NATIVE_TOGGLE_CLIENT_GPU_PIXELS")
  record["native_witness"]=result
  record["legacy_01a_witness"]=prior["verdict"]
  record["native_receipt_sha256"]=sha(OUT/"native/native-qualification.json")
  record["legacy_01a_receipt_sha256"]=sha(OUT/"legacy01a/native-qualification.json")
 final=git("diff","HEAD","--",dirty)
 record["g04b_dirty_after_sha256"]=hashlib_text(final)
 record["g04b_preserved"]=initial==final
 valid=valid and record["g04b_preserved"]
 record["verdict"]="SCOPED_PASS_TWO_REAL_NATIVE_COMPONENTS" if valid else "HOLD"
 (OUT/"qualification.json").write_text(json.dumps(record,indent=2,ensure_ascii=False)+"\n")
 print("BLOB_UI_RUNTIME_01B_"+record["verdict"],flush=True)
 return 0 if valid else 1
if __name__=="__main__":
 raise SystemExit(main())
