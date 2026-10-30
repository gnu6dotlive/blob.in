#!/usr/bin/env python3
"""Live GPU stdout frames -> per-frame sealed memfd Unix SEQPACKET source.
Never loads rendered files as output: baseline files are an exactness oracle only.
"""
import argparse,fcntl,hashlib,json,os,socket,struct,subprocess,time
from pathlib import Path
VERSION="QCHAIN-GPU-STREAM-v1"
BYTES=512*384*4
def need(ok,msg):
    if not ok:raise RuntimeError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def read_exact(fd,n):
    out=bytearray()
    while len(out)<n:
        data=fd.read(n-len(out))
        if not data:raise EOFError("ENGINE_STREAM_TRUNCATED")
        out.extend(data)
    return bytes(out)
def sealed(raw):
    fd=os.memfd_create("qchain-cpi02-live",os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
    try:
        with os.fdopen(os.dup(fd),"wb") as f:f.write(raw)
        fcntl.fcntl(fd,fcntl.F_ADD_SEALS,fcntl.F_SEAL_SEAL|
            fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_GROW|fcntl.F_SEAL_WRITE)
        need(os.fstat(fd).st_size==BYTES,"LIVE_MEMFD_SIZE_INVALID")
        return fd
    except:
        os.close(fd);raise

def run(a):
    need(40<=a.frames<=300,"FRAME_COUNT_BOUNDS")
    need(not a.socket.exists(),"SOCKET_ALREADY_EXISTS")
    need(a.socket.parent==Path(os.getenv("XDG_RUNTIME_DIR","/run/user/1000")),
         "SOCKET_PATH_MUST_BE_RUNTIME_DIR")
    need(a.log.is_dir() and not any(a.log.iterdir()),"EVIDENCE_ROOT_NOT_EMPTY")
    provenance=json.loads(a.receipt.read_text())
    stages=provenance["stages"]
    need(len(stages)==5,"FIVE_CANONICAL_STAGES_REQUIRED")
    process_env=dict(os.environ)
    process_env["RUST_BACKTRACE"]="1"
    engine_err=(a.log/"engine.stderr").open("wb")
    engine=subprocess.Popen([str(a.engine),str(a.frames)],stdout=subprocess.PIPE,
            stderr=engine_err,env=process_env,bufsize=0)
    listener=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET)
    listener.bind(str(a.socket))
    os.chmod(a.socket,0o600)
    listener.listen(1)
    listener.settimeout(8.0)
    timeline=[]
    try:
        for seq in range(a.frames):
            conn,_=listener.accept()
            conn.settimeout(5.0)
            with conn:
                _,uid,_=struct.unpack("3i",conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                need(uid==os.geteuid(),"FOREIGN_PEER_UID")
                data,_,flags,_=conn.recvmsg(4096)
                need(flags==0,"REQUEST_TRUNCATED")
                req=json.loads(data)
                need(req=={"version":VERSION,"seq":seq},"OUT_OF_ORDER_REQUEST")
                t0=time.monotonic_ns()
                header=read_exact(engine.stdout,24)
                magic,s,stage,variant,length=struct.unpack("<8sIIII",header)
                need(magic==b"QCI02v1!" and s==seq and stage==min(seq,4)
                     and variant==(0 if seq<5 else ((seq-5)//12)%8)
                     and length==BYTES,"ENGINE_FRAME_HEADER_INVALID")
                pixels=read_exact(engine.stdout,BYTES)
                need(all(pixels[i]==255 for i in range(3,BYTES,4)),
                     "GPU_FRAME_NONOPAQUE")
                material=("ceramic","gel","metal","paper")[variant//2]
                name=f"state{stage}-{material}-frame{variant%2}-dpr2.gpu-rgba.bin"
                expected=a.baseline.joinpath(name).read_bytes()
                need(pixels==expected,"LIVE_GPU_RESULT_CHANGED_"+str(seq))

                frame_hash=sha(pixels)
                time_ns=time.monotonic_ns()
                meta={"version":VERSION,"seq":seq,"stage":stage,
                      "scene_sha256":stages[stage]["scene_sha256"],
                      "semantic_digest":stages[stage]["f2_semantic_digest"],
                      "pixel_sha256":frame_hash,
                      "bytes":BYTES,"stride":2048,"width":512,"height":384,
                      "backend":"Vulkan/WGSL","source":"CP-F-PersistentSession",
                      "compute_source_commit":"5132cf59b3842e27dcacf89bfe7060e807706e90",
                      "frame_dispatched_ns":time_ns,"zero_copy":False}
                fd=sealed(pixels)
                try:
                    sent=conn.sendmsg([json.dumps(meta,separators=(",",":")).encode()],
                             [(socket.SOL_SOCKET,socket.SCM_RIGHTS,
                               struct.pack("i",fd))])
                    need(sent>0,"SOURCE_FRAME_SEND_FAILED")
                finally:os.close(fd)
                timeline.append({"seq":seq,"stage":stage,"variant":variant,
                    "pixel_sha256":frame_hash,"gpu_pipe_wait_us":
                    round((time_ns-t0)/1000,1),"ready_ns":time_ns})
                if seq%30==0:print("CPI02_GPU_IPC_LIVE_FRAME",seq,flush=True)
        engine.stdout.close()
        status=engine.wait(timeout=8)
        need(status==0,"ENGINE_EXIT_NONZERO")
        (a.log/"timeline.json").write_text(json.dumps({
           "schema":"gnu6.qchain.cpi02_source_timeline.v1",
           "frames":timeline,"engine_exit":status,
           "gpu_device_single_session":True,
           "memfd_backpressure":"viewer-initiated one frame per connection"},indent=2)+"\n")
        print("CPI02_SOURCE_COMPLETE frames="+str(a.frames),flush=True)
    finally:
        listener.close();a.socket.unlink(missing_ok=True)
        if engine.poll() is None:
            engine.terminate()
            try:engine.wait(timeout=3)
            except subprocess.TimeoutExpired:engine.kill();engine.wait()
        engine_err.close()

def main():
    p=argparse.ArgumentParser()
    for n in ("engine","baseline","receipt","socket","log"):
        p.add_argument("--"+n,required=True,type=Path)
    p.add_argument("--frames",type=int,default=120)
    a=p.parse_args();run(a)
if __name__=="__main__":main()
