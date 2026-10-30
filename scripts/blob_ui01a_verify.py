#!/usr/bin/env python3
"""BLOB-UI-RUNTIME-01A: locally reproducible first-party native UI adoption.
Runs offline Rust checks then private Weston + real CPU SDF + GPU pixel oracle.
No active-desktop input, network server, SDF kernel edits or GitHub Actions.
"""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,os,shlex,subprocess,sys,tempfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"evidence/runs/blob-ui-runtime-01a-20261012"
SOURCES=[
 "contracts/BLOB-UI-RUNTIME-01_Contrat_de_travail_2026-10-12.md",
 "contracts/BLOB-UI-RUNTIME-01-AVENANT-RATIFICATION-20261012.md",
 "docs/BLOB-UI-RUNTIME-01A-QUALIFICATION-20261012.md",
 "docs/BLOB-UI-RUNTIME-01A-BASELINE-20261012.md",
 "docs/PROGRAM-INTEGRATION-SPINE-20261012.md",
 "Cargo.toml","Cargo.lock","crates/showcase/Cargo.toml",
 "crates/blobin-ui-scene/Cargo.toml","crates/blobin-ui-scene/src/lib.rs",
 "crates/showcase/src/ac01a_toggle.rs","crates/showcase/src/ac01a_native_gpu.rs",
 "crates/showcase/src/app.rs","crates/showcase/src/lib.rs",
 "scripts/blob_ui01a_native_smoke.py","scripts/blob_ui01a_test_input.c",
 "scripts/blob_ui01a_oracle.py","scripts/blob_ui01a_verify.py",
]
COMMANDS=[
 ["rustfmt","--edition","2021","--check",
  "crates/blobin-ui-scene/src/lib.rs","crates/showcase/src/ac01a_toggle.rs",
  "crates/showcase/src/ac01a_native_gpu.rs"],
 ["cargo","tree","--offline","-p","blobin-ui-scene"],
 ["cargo","test","--offline","-p","blobin-ui-scene","--all-targets"],
 ["cargo","test","--offline","-p","blobin-showcase","--lib","ac01a_toggle"],
 ["cargo","test","--offline","-p","blobin-showcase","--lib",
  "ui01a_egui_entire_label_and_thumb_both_activate_once"],
 ["cargo","test","--offline","--workspace","--lib"],
 ["cargo","clippy","--offline","-p","blobin-ui-scene","--all-targets","--","-D","warnings"],
 ["cargo","clippy","--offline","-p","blobin-showcase","--lib","--bin","blobin-showcase","--","-D","warnings"],
 ["cargo","build","--offline","-p","blobin-showcase","--bin","blobin-showcase"],
 ["git","diff","--check"],
]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def raw_sha(data):return hashlib.sha256(data).hexdigest()
def git(*args):return subprocess.run(["git",*args],cwd=ROOT,
                                   capture_output=True,text=True,check=True).stdout.strip()
