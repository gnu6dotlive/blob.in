#!/usr/bin/env python3
"""Negative preflight gate. Refuses to overwrite proof and never writes canonical inputs."""
from pathlib import Path
import hashlib, json, subprocess, sys
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def need(ok,reason):
 if not ok:raise RuntimeError(reason)
def main():
 if len(sys.argv)!=7:
  raise SystemExit("usage: receipt_fault_gate SOURCE RAW MANIFEST COMPUTE_LOG CPU_RECEIPT EMPTY_PROOF_ROOT")
 source,raw,manifest,log,receipt,root=map(Path,sys.argv[1:])
 need(root.is_dir() and not any(root.iterdir()),"EVIDENCE_ROOT_NOT_EMPTY")
 need(all(x.is_file() for x in (source,manifest,log,receipt)),"INPUT_ABSENT")
 cases=[]
 for case,input_path in (("bad-compute-log",log),("bad-cpu-receipt",receipt)):
  modified=input_path.read_bytes()+b"\nCPH_FAULT_ONE_BYTE\n"
  changed=root/f"{case}.input"
  changed.write_bytes(modified)
  process=subprocess.run([
    str(source),str(raw),str(manifest),
    str(changed if case=="bad-compute-log" else log),
    str(changed if case=="bad-cpu-receipt" else receipt),
    str(root/f"{case}.sock")],capture_output=True,timeout=8)
  (root/f"{case}.stderr").write_bytes(process.stderr)
  (root/f"{case}.stdout").write_bytes(process.stdout)
  expected=("GPU_COMPUTE_RECEIPT_MISMATCH" if case=="bad-compute-log"
    else "GPU_CPU_RECEIPT_HASH_MISMATCH")
  need(process.returncode!=0 and expected.encode() in process.stderr,
      "RECEIPT_FAULT_NOT_REJECTED_"+case)
  need(not (root/f"{case}.sock").exists(),"SOCKET_CREATED_BEFORE_RECEIPT_VALIDATION")
  cases.append({"id":case,"expected_error":expected,"observed_exit":process.returncode,
    "rejected_before_socket":True,"mutated_sha256":sha(changed)})

 verdict={"schema":"gnu6.qchain.cph_receipt_negative_gate.v1",
   "verdict":"QCHAIN_GPU_SOURCE_RECEIPTS_FAIL_CLOSED_PASS",
   "source_read_only":True,"canonical_receipts_unchanged":True,
   "negative_cases":cases,"positive_case_covered_by":"recovery_gate"}
 result=root/"result.json"
 need(not result.exists(),"REFUSE_OVERWRITE")
 result.write_text(json.dumps(verdict,indent=2)+"\n")
 print(verdict["verdict"],"negative_cases",len(cases))
if __name__=="__main__": main()
