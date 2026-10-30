#!/usr/bin/env python3
"""Fail-closed timing falsifications in private ephemeral copies."""
import json,shutil,tempfile
from pathlib import Path
from qchain_cpja7h_analyze import analyze
from qchain_cpja7h_independent_oracle import verify
ROOT=Path("/mnt/workbench/evidence/runs/qchain-cpja7h-20261012-01")
REF=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
RECEIPT=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-replay-reconciliation.json")
BASE=ROOT/"runs/baseline-33ms"
def reject(name,fn):
    try:fn()
    except (AssertionError,ValueError,RuntimeError,KeyError) as e:
        print("CPJA7H_ADVERSARY_REJECTED",name,str(e)[:60],flush=True)
        return
    raise AssertionError("FALSELY_ACCEPTED_"+name)
def modify(path,term,substitute=None):
    lines=path.read_text(errors="replace").splitlines()
    for i,line in enumerate(lines):
        if term in line:
            if substitute is None:lines.pop(i)
            else:lines[i]=substitute(line)
            path.write_text("\n".join(lines)+"\n")
            return
    raise AssertionError("MUTATION_SOURCE_MISSING_"+term)
def copy_evidence(root):
    for name in ("source.stdout","viewer.stdout","viewer.stderr",
                 "weston.stdout","weston-timeline-proto.log"):
        shutil.copy2(BASE/name,root/name)
    (root/"engine-ledger").mkdir()
    shutil.copy2(BASE/"engine-ledger/engine.stderr",
                 root/"engine-ledger/engine.stderr")
    for p in BASE.glob("sample-*.png"):(root/p.name).symlink_to(p)
def attack(name,mutation,oracle):
    with tempfile.TemporaryDirectory(prefix="cpja7h-attack-") as d:
        root=Path(d)
        copy_evidence(root)
        mutation(root)
        if oracle=="stage":reject(name,lambda:analyze(root))
        else:reject(name,lambda:verify(root,REF,RECEIPT))
def main():
    assert analyze(BASE)["frames"]==1200
    assert verify(BASE,REF,RECEIPT)["source_frames"]==1200
    attack("missing_compute_timing",
       lambda p:modify(p/"engine-ledger/engine.stderr",
                       "CPJA7H_ENGINE_TIMING seq=15 "), "stage")
    attack("duplicate_broker_timing",
       lambda p:(p/"source.stdout").open("a").write(
         "CPJA7H_BROKER_TIMING seq=0 pipe_read_us=1 canonical_verify_us=1 memfd_seal_us=1 memfd_send_us=1\n"),"stage")
    attack("invalid_negative_gpu_timing",
       lambda p:modify(p/"engine-ledger/engine.stderr",
         "CPJA7H_ENGINE_TIMING seq=19 ",
         lambda x:x.replace("compute_readback_host_us=",
                             "compute_readback_host_us=-1")),"stage")
    attack("tampered_texture_upload",
       lambda p:modify(p/"viewer.stdout",
        "CPJA7H_VIEWER_TIMING seq=29 ",
        lambda x:x.replace("texture_upload_api_us=",
                           "texture_upload_api_us=999999999 ")),"stage")
    attack("missing_client_ipc",
       lambda p:modify(p/"viewer.stdout",
                       "CPJA7H_CLIENT_TIMING seq=66 "), "stage")
    attack("missing_vk_wait",
       lambda p:modify(p/"viewer.stderr",
         "CPJA7DB_WORKER_WAIT_SUCCESS generation=1 present_id=7"),"wsi")
    attack("missing_weston_feedback",
       lambda p:modify(p/"weston-timeline-proto.log",
         ".presented("),"wsi")
    attack("forged_frame_hash",
       lambda p:modify(p/"viewer.stdout",
         "CPI02_WGPU_PRESENT_SUBMITTED seq=55 ",
         lambda x:x.replace("rgba_sha256=",
                   "rgba_sha256="+("0"*64)+" forged=")),"wsi")
    attack("lost_compute_session_summary",
       lambda p:modify(p/"engine-ledger/engine.stderr",
         "CPJA7G_GPU_STREAM_COMPLETE"),"wsi")
    print("CPJA7H_ADVERSARIAL_9_OF_9_PASS",flush=True)
if __name__=="__main__":main()