def step(index:int,argv:list[str],timeout:int=180)->dict:
    process=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
    stdout=OUT/f"gate-{index:02d}.stdout.txt"
    stderr=OUT/f"gate-{index:02d}.stderr.txt"
    stdout.write_text(process.stdout.rstrip("\n")+("\n" if process.stdout else ""))
    stderr.write_text(process.stderr.rstrip("\n")+("\n" if process.stderr else ""))
    record={"argv":argv,"exit_code":process.returncode,
      "stdout":str(stdout.relative_to(ROOT)),"stdout_sha256":sha(stdout),
      "stderr":str(stderr.relative_to(ROOT)),"stderr_sha256":sha(stderr)}
    print(f"UI01A gate-{index:02d} {'PASS' if not process.returncode else 'HOLD'}: {' '.join(argv)}",flush=True)
    return record
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    dirty="crates/showcase/src/bin/blobin_ui_g04b_wayland.rs"
    preexist_diff=git("diff","HEAD","--",dirty)
    ledger={
        "mandate":"BLOB-UI-RUNTIME-01A",
        "utc":datetime.now(timezone.utc).isoformat(),
        "branch":git("branch","--show-current"),
        "baseline_sha":git("rev-parse","HEAD"),
        "remote":git("remote","get-url","origin"),
        "dirty_g04b_before_sha256":raw_sha(preexist_diff.encode()),
        "source_sha256":{name:sha(ROOT/name) for name in SOURCES},
        "renderer_authority":"existing true blobin_renderd CPU; no code changed",
        "ui_scene":"first-party blobin-ui-scene G02/G03 display-list",
        "input_owner":"egui pointer/focus/button, no second InputRouter",
        "gpu_surface_owner":"existing showcase Gfx wgpu",
        "text_owner":"egui until future G-TEXT",
        "compositor_presentation_feedback":False,
        "physical_hid":False,
        "cp03_hybrid60":"NOT_PASS",
        "p1_complete":False,
        "commands":[],
    }
    good=(ledger["branch"]=="main" and
          ledger["remote"]=="https://github.com/tension-atoi/blob.in-showcase.git")
    for i,argv in enumerate(COMMANDS,1):
        result=step(i,argv)
        ledger["commands"].append(result)
        if result["exit_code"]!=0:
            good=False;break
        if i==2:
            out=(OUT/"gate-02.stdout.txt").read_text()
            if "blobin-ui-core" not in out or any(word in out.lower() for word in ("egui","wgpu","wayland","gpui")):
                ledger["dependency_barrier"]="HOLD"
                good=False;break
            ledger["dependency_barrier"]="PASS: core only, no renderer or egui dependencies"
    if good:
        with tempfile.TemporaryDirectory(prefix="blob-ui01a-live-") as work:
            private=Path(work)
            module=private/"01a-weston-test-input.so"
            flags=subprocess.run(["pkg-config","--cflags","libweston-15"],capture_output=True,text=True,check=True)
            libs=subprocess.run(["pkg-config","--libs","libweston-15"],capture_output=True,text=True,check=True)
            argv=["cc","-std=gnu11","-Wall","-Wextra","-Werror","-shared","-fPIC","-O2",
                  *shlex.split(flags.stdout),"scripts/blob_ui01a_test_input.c",
                  "-o",str(module),*shlex.split(libs.stdout)]
            result=step(11,argv)
            ledger["commands"].append(result)
            if result["exit_code"]!=0:good=False
            else:
                ledger["weston_input_plugin_sha256"]=sha(module)
                source=private/"private-weston-run"
                argv=[sys.executable,"scripts/blob_ui01a_native_smoke.py",
                      "--module",str(module),"--out",str(source)]
                result=step(12,argv,60)
                ledger["commands"].append(result)
                if result["exit_code"]!=0:good=False
                else:
                    argv=[sys.executable,"scripts/blob_ui01a_oracle.py",
                          "--source",str(source),"--destination",str(OUT/"native")]
                    result=step(13,argv,30)
                    ledger["commands"].append(result)
                    if result["exit_code"]!=0:good=False
    if good:
        native=OUT/"native"
        for index,extra in [(14,[]),(15,["--negative-test"]),(16,["--negative-png"])]:
            argv=[sys.executable,"scripts/blob_ui01a_oracle.py","--source",str(native),*extra]
            result=step(index,argv,30)
            ledger["commands"].append(result)
            if result["exit_code"]!=0:good=False;break
        if good:
            witness=json.loads((native/"native-qualification.json").read_text())
            good=(witness["verdict"]=="SCOPED_PASS_REAL_EDITOR_NATIVE_TOGGLE_CLIENT_GPU_PIXELS"
              and witness["sdf_request_count"]==1 and witness["sdf_frame_count"]==1
              and witness["g02_ui_revisions"]==[1,2]
              and witness["control_changed_channel_bytes"]>1000)
            ledger["native_witness"]=witness
            ledger["native_receipt_sha256"]=sha(native/"native-qualification.json")
    post_diff=git("diff","HEAD","--",dirty)
    ledger["dirty_g04b_after_sha256"]=raw_sha(post_diff.encode())
    ledger["concurrent_dirty_preserved"]=post_diff==preexist_diff
    good=good and ledger["concurrent_dirty_preserved"]
    ledger["verdict"]="SCOPED_PASS_NATIVE_EDITOR_UI_TO_SWAPCHAIN" if good else "HOLD"
    (OUT/"qualification.json").write_text(json.dumps(ledger,indent=2,ensure_ascii=False)+"\n")
    print("BLOB_UI_RUNTIME_01A_"+ledger["verdict"],flush=True)
    return 0 if good else 1
if __name__=="__main__":
    sys.exit(main())
