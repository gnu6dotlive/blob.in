#!/usr/bin/env python3
"""BLOB-UI-RUNTIME-01E: native composition/gpu stress gates + fresh 01A/B/C E2E.
No background work, host-desktop pointer events, CI workflows, or external vendoring.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,shlex,subprocess,sys,tempfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"evidence/runs/blob-ui-runtime-01e-20261012"
FILES=[
"contracts/BLOB-UI-RUNTIME-01E-CONTRAT-20261012.md",
"docs/BLOB-UI-RUNTIME-01E-QUALIFICATION-20261012.md",
"docs/PROGRAM-INTEGRATION-SPINE-20261012.md",
"crates/blobin-ui-scene/src/lib.rs",
"crates/blobin-ui-scene/src/composition.rs",
"crates/blobin-ui-scene/src/strokes.rs",
"crates/showcase/src/ac01e_stroke_stress.rs",
"crates/showcase/src/ac01a_native_gpu.rs",
"crates/showcase/src/app.rs",
"crates/showcase/src/lib.rs",
"scripts/blob_ui01e_native_smoke.py",
"scripts/blob_ui01e_test_input.c",
"scripts/blob_ui01e_oracle.py",
"scripts/blob_ui01e_verify.py",
]
CONCURRENT=[
"crates/showcase/src/bin/blobin_ui_g04b_wayland.rs",
"docs/BLOB-UI-G04B-HYPRLAND-COMPOSITOR-INPUT-E2E-20261012.md",
"scripts/blobin_ui_g04b_hyprland_oracle.py",
]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def git(*parts):return subprocess.run(["git",*parts],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()
def concurrent_snapshot():
    files={}
    for name in CONCURRENT:
        path=ROOT/name
        files[name]=sha(path) if path.is_file() else None
    for p in (ROOT/"evidence/runs/blob-ui-g04b-hyprland-20261012").rglob("*"):
        if p.is_file():files[str(p.relative_to(ROOT))]=sha(p)
    files["git_tracked_g04b_diff"]=hashlib.sha256(
        git("diff","HEAD","--","crates/showcase/src/bin/blobin_ui_g04b_wayland.rs").encode()
    ).hexdigest()
    return files
def run(n,argv,timeout=150):
    try:result=subprocess.run(argv,cwd=ROOT,stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,text=True,timeout=timeout)
    except subprocess.TimeoutExpired as e:
        result=subprocess.CompletedProcess(argv,124,
            (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout,bytes) else (e.stdout or ""),
            (e.stderr or b"").decode(errors="replace") if isinstance(e.stderr,bytes) else (e.stderr or "TIMEOUT"))
    stdout=OUT/f"gate-{n:02d}.stdout.txt"
    stderr=OUT/f"gate-{n:02d}.stderr.txt"
    stdout.write_text(result.stdout or "",encoding="utf8")
    stderr.write_text(result.stderr or "",encoding="utf8")
    print(f"UI01E-G{n:02d} {'PASS' if result.returncode==0 else 'HOLD'}",flush=True)
    return {"command":[str(x) for x in argv],"exit_code":result.returncode,
            "stdout_file":str(stdout.relative_to(ROOT)),"stdout_sha256":sha(stdout),
            "stderr_file":str(stderr.relative_to(ROOT)),"stderr_sha256":sha(stderr)}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    initial=concurrent_snapshot()
    receipt={
       "contract":"BLOB-UI-RUNTIME-01E",
       "utc":datetime.now(timezone.utc).isoformat(),
       "baseline_head":git("rev-parse","HEAD"),
       "branch":git("branch","--show-current"),
       "origin":git("remote","get-url","origin"),
       "source_sha256":{f:sha(ROOT/f) for f in FILES},
       "native_gpu_scene":"3 real product G02 controls + 55 private-test-only rects",
       "native_compositor":"private Weston under user/network namespace",
       "sdf_engine":"real blobin_renderd CPU",
       "presentation_feedback_qualified":False,
       "real_60_fps_qualified":False,
       "cp03_hybrid60":"NOT_PASS",
       "full_native_runtime":"OPEN",
       "g04b_h_snapshot_before":initial,
       "commands":[]
    }
    good=receipt["branch"]=="main" and receipt["origin"]=="https://github.com/tension-atoi/blob.in-showcase.git"
    commands=[
      ["rustfmt","--edition","2021","--check",
       "crates/blobin-ui-scene/src/lib.rs","crates/blobin-ui-scene/src/composition.rs",
"crates/blobin-ui-scene/src/strokes.rs",
       "crates/showcase/src/ac01e_stroke_stress.rs"],
      ["cargo","tree","--offline","-p","blobin-ui-scene"],
      ["cargo","test","--offline","-p","blobin-ui-scene","--all-targets"],
      ["cargo","test","--offline","-p","blobin-showcase","--lib","ac01e_stroke_stress"],
      ["cargo","test","--offline","-p","blobin-showcase","--lib","ac04_production_input_tests"],
      ["cargo","test","--offline","--workspace","--lib"],
      ["cargo","clippy","--offline","-p","blobin-ui-scene","--all-targets","--","-D","warnings"],
      ["cargo","clippy","--offline","-p","blobin-showcase","--lib","--bin","blobin-showcase","--","-D","warnings"],
      ["cargo","build","--offline","-p","blobin-showcase","--bin","blobin-showcase"],
      [sys.executable,"scripts/blob_ui01e_oracle.py","--source",str(OUT/"native")],
      [sys.executable,"scripts/blob_ui01e_oracle.py","--source",str(OUT/"native"),"--negative","trace"],
      [sys.executable,"scripts/blob_ui01e_oracle.py","--source",str(OUT/"native"),"--negative","png"],
      [sys.executable,"scripts/blob_ui01c_oracle.py","--source",
       "evidence/runs/blob-ui-runtime-01c-20261012/native"],
      [sys.executable,"scripts/blob_ui01b_oracle.py","--source",
       "evidence/runs/blob-ui-runtime-01b-20261012/native"],
      [sys.executable,"scripts/blob_ui01a_oracle.py","--source",
       "evidence/runs/blob-ui-runtime-01a-20261012/native"],
      ["git","diff","--check"],
    ]
    for i,cmd in enumerate(commands,1):
        step=run(i,cmd)
        receipt["commands"].append(step)
        if step["exit_code"]!=0:good=False;break
        if i==2:
            deps=(OUT/"gate-02.stdout.txt").read_text().lower()
            if "blobin-ui-core" not in deps or any(d in deps for d in ("egui","wgpu","wayland","gpui")):
                good=False
                receipt["dependency_barrier"]="HOLD"
                break
            receipt["dependency_barrier"]="PASS: core-only scene"
    if good:
        flags=shlex.split(subprocess.check_output(["pkg-config","--cflags","libweston-15"],text=True))
        libs=shlex.split(subprocess.check_output(["pkg-config","--libs","libweston-15"],text=True))
        with tempfile.TemporaryDirectory(prefix="ui01e-fresh-weston-") as folder:
            temp=Path(folder)
            scenarios=[
                ("01e","scripts/blob_ui01e_test_input.c","scripts/blob_ui01e_native_smoke.py","scripts/blob_ui01e_oracle.py"),
                ("01d","scripts/blob_ui01d_test_input.c","scripts/blob_ui01d_native_smoke.py","scripts/blob_ui01d_oracle.py"),
                ("01c","scripts/blob_ui01c_test_input.c","scripts/blob_ui01c_native_smoke.py","scripts/blob_ui01c_oracle.py"),
                ("01b","scripts/blob_ui01b_test_input.c","scripts/blob_ui01b_native_smoke.py","scripts/blob_ui01b_oracle.py"),
                ("01a","scripts/blob_ui01a_test_input.c","scripts/blob_ui01a_native_smoke.py","scripts/blob_ui01a_oracle.py"),
            ]
            next_gate=17
            for label,source,smoke,oracle in scenarios:
                mod=temp/(label+".so")
                start=run(next_gate,["cc","-std=gnu11","-Wall","-Wextra","-Werror",
                     "-shared","-fPIC","-O2",*flags,source,"-o",str(mod),*libs],40)
                receipt["commands"].append(start)
                if start["exit_code"]!=0:good=False;break
                raw=temp/label
                start=run(next_gate+1,[sys.executable,smoke,"--module",str(mod),"--out",str(raw)],70)
                receipt["commands"].append(start)
                if start["exit_code"]!=0:good=False;break
                start=run(next_gate+2,[sys.executable,oracle,"--source",str(raw)],35)
                receipt["commands"].append(start)
                if start["exit_code"]!=0:good=False;break
                receipt[label+"_fresh_native_replay"]="PASS"
                next_gate+=3
    receipt["g04b_h_snapshot_after"]=concurrent_snapshot()
    receipt["g04b_h_preserved"]=receipt["g04b_h_snapshot_after"]==initial
    good=good and receipt["g04b_h_preserved"]
    if good:
        native=json.loads((OUT/"native/native-qualification.json").read_text())
        good=native["verdict"]=="SCOPED_PASS_REAL_WGPU_64_COMMAND_VECTOR_SCENE" and native["verified_stress_shape_pixels"]==51 and native["verified_stroke_center_pixels"]==4
        receipt["native_stress_witness_sha256"]=sha(OUT/"native/native-qualification.json")
        receipt["native_observed_commands"]=native["gpu_draw_commands"]
        receipt["native_observed_layers"]=native["composed_layers"]
        receipt["native_gpu_pixel_sha256"]=native["original_gpu_rgba_sha256"]
        receipt["first_party_01a_01b_01c_01d_fresh_replayed"]=True
    receipt["verdict"]="SCOPED_PASS_NATIVE_VECTOR_STROKES_64_COMMANDS" if good else "HOLD"
    (OUT/"qualification.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print("BLOB_UI_RUNTIME_01E_"+receipt["verdict"],flush=True)
    return 0 if good else 1
if __name__=="__main__":raise SystemExit(main())
