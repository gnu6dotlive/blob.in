#!/usr/bin/env python3
"""Adapt reviewed wgpu Wayland presenter for a bounded live IPC ring of one frame."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
src=root/"crates/showcase/src/bin/qchain_gpu_viewer.rs"
dst=root/"crates/showcase/src/bin/qchain_gpu_stream_viewer.rs"
assert not dst.exists()
s=src.read_text()
s=s.replace("    qchain_gpu::{self, Request},", "    MappedFrame,")
s=s.replace("    env, fs,", "    env, fs,")
s=s.replace("path::{Path, PathBuf}", "path::PathBuf")
s=s.replace("//! Opt-in native Wayland viewer of verified QCHAIN-FRAME-v1 CPU pixels.",
            "//! CP-I02 bounded native Wayland consumer of freshly computed GPU frames via sealed memfd.")
s=s.replace("    sync::Arc,", "    sync::{Arc,mpsc::{self,Receiver}},")
s=s.replace("    time::{Duration, Instant},", "    time::{Duration, Instant},thread,")
s=s.replace("    epoch: u64,\n}", "    epoch: u64,\n    seq: usize,\n    received: Instant,\n}")
start=s.index("fn fetch(socket: &Path,")
end=s.index("struct Gpu {",start)
s=s[:start]+'''fn stream(socket:PathBuf, receipt:PathBuf, frames:usize,
          sender:mpsc::SyncSender<Result<Frame,String>>) {
    let execute=||->Result<(),String>{
        let cpu:serde_json::Value=serde_json::from_slice(
            &fs::read(&receipt).map_err(|e|e.to_string())?)
            .map_err(|e|e.to_string())?;
        let canonical=cpu["stages"].as_array().ok_or("CPU_STAGES_MISSING")?;
        if canonical.len()!=5{return Err("CANONICAL_FIVE_SCENES_REQUIRED".into());}
        for seq in 0..frames {
            let conn=SeqPacket::connect(&socket).map_err(|e|e.to_string())?;
            conn.require_same_uid().map_err(|e|e.to_string())?;
            conn.set_read_timeout(Some(Duration::from_secs(5)))
                .map_err(|e|e.to_string())?;
            let request=serde_json::json!({"version":"QCHAIN-GPU-STREAM-v1","seq":seq});
            conn.send(&serde_json::to_vec(&request).map_err(|e|e.to_string())?,&[])
                .map_err(|e|e.to_string())?;
            let mut packet=conn.recv().map_err(|e|e.to_string())?;
            if packet.fds.len()!=1{return Err("STREAM_MEMFD_COUNT_INVALID".into());}
            let m:serde_json::Value=serde_json::from_slice(&packet.bytes)
                .map_err(|_|"STREAM_METADATA_JSON_INVALID")?;
            let stage=seq.min(4);
            let canonical_scene=&canonical[stage];
            if m["version"]!="QCHAIN-GPU-STREAM-v1"
                || m["seq"].as_u64()!=Some(seq as u64)
                || m["stage"].as_u64()!=Some(stage as u64)
                || m["scene_sha256"]!=canonical_scene["scene_sha256"]
                || m["semantic_digest"]!=canonical_scene["f2_semantic_digest"]
                || m["backend"]!="Vulkan/WGSL"
                || m["source"]!="CP-F-PersistentSession"
                || m["compute_source_commit"]!="5132cf59b3842e27dcacf89bfe7060e807706e90"
                || m["bytes"]!=786432 || m["stride"]!=2048
                || m["width"]!=512 || m["height"]!=384 || m["zero_copy"]!=false {
                return Err("STREAM_METADATA_AUTHORITY_MISMATCH".into());
            }
            let stat=rustix::fs::fstat(&packet.fds[0]).map_err(|e|e.to_string())?;
            if stat.st_size!=786432{return Err("STREAM_MEMFD_SIZE_INVALID".into());}
            let mapped=MappedFrame::map(packet.fds.remove(0),786432)
                .map_err(|e|e.to_string())?;
            let hash=qchain::digest(mapped.bytes());
            if m["pixel_sha256"].as_str()!=Some(hash.as_str()){
                return Err("STREAM_PIXEL_INTEGRITY_FAILED".into());
            }
            let received=Instant::now();
            let frame=Frame{pixels:mapped.bytes().to_vec(),seq,
                scene_sha:m["scene_sha256"].as_str().unwrap().into(),
                rgba_sha:hash,epoch:stage as u64,received};
            if sender.send(Ok(frame)).is_err(){return Ok(());}
        }
        Ok(())
    };
    if let Err(error)=execute(){let _=sender.send(Err(error));}
}
''' +s[end:]

start=s.index("struct Viewer {")
end=s.index("impl Viewer {",start)
s=s[:start]+'''struct Viewer {
    frame: Option<Frame>,
    receiver:Receiver<Result<Frame,String>>,
    gpu:Option<Gpu>,
    next:Instant,
    end:Instant,
    submitted:usize,
    target:usize,
    started:Instant,
    error:Option<String>,
}
'''+s[end:]
s=s.replace('with_title("QCHAIN · GPU F4 compute witness")',
            'with_title("QCHAIN · LIVE GPU compute → Wayland")')
s=s.replace('"blobin-qchain-gpu-viewer", "blobin-qchain-gpu-viewer"',
            '"blobin-qchain-stream-viewer", "blobin-qchain-stream-viewer"')
s=s.replace("        self.next = Instant::now() + Duration::from_millis(2400);",
            "        self.next = Instant::now()+Duration::from_millis(100);")
s=s.replace("        self.end = Instant::now() + Duration::from_millis(12000);",
            "        self.end = Instant::now()+Duration::from_millis((self.target as u64)*90+10000);")
s=s.replace("        let frame = &self.frames[self.stage];",
            "        let Some(frame) = self.frame.as_ref() else {return Ok(());};")
s=s.replace("        self.submitted[self.stage] = true;",
            "        self.submitted+=1;")
old='''        println!("QCHAIN_GPU_WGPU_PRESENT_SUBMITTED stage={} epoch={} scene_sha256={} rgba_sha256={} dimensions={}x{}",
   self.stage,frame.epoch,frame.scene_sha,frame.rgba_sha,gpu.config.width,gpu.config.height);
        Ok(())'''
new='''        println!("CPI02_WGPU_PRESENT_SUBMITTED seq={} stage={} elapsed_us={} received_to_submit_us={} epoch={} scene_sha256={} rgba_sha256={} dimensions={}x{}",
            frame.seq,frame.epoch,self.started.elapsed().as_micros(),
            frame.received.elapsed().as_micros(),frame.epoch,frame.scene_sha,
            frame.rgba_sha,gpu.config.width,gpu.config.height);
        self.frame=None;
        Ok(())'''
assert old in s
s=s.replace(old,new)

start=s.index("    fn about_to_wait(&mut self, el: &ActiveEventLoop) {")
end=s.index("\n}\nfn main()",start)
s=s[:start]+'''    fn about_to_wait(&mut self, el:&ActiveEventLoop) {
        if self.gpu.is_none(){return;}
        if self.submitted==self.target {el.exit();return;}
        let now=Instant::now();
        if now>=self.end {
            self.error=Some("CPI02_PRESENTATION_TIMEOUT".into());
            el.exit();return;
        }
        if now>=self.next && self.frame.is_none() {
            match self.receiver.try_recv(){
                Ok(Ok(frame))=>{
                    if frame.seq!=self.submitted {
                        self.error=Some("STREAM_FRAME_SEQUENCE_GAP".into());
                        el.exit();return;
                    }
                    self.frame=Some(frame);
                    self.next=now+Duration::from_millis(33);
                    if let Some(gpu)=&self.gpu{gpu.window.request_redraw();}
                }
                Ok(Err(err))=>{
                    self.error=Some(err);el.exit();return;
                }
                Err(mpsc::TryRecvError::Disconnected)=>{
                    self.error=Some("CPI02_SOURCE_DISCONNECTED".into());
                    el.exit();return;
                }
                Err(mpsc::TryRecvError::Empty)=>{
                    self.next=now+Duration::from_millis(4);
                }
            }
        }
        el.set_control_flow(ControlFlow::WaitUntil(self.next.min(self.end)));
    }
'''+s[end:]
start=s.index("fn main()")
s=s[:start]+'''fn main()->Result<(),Box<dyn std::error::Error>> {
    let mut args=env::args().skip(1);
    let socket=PathBuf::from(args.next().ok_or("PRIVATE_SOCKET_REQUIRED")?);
    let receipt=PathBuf::from(args.next().ok_or("CANONICAL_CPU_RECEIPT_REQUIRED")?);
    let target:usize=args.next().ok_or("FRAMES_REQUIRED")?.parse()?;
    if args.next().is_some() || !(40..=300).contains(&target){
        return Err("CPI02_FRAME_TARGET_INVALID".into());
    }
    if env::var_os("WAYLAND_DISPLAY").is_none(){
        return Err("WAYLAND_DISPLAY_MISSING".into());
    }
    let (sender,receiver)=mpsc::sync_channel(1);
    let worker=thread::spawn(move||stream(socket,receipt,target,sender));
    let mut viewer=Viewer{frame:None,receiver,gpu:None,
        next:Instant::now(),end:Instant::now(),submitted:0,target,
        started:Instant::now(),error:None};
    let el=EventLoop::new()?;
    el.set_control_flow(ControlFlow::Wait);
    el.run_app(&mut viewer)?;
    if let Some(error)=viewer.error{return Err(error.into());}
    if viewer.submitted!=target{return Err("CPI02_INCOMPLETE_STREAM".into());}
    worker.join().map_err(|_|"CPI02_STREAM_THREAD_PANICKED")?;
    println!("CPI02_WGPU_STREAM_COMPLETE submitted={target}");
    Ok(())
}
'''
dst.write_text(s)
print("CPI02_VIEWER_GENERATED",len(s.splitlines()))
