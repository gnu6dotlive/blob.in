//! GPU-source readback provider.
use blob_frame::{
    qchain,
    qchain_gpu::{self, SourceFrame},
    SeqListener,
};
use std::{env, fs, path::PathBuf};
fn field<'a>(v: &'a serde_json::Value, key: &str) -> Result<&'a str, String> {
    v[key]
        .as_str()
        .ok_or_else(|| format!("GPU_MANIFEST_FIELD_MISSING {key}"))
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = env::args().skip(1);
    let raw = PathBuf::from(args.next().ok_or("GPU_RAW required")?);
    let manifest = PathBuf::from(args.next().ok_or("GPU_MANIFEST required")?);
    let compute_log = PathBuf::from(args.next().ok_or("GPU_COMPUTE_LOG required")?);
    let cpu_receipt = PathBuf::from(args.next().ok_or("GPU_CPU_RECEIPT required")?);
    let socket = PathBuf::from(args.next().ok_or("GPU_SOCKET required")?);
    if args.next().is_some() {
        return Err("TOO_MANY_ARGUMENTS".into());
    }
    let v: serde_json::Value = serde_json::from_slice(&fs::read(manifest)?)?;
    if v["schema"] != "gnu6.qchain.gpu_source_manifest.v1"
        || v["transport_version"] != qchain_gpu::VERSION
        || v["backend"] != qchain_gpu::BACKEND
        || v["compute_source_commit"] != "5132cf59b3842e27dcacf89bfe7060e807706e90"
        || v["compute_run"] != "CP-F persistent session 40 frames; 1 device; 3 pipelines; 5 buffers"
        || v["gpu_readback_into_sealed_memfd"] != true
        || v["compositor_observed"] != false
        || v["physical_gpu_attestation"] != false
    {
        return Err("GPU_SOURCE_MANIFEST_AUTHORITY_MISMATCH".into());
    }
    let run_hash = field(&v, "compute_run_log_sha256")?.to_owned();
    let log_bytes = fs::read(compute_log)?;
    if qchain::digest(&log_bytes) != run_hash
        || !String::from_utf8_lossy(&log_bytes).contains(
          "QCHAIN_CP_F_PERSISTENT_SESSION_PASS states=5 materials=4 frames=40 devices=1 pipelines=3 reusable_buffers=5 submits=40") {
        return Err("GPU_COMPUTE_RECEIPT_MISMATCH".into());
    }
    let cpu_bytes = fs::read(cpu_receipt)?;
    if qchain::digest(&cpu_bytes) != field(&v, "cpu_receipt_sha256")? {
        return Err("GPU_CPU_RECEIPT_HASH_MISMATCH".into());
    }
    let cpu: serde_json::Value = serde_json::from_slice(&cpu_bytes)?;
    if cpu["verdict"] != "F2_F3_F4_CPU_CHAIN_PASS_BRIDGE_NOT_RUN" {
        return Err("GPU_CPU_RECEIPT_NOT_CANONICAL".into());
    }
    let cpu_stages = cpu["stages"].as_array().ok_or("GPU_CPU_STAGES_MISSING")?;
    if cpu_stages.len() != 5 {
        return Err("GPU_CPU_STAGE_COUNT_MISMATCH".into());
    }
    let list = v["stages"]
        .as_array()
        .ok_or("GPU_MANIFEST_STAGES_MISSING")?;
    if list.len() != 5 {
        return Err("GPU_EXPECTED_FIVE_STAGES".into());
    }
    let listener = SeqListener::bind(&socket)?;
    println!(
        "QCHAIN_GPU_SOURCE_READY socket={} stages=5",
        socket.display()
    );
    for (stage, entry) in list.iter().enumerate() {
        if entry["stage"].as_u64() != Some(stage as u64)
            || entry["epoch"].as_u64() != Some(stage as u64)
        {
            return Err("GPU_SOURCE_EPOCH_REPLAY".into());
        }
        let cpu_stage = &cpu_stages[stage];
        if cpu_stage["epoch"].as_u64() != Some(stage as u64)
            || field(entry, "scene_sha256")? != field(cpu_stage, "scene_sha256")?
            || field(entry, "semantic_digest")? != field(cpu_stage, "f2_semantic_digest")?
        {
            return Err("GPU_CPU_SCENE_BINDING_MISMATCH".into());
        }
        let stem = format!("state{stage}-ceramic-frame0-dpr2.gpu-rgba.bin");
        if field(entry, "gpu_file")? != stem {
            return Err("GPU_UNEXPECTED_SOURCE_FILENAME".into());
        }
        let bytes = fs::read(raw.join(stem))?;
        let hash = qchain::digest(&bytes);
        if hash != field(entry, "gpu_rgba_sha256")? {
            return Err("GPU_SOURCE_PIXELS_CHANGED".into());
        }
        let frame = SourceFrame {
            scene_revision: stage as u64,
            scene_sha256: field(entry, "scene_sha256")?.to_owned(),
            semantic_digest: field(entry, "semantic_digest")?.to_owned(),
            compute_run_log_sha256: run_hash.clone(),
            pixels: bytes,
        };
        frame.validate()?;
        let peer = listener.accept()?;
        qchain_gpu::serve_one(&peer, &frame)?;
        println!(
            "QCHAIN_GPU_SOURCE_TRANSMITTED stage={stage} sha256={hash} run_log_sha256={run_hash}"
        );
    }
    println!("QCHAIN_GPU_SOURCE_COMPLETE gpu_readback_frames=5");
    Ok(())
}
