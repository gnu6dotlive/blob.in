#!/usr/bin/env python3
"""Reconstruct private F4 GPU-copy instrumented sources from a SHA-pinned parent."""
import argparse,hashlib,shutil,subprocess
from pathlib import Path
BASE_SHA="b710306da940f6dd83826bf0da7921ce9739452708ff20d1e000becd54e0ddb7"
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def materialize(baseline,dest,repo):
    if dest.exists():raise RuntimeError("CPJA7K_REFUSE_OVERWRITE_EXISTING_SOURCE")
    original=baseline/"F4/src/gpu_session.rs"
    if digest(original)!=BASE_SHA:
        raise RuntimeError("CPJA7K_PARENT_F4_SOURCE_SHA256_MISMATCH")
    shutil.copytree(baseline,dest)
    patch=repo/"tests/cpja7k/gpu-session-readback-query.patch"
    r=subprocess.run(["patch","--batch","-p0","--input",str(patch)],
        cwd=dest/"F4/src",capture_output=True,text=True,timeout=15)
    if r.returncode!=0:raise RuntimeError("CPJA7K_PATCH_RECONSTRUCTION_FAILED "+r.stderr)
    shutil.copy2(repo/"tests/cpja7k/qchain_cpja7k_f4_source.rs",
                 dest/"F4/src/bin/qchain_cpja7k_f4_source.rs")
    print("CPJA7K_SOURCE_RECONSTRUCTION_PASS",
          "baseline",BASE_SHA,"modified",digest(dest/"F4/src/gpu_session.rs"))
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--baseline",required=True,type=Path)
    p.add_argument("--dest",required=True,type=Path)
    p.add_argument("--repo",type=Path,default=Path(__file__).resolve().parents[1])
    a=p.parse_args()
    materialize(a.baseline.resolve(),a.dest,a.repo.resolve())
if __name__=="__main__":main()
