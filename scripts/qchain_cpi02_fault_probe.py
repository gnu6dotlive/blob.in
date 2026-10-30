#!/usr/bin/env python3
"""One-shot malformed stream request, fail-closed outside the compositor."""
import argparse,json,os,socket,subprocess,time
from pathlib import Path
def need(ok,msg):
    if not ok:raise RuntimeError(msg)
def run(a):
    need(a.root.is_dir() and not any(a.root.iterdir()),"ROOT_NOT_EMPTY")
    logs=a.root/"broker-evidence";logs.mkdir()
    sock=Path(os.environ.get("XDG_RUNTIME_DIR","/run/user/1000"))/f"qci02-fault-{os.getpid()}.sock"
    source_out=(a.root/"source.stdout").open("wb")
    source_err=(a.root/"source.stderr").open("wb")
    p=subprocess.Popen(["python3",str(a.source),"--engine",str(a.engine),
      "--baseline",str(a.baseline),"--receipt",str(a.receipt),
      "--socket",str(sock),"--log",str(logs),"--frames","40"],
      stdout=source_out,stderr=source_err)
    try:
        for _ in range(100):
            if sock.is_socket():break
            if p.poll() is not None:break
            time.sleep(.025)
        need(sock.is_socket(),"SOURCE_FAILED_TO_BIND")
        with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as c:
            c.connect(str(sock))
            c.send(json.dumps({"version":"QCHAIN-GPU-STREAM-v1","seq":999}).encode())
            try:
                data=c.recv(4096)
                need(data==b"","INVALID_REQUEST_WAS_ANSWERED")
            except ConnectionResetError:pass
        status=p.wait(timeout=6)
        source_err.flush()
        err=(a.root/"source.stderr").read_text()
        need(status!=0 and "OUT_OF_ORDER_REQUEST" in err,
             "INCORRECT_SEQUENCE_WAS_NOT_REJECTED")
        need(not (logs/"timeline.json").exists(),
             "FALSE_COMPLETION_TIMELINE")
        report={"schema":"gnu6.qchain.cpi02_bad_request.v1",
         "expected_refusal":"OUT_OF_ORDER_REQUEST","source_exit":status,
         "fd_returned":False,"completion_receipt_emitted":False,
         "verdict":"CPI02_LIVE_STREAM_OUT_OF_ORDER_REJECTED"}
        (a.root/"verdict.json").write_text(json.dumps(report,indent=2)+"\n")
        print(report["verdict"])
    finally:
        if p.poll() is None:p.kill();p.wait()
        source_out.close();source_err.close()
        sock.unlink(missing_ok=True)
def main():
    p=argparse.ArgumentParser()
    for n in ("root","source","engine","baseline","receipt"):
        p.add_argument("--"+n,required=True,type=Path)
    run(p.parse_args())
if __name__=="__main__":main()
