//! CP-H deterministic external-client probe of five GPU-source IPC frames.
use blob_frame::{
    qchain,
    qchain_gpu::{self, Request},
    SeqPacket,
};
use std::{env, fs, path::PathBuf, time::Duration};
fn text<'a>(v: &'a serde_json::Value, k: &str) -> Result<&'a str, String> {
    v[k].as_str()
        .ok_or_else(|| format!("CPH_MANIFEST_MISSING_{k}"))
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = env::args().skip(1);
    let sock = PathBuf::from(args.next().ok_or("SOCKET_REQUIRED")?);
    let manifest = PathBuf::from(args.next().ok_or("MANIFEST_REQUIRED")?);
    if args.next().is_some() {
        return Err("EXTRA_ARGUMENTS".into());
    }
    let v: serde_json::Value = serde_json::from_slice(&fs::read(manifest)?)?;
    if v["transport_version"] != qchain_gpu::VERSION {
        return Err("CPH_EXPECT_GPU_PROTOCOL".into());
    }
    let run = text(&v, "compute_run_log_sha256")?;
    let list = v["stages"].as_array().ok_or("CPH_STAGES_REQUIRED")?;
    if list.len() != 5 {
        return Err("CPH_FIVE_STAGES_REQUIRED".into());
    }
    for (i, stage) in list.iter().enumerate() {
        if stage["stage"].as_u64() != Some(i as u64) || stage["epoch"].as_u64() != Some(i as u64) {
            return Err("CPH_EPOCH_MISMATCH".into());
        }
        let req = Request {
            version: qchain_gpu::VERSION.into(),
            request_id: i as u64 + 1,
            scene_revision: i as u64,
            scene_sha256: text(stage, "scene_sha256")?.into(),
            semantic_digest: text(stage, "semantic_digest")?.into(),
            expected_gpu_rgba_sha256: text(stage, "gpu_rgba_sha256")?.into(),
            compute_run_log_sha256: run.into(),
        };
        let conn = SeqPacket::connect(&sock)?;
        conn.set_read_timeout(Some(Duration::from_secs(5)))?;
        let (meta, frame) = qchain_gpu::receive_one(&conn, &req)?;
        if meta.scene_revision != i as u64
            || qchain::digest(frame.bytes()) != req.expected_gpu_rgba_sha256
        {
            return Err("CPH_GPU_FRAME_IDENTITY_DRIFT".into());
        }
        println!("CPH_GPU_IPC_VERIFIED stage={i} sha256={}", meta.rgba_sha256);
    }
    println!("CPH_GPU_IPC_FIVE_FRAMES_PASS");
    Ok(())
}
