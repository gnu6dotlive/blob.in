//! QCHAIN-FRAME-v1: an opt-in immutable CPU scene-frame source.
//! This intentionally does NOT reinterpret F2 lobes as BLOB-FRAME-v1 circles.
use crate::{
    memfd::{sealed_memfd, MappedFrame},
    SeqPacket,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::os::fd::AsFd;

pub const VERSION: &str = "QCHAIN-FRAME-v1";
pub const QUALIFICATION: &str = "F2_F3_F4_CPU_WITNESS_NOT_WAYLAND";
pub const SOURCE: &str = "qchain-f2-f3-f4-cpu-archive";
pub const W: u32 = 512;
pub const H: u32 = 384;
pub const STRIDE: u32 = W * 4;
pub const PIXEL_BYTES: u64 = (STRIDE as u64) * (H as u64);

pub fn digest(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}
fn valid_hash(s: &str) -> bool {
    s.len() == 64
        && s.bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct SceneRequest {
    pub version: String,
    pub request_id: u64,
    pub scene_revision: u64,
    pub scene_sha256: String,
    pub expected_rgba_sha256: String,
    pub semantic_digest: String,
}
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct SceneFrame {
    pub version: String,
    pub request_id: u64,
    pub scene_revision: u64,
    pub scene_sha256: String,
    pub source: String,
    pub width_px: u32,
    pub height_px: u32,
    pub stride_bytes: u32,
    pub buffer_bytes: u64,
    pub rgba_sha256: String,
    pub format: String,
    pub qualification: String,
    pub semantic_digest: String,
    pub gpu_qualified: bool,
    pub compositor_observed: bool,
}
#[derive(Debug, Clone)]
pub struct SourceFrame {
    pub scene_revision: u64,
    pub scene_sha256: String,
    pub semantic_digest: String,
    pub pixels: Vec<u8>,
}
impl SourceFrame {
    pub fn validate(&self) -> Result<(), String> {
        if !valid_hash(&self.scene_sha256)
            || self.semantic_digest.parse::<u64>().is_err()
            || self.pixels.len() != PIXEL_BYTES as usize
            || self.pixels.chunks_exact(4).any(|p| p[3] != 255)
        {
            return Err("QCHAIN_INVALID_SOURCE_FRAME".into());
        }
        Ok(())
    }
}
pub fn validate(req: &SceneRequest, meta: &SceneFrame) -> Result<(), String> {
    if req.version != VERSION
        || meta.version != VERSION
        || req.request_id == 0
        || req.scene_sha256 != meta.scene_sha256
        || req.scene_revision != meta.scene_revision
        || req.request_id != meta.request_id
        || req.expected_rgba_sha256 != meta.rgba_sha256
        || req.semantic_digest != meta.semantic_digest
        || !valid_hash(&meta.scene_sha256)
        || !valid_hash(&meta.rgba_sha256)
        || meta.source != SOURCE
        || meta.qualification != QUALIFICATION
        || meta.width_px != W
        || meta.height_px != H
        || meta.stride_bytes != STRIDE
        || meta.buffer_bytes != PIXEL_BYTES
        || meta.format != "RGBA8_UNORM_OPAQUE"
        || meta.gpu_qualified
        || meta.compositor_observed
        || meta.semantic_digest.parse::<u64>().is_err()
    {
        return Err("QCHAIN_FRAME_CONTRACT_MISMATCH".into());
    }
    Ok(())
}
pub fn serve_one(conn: &SeqPacket, source: &SourceFrame) -> Result<(), String> {
    conn.require_same_uid().map_err(|e| e.to_string())?;
    source.validate()?;
    let packet = conn.recv().map_err(|e| e.to_string())?;
    if !packet.fds.is_empty() {
        return Err("QCHAIN_REQUEST_CARRIED_FDS".into());
    }
    let req: SceneRequest =
        serde_json::from_slice(&packet.bytes).map_err(|_| "QCHAIN_INVALID_REQUEST")?;
    if req.version != VERSION
        || req.request_id == 0
        || req.scene_revision != source.scene_revision
        || req.scene_sha256 != source.scene_sha256
        || req.semantic_digest != source.semantic_digest
        || req.expected_rgba_sha256 != digest(&source.pixels)
    {
        return Err("QCHAIN_SOURCE_BINDING_MISMATCH".into());
    }
    let meta = SceneFrame {
        version: VERSION.into(),
        request_id: req.request_id,
        scene_revision: source.scene_revision,
        scene_sha256: source.scene_sha256.clone(),
        source: SOURCE.into(),
        width_px: W,
        height_px: H,
        stride_bytes: STRIDE,
        buffer_bytes: PIXEL_BYTES,
        rgba_sha256: digest(&source.pixels),
        format: "RGBA8_UNORM_OPAQUE".into(),
        qualification: QUALIFICATION.into(),
        semantic_digest: source.semantic_digest.clone(),
        gpu_qualified: false,
        compositor_observed: false,
    };
    let fd = sealed_memfd("qchain-f4-cpu", &source.pixels).map_err(|e| e.to_string())?;
    let bytes = serde_json::to_vec(&meta).map_err(|e| e.to_string())?;
    conn.send(&bytes, &[fd.as_fd()]).map_err(|e| e.to_string())
}
pub fn receive_one(
    conn: &SeqPacket,
    req: &SceneRequest,
) -> Result<(SceneFrame, MappedFrame), String> {
    conn.require_same_uid().map_err(|e| e.to_string())?;
    if req.version != VERSION
        || req.request_id == 0
        || !valid_hash(&req.scene_sha256)
        || !valid_hash(&req.expected_rgba_sha256)
        || req.semantic_digest.parse::<u64>().is_err()
    {
        return Err("QCHAIN_REQUEST_INVALID".into());
    }
    conn.send(&serde_json::to_vec(req).map_err(|e| e.to_string())?, &[])
        .map_err(|e| e.to_string())?;
    let mut packet = conn.recv().map_err(|e| e.to_string())?;
    if packet.fds.len() != 1 {
        return Err("QCHAIN_EXPECTS_EXACT_ONE_MEMFD".into());
    }
    let meta: SceneFrame =
        serde_json::from_slice(&packet.bytes).map_err(|_| "QCHAIN_INVALID_FRAME_META")?;
    validate(req, &meta)?;
    let mapped = MappedFrame::map(packet.fds.remove(0), meta.buffer_bytes)
        .map_err(|e| format!("QCHAIN_MEMFD_NOT_VERIFIED {e}"))?;
    if mapped.bytes().chunks_exact(4).any(|p| p[3] != 255)
        || digest(mapped.bytes()) != meta.rgba_sha256
    {
        return Err("QCHAIN_PIXEL_INTEGRITY_FAILED".into());
    }
    Ok((meta, mapped))
}
#[cfg(test)]
mod tests {
    use super::*;
    use std::thread;
    fn fixture() -> (SceneRequest, SourceFrame) {
        let pixels = vec![255u8; PIXEL_BYTES as usize];
        let scene_sha256 = digest(b"qchain-test-source");
        (
            SceneRequest {
                version: VERSION.into(),
                request_id: 4,
                scene_revision: 2,
                scene_sha256: scene_sha256.clone(),
                expected_rgba_sha256: digest(&pixels),
                semantic_digest: "123456".into(),
            },
            SourceFrame {
                scene_revision: 2,
                scene_sha256,
                semantic_digest: "123456".into(),
                pixels,
            },
        )
    }
    #[test]
    fn sealed_socket_roundtrip_and_exact_pixel_digest() {
        let (req, source) = fixture();
        let (a, b) = SeqPacket::pair().unwrap();
        let child = thread::spawn(move || serve_one(&a, &source).unwrap());
        let (meta, pixels) = receive_one(&b, &req).unwrap();
        assert_eq!(meta.rgba_sha256, digest(pixels.bytes()));
        assert_eq!(pixels.bytes().len(), PIXEL_BYTES as usize);
        assert!(!meta.compositor_observed && !meta.gpu_qualified);
        child.join().unwrap();
    }
    #[test]
    fn negative_wrong_scene_epoch_and_hash_rejected() {
        let (req, source) = fixture();
        let mut wrong = req.clone();
        wrong.scene_revision += 1;
        let (a, b) = SeqPacket::pair().unwrap();
        let child = thread::spawn(move || serve_one(&a, &source));
        let send = serde_json::to_vec(&wrong).unwrap();
        b.send(&send, &[]).unwrap();
        assert!(child.join().unwrap().is_err());
        let meta = SceneFrame {
            version: VERSION.into(),
            request_id: req.request_id,
            scene_revision: req.scene_revision,
            scene_sha256: req.scene_sha256.clone(),
            source: SOURCE.into(),
            width_px: W,
            height_px: H,
            stride_bytes: STRIDE,
            buffer_bytes: PIXEL_BYTES,
            rgba_sha256: digest(&vec![255; PIXEL_BYTES as usize]),
            format: "RGBA8_UNORM_OPAQUE".into(),
            qualification: QUALIFICATION.into(),
            semantic_digest: "5".into(),
            gpu_qualified: false,
            compositor_observed: false,
        };
        let mut wrong_meta = meta.clone();
        wrong_meta.scene_sha256 = digest(b"foreign");
        assert!(validate(&req, &wrong_meta).is_err());
        let mut forged = meta.clone();
        forged.gpu_qualified = true;
        assert!(validate(&req, &forged).is_err());
        let mut forged = meta.clone();
        forged.compositor_observed = true;
        assert!(validate(&req, &forged).is_err());
        let mut forged = meta;
        forged.buffer_bytes = 42;
        assert!(validate(&req, &forged).is_err());
    }
}
