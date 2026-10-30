#!/usr/bin/env python3
"""BLOB-UI-RUNTIME-01B isolated real native toggle click and GPU pixel witness.
Not a release gate until input/frame oracle has passed.
"""
import argparse,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--out",required=True,type=Path)
 p.add_argument("--inside",action="store_true")
 p.add_argument("--module",type=Path,required=True)
 a=p.parse_args()
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
 if not a.inside:
  proc=subprocess.run(["unshare","-Urn",sys.executable,str(Path(__file__).resolve()),
          "--out",str(out),"--inside","--module",str(a.module.resolve())],
          capture_output=True,text=True,timeout=60)
  (out/"namespace.stdout").write_text(proc.stdout)
  (out/"namespace.stderr").write_text(proc.stderr)
  print(proc.stdout,flush=True)
  if proc.stderr:print(proc.stderr,file=sys.stderr,flush=True)
  return proc.returncode
 subprocess.run(["ip","link","set","lo","up"],check=True,timeout=3)
 rt=Path(os.environ.get("XDG_RUNTIME_DIR","/run/user/1000"))
 socket=out/"render.sock"
 display="blob-ui-01d-private-"+str(os.getpid())
 env=os.environ.copy()
 env.update(WAYLAND_DISPLAY=display,BLOB_UI_01D_ISOLATED_COMPOSITOR="1",RUST_BACKTRACE="1",
               BLOB_UI_01D_CAPTURE_DIR=str(out),BLOB_UI_01D_STRESS="1")
 for k in ("VK_LAYER_PATH","VK_INSTANCE_LAYERS","CPJA7CB_LOADER_FAULT"):env.pop(k,None)
 workers=Path("/mnt/workbench/target/release")
 target=Path("/mnt/sandbox/builds/cargo/debug/blobin-showcase")
 if not target.exists():raise RuntimeError("MISSING_CLIENT_BINARY")
 programs=[
 ["weston","--backend=headless","--renderer=gl","--shell=kiosk","--no-config",
  "--width=1280","--height=800","--idle-time=0","-S",display,
  "--modules="+str(a.module.resolve()),"--log="+str(out/"weston.log")],
 [str(workers/"blobin_renderd"),"--socket",str(socket),
  "--frame-worker",str(workers/"blobin_frame_worker"),
  "--frame-sha256",sha(workers/"blobin_frame_worker"),
  "--gate-worker",str(workers/"worker05c"),"--gate-sha256",sha(workers/"worker05c"),
  "--timeout-ms","15000"],
 [str(target),"--socket",str(socket),"--lab","1","--backend","cpu","--size","1280x800",
  "--trace",str(out/"production-events.jsonl")],
 ]
 children=[];handles=[]
 try:
  for i,cmd in enumerate(programs):
   label=["weston","renderd","showcase"][i]
   so=open(out/(label+".stdout"),"wb");se=open(out/(label+".stderr"),"wb")
   handles.extend((so,se))
   proc=subprocess.Popen(cmd,cwd=out,env=env,stdout=so,stderr=se,start_new_session=True)
   children.append(proc)
   if i==0:
    for _ in range(100):
     if (rt/display).is_socket() or proc.poll() is not None:break
     time.sleep(.04)
    print("Weston",proc.poll(),"socket",(rt/display).is_socket(),flush=True)
    if not (rt/display).is_socket():raise RuntimeError("NO_WESTON_SOCKET")
   if i==1:
    for _ in range(200):
     if socket.exists() or proc.poll() is not None:break
     time.sleep(.03)
    print("Renderd",proc.poll(),"socket",socket.exists(),flush=True)
    if not socket.exists():raise RuntimeError("NO_RENDERD_SOCKET")
  time.sleep(7.5)
  for label,proc in zip(["weston","renderd","showcase"],children):
   print(label,"code",proc.poll(),flush=True)
  for name in ["production-events.jsonl","weston.stdout","renderd.stdout","renderd.stderr","showcase.stdout","showcase.stderr"]:
   f=out/name
   if f.exists():
    t=f.read_text(errors="replace")
    print(name,len(t),t[-4500:] if "events" in name else t[-900:],flush=True)
 finally:
  for proc in reversed(children):
   if proc.poll() is None:
    os.killpg(proc.pid,signal.SIGTERM)
    try:proc.wait(timeout=3)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
  for h in handles:h.close()
 return 0
if __name__=="__main__":sys.exit(main())
