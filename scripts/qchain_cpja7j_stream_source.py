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
    need(40<=a.frames<=4800,"FRAME_COUNT_BOUNDS")
    need(not a.socket.exists(),"SOCKET_ALREADY_EXISTS")
    need(a.socket.parent==Path(os.getenv("XDG_RUNTIME_DIR","/run/user/1000")),
         "SOCKET_PATH_MUST_BE_RUNTIME_DIR")
    need(a.log.is_dir() and not any(a.log.iterdir()),"EVIDENCE_ROOT_NOT_EMPTY")
    provenance=json.loads(a.receipt.read_text())
    stages=provenance["stages"]
    need(len(stages)==5,"FIVE_CANONICAL_STAGES_REQUIRED")
    pipe_requested=int(os.environ.get("CPJA7J_PIPE_BYTES","65536"))
    mode=os.environ.get("CPJA7J_CANONICAL_CACHE","0")
    need(pipe_requested in (65536,1048576),"PIPE_BYTES_NOT_PREREGISTERED")
    need(mode in ("0","1"),"CANONICAL_CACHE_MODE_NOT_PREREGISTERED")
    reference_names=set()
    for n in range(a.frames):
        stage=min(n,4)
        variant=0 if n<5 else ((n-5)//12)%8
        material=("ceramic","gel","metal","paper")[variant//2]
        reference_names.add(f"state{stage}-{material}-frame{variant%2}-dpr2.gpu-rgba.bin")
    reference_hashes={}
    cached={}
    for name in sorted(reference_names):
        contents=(a.baseline/name).read_bytes()
        need(len(contents)==BYTES,"REFERENCE_SIZE_CHANGED")
        reference_hashes[name]=sha(contents)
        if mode=="1":cached[name]=contents
    import fcntl
    process_env=dict(os.environ)
    process_env["RUST_BACKTRACE"]="1"
    engine_err=(a.log/"engine.stderr").open("wb")
    engine=subprocess.Popen([str(a.engine),str(a.frames)],stdout=subprocess.PIPE,
            stderr=engine_err,env=process_env,bufsize=0,pipesize=pipe_requested)
    actual_pipe_bytes=fcntl.fcntl(engine.stdout.fileno(),fcntl.F_GETPIPE_SZ)
    need(actual_pipe_bytes==pipe_requested,"PIPE_BUFFER_SIZE_NOT_APPLIED")
    import hashlib
    digest=hashlib.sha256(json.dumps(reference_hashes,sort_keys=True).encode()).hexdigest()
    print(f"CPJA7J_INTERVENTION_CONFIG pipe_bytes={actual_pipe_bytes} canonical_cache={mode} baseline_blobs={len(reference_hashes)} reference_digest={digest}",flush=True)
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
                pipe_read_us=(time.monotonic_ns()-t0)//1000
                verified_started=time.monotonic_ns()
                need(all(pixels[i]==255 for i in range(3,BYTES,4)),
                     "GPU_FRAME_NONOPAQUE")
                material=("ceramic","gel","metal","paper")[variant//2]
                name=f"state{stage}-{material}-frame{variant%2}-dpr2.gpu-rgba.bin"
                expected=cached[name] if mode=="1" else a.baseline.joinpath(name).read_bytes()
                need(sha(expected)==reference_hashes[name],"REFERENCE_DIGEST_CHANGED")
                need(pixels==expected,"LIVE_GPU_RESULT_CHANGED_"+str(seq))
                if seq%30==0:
                    print(f"CPJA7J_FULL_BYTE_COMPARE seq={seq} reference_sha256={reference_hashes[name]} status=EQUAL bytes={BYTES}",flush=True)

                verification_us=(time.monotonic_ns()-verified_started)//1000
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
                seal_started=time.monotonic_ns()
                fd=sealed(pixels)
                seal_us=(time.monotonic_ns()-seal_started)//1000
                send_started=time.monotonic_ns()
                try:
                    sent=conn.sendmsg([json.dumps(meta,separators=(",",":")).encode()],
                             [(socket.SOL_SOCKET,socket.SCM_RIGHTS,
                               struct.pack("i",fd))])
                    need(sent>0,"SOURCE_FRAME_SEND_FAILED")
                finally:os.close(fd)
                send_us=(time.monotonic_ns()-send_started)//1000
                print("CPJA7H_BROKER_TIMING seq={} pipe_read_us={} canonical_verify_us={} memfd_seal_us={} memfd_send_us={}".format(
                      seq,pipe_read_us,verification_us,seal_us,send_us),flush=True)
                timeline.append({"seq":seq,"stage":stage,"variant":variant,
                    "pixel_sha256":frame_hash,
                    "pipe_read_us":pipe_read_us,
                    "canonical_verify_us":verification_us,
                    "memfd_seal_us":seal_us,
                    "memfd_send_us":send_us,
                    "gpu_pipe_wait_us":
                    round((time_ns-t0)/1000,1),"ready_ns":time_ns})
                if seq%30==0:print("CPI02_GPU_IPC_LIVE_FRAME",seq,flush=True)
        engine.stdout.close()
        status=engine.wait(timeout=8)
        need(status==0,"ENGINE_EXIT_NONZERO")
        (a.log/"timeline.json").write_text(json.dumps({
           "schema":"gnu6.qchain.cpi02_source_timeline.v1",
           "frames":timeline,"engine_exit":status,
           "gpu_device_single_session":True,
           "memfd_backpressure":"viewer-initiated one frame per connection",
           "cpja7j_pipe_bytes":actual_pipe_bytes,
           "cpja7j_canonical_cache":mode,
           "cpja7j_reference_sha256":reference_hashes,
           "cpja7j_full_byte_comparisons":a.frames},indent=2)+"\n")
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
