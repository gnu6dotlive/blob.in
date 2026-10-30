#!/usr/bin/env python3
"""01C integration qualification: real Weston isolated E2E, preserved 01A/01B, no G04B/H writes."""
import hashlib,json,shlex,subprocess,sys,tempfile
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"evidence/runs/blob-ui-runtime-01c-20261012"
SOURCE=[
"contracts/BLOB-UI-RUNTIME-01C-CONTRAT-20261012.md",
"docs/BLOB-UI-RUNTIME-01C-QUALIFICATION-20261012.md",
"docs/PROGRAM-INTEGRATION-SPINE-20261012.md",
"crates/blobin-ui-scene/src/lib.rs",
"crates/showcase/src/ac01b_action.rs",
"crates/showcase/src/ac01c_reset.rs",
"crates/showcase/src/app.rs",
"crates/showcase/src/lib.rs",
"scripts/blob_ui01c_native_smoke.py","scripts/blob_ui01c_test_input.c",
"scripts/blob_ui01c_oracle.py","scripts/blob_ui01c_verify.py",
"scripts/blob_ui01b_native_smoke.py","scripts/blob_ui01a_native_smoke.py",
]
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def git(*a):return subprocess.run(["git",*a],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
def run(i,argv,timeout=110):
 try:r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
 except subprocess.TimeoutExpired:r=subprocess.CompletedProcess(argv,124,"","TIMEOUT")
 a=OUT/f"gate-{i:02d}.stdout.txt";b=OUT/f"gate-{i:02d}.stderr.txt"
 a.write_text(r.stdout or "");b.write_text(r.stderr or "")
 print(f"01C-{i:02d} {'PASS' if r.returncode==0 else 'HOLD'}",flush=True)
 return {"argv":[str(x) for x in argv],"exit_code":r.returncode,
    "stdout_sha256":sha(a),"stderr_sha256":sha(b)}
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 target="crates/showcase/src/bin/blobin_ui_g04b_wayland.rs"
 before=git("diff","HEAD","--",target)
 ledger={"program":"BLOB-UI-RUNTIME-01C","date_utc":datetime.now(timezone.utc).isoformat(),
   "baseline":git("rev-parse","HEAD"),"branch":git("branch","--show-current"),
   "origin":git("remote","get-url","origin"),
   "scope":"3 production UI controls + bounded transforms/clips + one shared GPU pass",
   "source_sha256":{f:sha(ROOT/f) for f in SOURCE},
   "compositor_present_feedback":False,"gpu_sdf_qualified":False,
   "cp03_hybrid60":"NOT_PASS","p1_complete":False,
   "commands":[]}
 valid=ledger["branch"]=="main" and ledger["origin"]=="https://github.com/tension-atoi/blob.in-showcase.git"
 tests=[
 ["rustfmt","--edition","2021","--check","crates/blobin-ui-scene/src/lib.rs",
  "crates/showcase/src/ac01b_action.rs","crates/showcase/src/ac01c_reset.rs"],
 ["cargo","tree","--offline","-p","blobin-ui-scene"],
 ["cargo","test","--offline","-p","blobin-ui-scene","--all-targets"],
 ["cargo","test","--offline","-p","blobin-showcase","--lib","ui01c_reset_real_camera_one_commit_then_idempotent_and_others_survive"],
 ["cargo","test","--offline","--workspace","--lib"],
 ["cargo","clippy","--offline","-p","blobin-ui-scene","--all-targets","--","-D","warnings"],
 ["cargo","clippy","--offline","-p","blobin-showcase","--lib","--bin","blobin-showcase","--","-D","warnings"],
 ["cargo","build","--offline","-p","blobin-showcase","--bin","blobin-showcase"],
 [sys.executable,"scripts/blob_ui01c_oracle.py","--source",str(OUT/"native")],
 [sys.executable,"scripts/blob_ui01c_oracle.py","--source",str(OUT/"native"),"--negative","trace"],
 [sys.executable,"scripts/blob_ui01c_oracle.py","--source",str(OUT/"native"),"--negative","png"],
 [sys.executable,"scripts/blob_ui01b_oracle.py","--source","evidence/runs/blob-ui-runtime-01b-20261012/native"],
 [sys.executable,"scripts/blob_ui01a_oracle.py","--source","evidence/runs/blob-ui-runtime-01a-20261012/native"],
 ["git","diff","--check"]]
 for i,argv in enumerate(tests,1):
  z=run(i,argv);ledger["commands"].append(z)
  if z["exit_code"]!=0:valid=False;break
  if i==2:
   tree=(OUT/"gate-02.stdout.txt").read_text().lower()
   if any(k in tree for k in ("egui","wgpu","gpui","wayland")) or "blobin-ui-core" not in tree:
    valid=False;break
 if valid:
  with tempfile.TemporaryDirectory(prefix="blob-ui01c-probes-") as temp:
   tmp=Path(temp)
   flags=shlex.split(subprocess.check_output(["pkg-config","--cflags","libweston-15"],text=True))
   libs=shlex.split(subprocess.check_output(["pkg-config","--libs","libweston-15"],text=True))
   sources=[("01c","scripts/blob_ui01c_test_input.c","scripts/blob_ui01c_native_smoke.py","scripts/blob_ui01c_oracle.py"),
    ("01b","scripts/blob_ui01b_test_input.c","scripts/blob_ui01b_native_smoke.py","scripts/blob_ui01b_oracle.py"),
    ("01a","scripts/blob_ui01a_test_input.c","scripts/blob_ui01a_native_smoke.py","scripts/blob_ui01a_oracle.py")]
   index=15
   for name,src,smoke,oracle in sources:
    lib=tmp/f"{name}.so"
    z=run(index,["cc","-std=gnu11","-Wall","-Wextra","-Werror","-shared","-fPIC","-O2",
      *flags,src,"-o",str(lib),*libs],30)
    ledger["commands"].append(z)
    if z["exit_code"]:valid=False;break
    raw=tmp/name
    z=run(index+1,[sys.executable,smoke,"--module",str(lib),"--out",str(raw)],65)
    ledger["commands"].append(z)
    if z["exit_code"]:valid=False;break
    # 01a and 01b use backward-compatible layouts while 01c is live.
    z=run(index+2,[sys.executable,oracle,"--source",str(raw)],30)
    ledger["commands"].append(z)
    if z["exit_code"]:valid=False;break
    index+=3
    ledger[name+"_live_replay"]="PASS"
 final=git("diff","HEAD","--",target)
 ledger["g04b_original_sha256"]=hashlib.sha256(before.encode()).hexdigest()
 ledger["g04b_final_sha256"]=hashlib.sha256(final.encode()).hexdigest()
 ledger["g04b_preserved"]=before==final
 valid=valid and ledger["g04b_preserved"]
 if valid:
  result=json.loads((OUT/"native/native-qualification.json").read_text())
  ledger["native_receipt_sha256"]=sha(OUT/"native/native-qualification.json")
  ledger["native_summary"]={key:result[key] for key in (
     "verdict","batched_nodes","batched_draw_commands","semantic_reset_count",
     "pointer_release_count","sdf_requests","sdf_frames","reset_button_changed_channel_bytes")}
 ledger["verdict"]="SCOPED_PASS_THREE_NATIVE_CONTROLS" if valid else "HOLD"
 (OUT/"qualification.json").write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+"\n")
 print("BLOB_UI01C_"+ledger["verdict"],flush=True)
 return 0 if valid else 1
if __name__=="__main__":raise SystemExit(main())
