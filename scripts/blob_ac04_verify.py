#!/usr/bin/env python3
"""BLOB-AC-04: scoped offline verification of the actual production egui canvas.
Never injects host input or substitutes the GPU/SDF renderer.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"evidence/runs/blob-ac04-20261012"
SOURCES=[
 "contracts/BLOB-AC-04-PRODUCTION-UI-ADOPTION-20261012.md",
 "docs/BLOB-AC-04-PRODUCTION-UI-QUALIFICATION-20261012.md",
 "docs/PROGRAM-INTEGRATION-SPINE-20261012.md",
 "crates/showcase/src/ac04_scene_gestures.rs",
 "crates/showcase/src/app.rs",
 "crates/showcase/src/lib.rs",
 "scripts/blob_ac04_verify.py",
]
COMMANDS=[
 ["rustfmt","--edition","2021","--check","crates/showcase/src/ac04_scene_gestures.rs"],
 ["cargo","test","--offline","-p","blobin-showcase","--lib","ac04_scene_gestures"],
 ["cargo","test","--offline","-p","blobin-showcase","--lib","ac04_production_input_tests"],
 ["cargo","clippy","--offline","-p","blobin-showcase","--lib","--bin","blobin-showcase","--","-D","warnings"],
 ["cargo","test","--offline","-p","blobin-showcase","--lib"],
 ["cargo","test","--offline","--workspace","--lib"],
 ["cargo","build","--offline","-p","blobin-showcase","--bin","blobin-showcase"],
 ["git","diff","--check"],
]
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def git(*args):
    return subprocess.run(["git",*args],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    receipt={
        "contract":"BLOB-AC-04",
        "date_utc":datetime.now(timezone.utc).isoformat(),
        "repo":"tension-atoi/blob.in-showcase",
        "branch":git("branch","--show-current"),
        "baseline":git("rev-parse","HEAD"),
        "origin":git("remote","get-url","origin"),
        "source_sha256":{p:sha(ROOT/p) for p in SOURCES},
        "method":"headless actual-egui Context.run_ui input events, model tests, production offline build, no compositor/oracle claim",
        "source_license":"First-party local Rust only; no ArtCraft imported",
        "renderer_owner":"BLOB-FRAME-v1 remote runtime (unchanged)",
        "physical_input":"NOT_TESTED",
        "production_compositor_e2e":"NOT_TESTED",
        "compositor_present_feedback":False,
        "cp03_hybrid60":"NOT_PASS",
        "commands":[],
    }
    ok=receipt["branch"]=="main" and receipt["origin"]=="https://github.com/tension-atoi/blob.in-showcase.git"
    for n,argv in enumerate(COMMANDS,1):
        proc=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=180)
        sout=OUT/f"gate-{n:02d}.stdout.txt"
        serr=OUT/f"gate-{n:02d}.stderr.txt"
        sout.write_text(proc.stdout.rstrip("\n")+("\n" if proc.stdout else ""),encoding="utf-8")
        serr.write_text(proc.stderr.rstrip("\n")+("\n" if proc.stderr else ""),encoding="utf-8")
        receipt["commands"].append({
            "argv":argv,"exit_code":proc.returncode,
            "stdout":str(sout.relative_to(ROOT)),"stdout_sha256":sha(sout),
            "stderr":str(serr.relative_to(ROOT)),"stderr_sha256":sha(serr)
        })
        print(f"AC04-G{n:02}: {'PASS' if proc.returncode==0 else 'HOLD'} — {' '.join(argv)}",flush=True)
        if proc.returncode:
            ok=False
            break
    # An ACTUAL integration test must execute through the production UI's
    # egui callbacks, not merely use the isolated transactions module.
    egui_log=OUT/"gate-03.stdout.txt"
    if not egui_log.exists() or "4 passed; 0 failed" not in egui_log.read_text():
        receipt["egui_oracle"]="HOLD"
        ok=False
    else:
        receipt["egui_oracle"]="4/4 PASS (production ui_root + actual egui events)"
    receipt["result"]="SCOPED_PASS_PRODUCTION_EGUI_NO_COMPOSITOR_E2E" if ok else "HOLD"
    (OUT/"qualification.json").write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("BLOB_AC04_"+receipt["result"],flush=True)
    return 0 if ok else 1
if __name__=="__main__":
    sys.exit(main())
