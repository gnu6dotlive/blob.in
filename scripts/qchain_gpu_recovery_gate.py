#!/usr/bin/env python3
"""Offline external-process fault/restart gate for QCHAIN GPU memfd transport."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(v,reason):
 if not v:raise RuntimeError(reason)
def run_case(case,source,probe,raw,manifest,compute_log,cpu_receipt,root,fail):
 home=root/f"case-{case:02d}"
 home.mkdir(mode=0o700)
 socket=home/"render.sock"
 env=dict(os.environ)
 with (home/"source.log").open("wb") as o,(home/"source.err").open("wb") as e:
  proc=subprocess.Popen([str(source),str(raw),str(manifest),str(compute_log),str(cpu_receipt),str(socket)],
      stdout=o,stderr=e,env=env)
  try:
   for _ in range(150):
    if socket.is_socket():break
    if proc.poll() is not None:break
    time.sleep(0.02)
   require(socket.is_socket(),"SERVER_DID_NOT_BIND")
   if fail:
    import socket as native
    c=native.socket(native.AF_UNIX,native.SOCK_SEQPACKET)
    c.connect(str(socket))
    c.close()
    code=proc.wait(timeout=6)
    require(code!=0,"EARLY_DISCONNECT_WRONGLY_ACCEPTED")
    return {"case":case,"scenario":"early_disconnect","server_exit":code,
      "fail_closed":True,"server_log_sha256":sha(home/"source.log")}
   client=subprocess.run([str(probe),str(socket),str(manifest)],env=env,
     capture_output=True,text=True,timeout=12)
   code=proc.wait(timeout=6)
   (home/"client.log").write_text(client.stdout)
   (home/"client.err").write_text(client.stderr)
   require(code==0 and client.returncode==0,"PROCESS_RESTART_FAILURE")
   require(client.stdout.count("CPH_GPU_IPC_VERIFIED stage=")==5,
      "FIVE_RECEIPTS_MISSING")
   require("CPH_GPU_IPC_FIVE_FRAMES_PASS" in client.stdout,
      "NO_CLIENT_COMPLETION")
   return {"case":case,"scenario":"fresh_socket_five_frames",
     "client_exit":client.returncode,"server_exit":code,
     "frames":5,"client_log_sha256":sha(home/"client.log"),
     "server_log_sha256":sha(home/"source.log")}
  finally:
   if proc.poll() is None:
    proc.terminate()
    try:proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
     proc.kill();proc.wait(timeout=2)

def main():
 if len(sys.argv)!=9:
  raise SystemExit("usage: recovery_gate SOURCE PROBE RAW MANIFEST COMPUTE_LOG CPU_RECEIPT NEW_EVIDENCE_DIR JSON_OUTPUT")
 source,probe,raw,manifest,compute_log,cpu_receipt,root,out=map(Path,sys.argv[1:])
 require(all(p.is_file() for p in (source,probe,manifest)),"BINARY_OR_MANIFEST_MISSING")
 require(raw.is_dir(),"MISSING_RAW_GPU_INPUTS")
 require(root.is_dir() and not any(root.iterdir()),"PROOF_ROOT_MUST_BE_EMPTY")
 require(not out.exists(),"REFUSE_TO_OVERWRITE_REPORT")
 results=[]
 for case,fail in [(1,False),(2,False),(3,True),(4,False)]:
  results.append(run_case(case,source,probe,raw,manifest,compute_log,cpu_receipt,root,fail))
 passes=[r for r in results if r["scenario"]=="fresh_socket_five_frames"]
 require(len(passes)==3 and sum(r["frames"] for r in passes)==15,
     "RESTART_GATE_NOT_CLOSED")
 report={"schema":"gnu6.qchain.cph_recovery.v1",
   "verdict":"QCHAIN_GPU_SOURCE_IPC_RESTART_AFTER_DISCONNECT_PASS",
   "transport_version":"QCHAIN-GPU-FRAME-v1",
   "fresh_source_processes":4,"successful_restart_runs":3,
   "total_verified_frames":15,
   "early_disconnect_denied":True,
   "gpu_compute_reexecuted_during_restarts":False,
   "transport_only":True,"cases":results}
 out.write_text(json.dumps(report,indent=2)+"\n")
 print(report["verdict"],"frames",report["total_verified_frames"])
if __name__=="__main__":main()
