//! Experimental GPU-source transport. Versioned separately from CPU QCHAIN-FRAME-v1.
use crate::qchain::{self, H, PIXEL_BYTES, STRIDE, W};
use crate::{
    memfd::{sealed_memfd, MappedFrame},
    SeqPacket,
};
use serde::{Deserialize, Serialize};
use std::{os::fd::AsFd, time::Duration};
pub const VERSION: &str = "QCHAIN-GPU-FRAME-v1";
pub const SOURCE: &str = "qchain-cpf-vulkan-gpu-readback";
pub const QUALIFICATION: &str = "GPU_COMPUTE_WITNESS_NOT_WAYLAND";
pub const BACKEND: &str = "Vulkan/WGSL";

fn valid_hash(s: &str) -> bool {
    s.len() == 64
        && s.bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub version: String,
    pub request_id: u64,
    pub scene_revision: u64,
    pub scene_sha256: String,
    pub semantic_digest: String,
    pub expected_gpu_rgba_sha256: String,
    pub compute_run_log_sha256: String,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct FrameMeta {
    pub version: String,
    pub request_id: u64,
    pub scene_revision: u64,
    pub scene_sha256: String,
    pub semantic_digest: String,
    pub rgba_sha256: String,
    pub compute_run_log_sha256: String,
    pub source: String,
    pub qualification: String,
    pub backend: String,
    pub width_px: u32,
    pub height_px: u32,
    pub stride_bytes: u32,
    pub buffer_bytes: u64,
    pub format: String,
    pub dispatches_per_frame: u32,
    pub gpu_readback_to_memfd: bool,
    pub compute_source_verified_in_run: bool,
    pub compositor_observed: bool,
    pub gpu_qualified: bool,
}
#[derive(Clone, Debug)]
pub struct SourceFrame {
    pub scene_revision: u64,
    pub scene_sha256: String,
    pub semantic_digest: String,
    pub compute_run_log_sha256: String,
    pub pixels: Vec<u8>,
}
pub fn validate_request(req: &Request) -> Result<(), String> {
    if req.version != VERSION
        || req.request_id == 0
        || req.scene_revision.checked_add(1) != Some(req.request_id)
        || !valid_hash(&req.scene_sha256)
        || !valid_hash(&req.expected_gpu_rgba_sha256)
        || !valid_hash(&req.compute_run_log_sha256)
        || req.semantic_digest.parse::<u64>().is_err()
    {
        return Err("GPU_REQUEST_INVALID".into());
    }
    Ok(())
}
pub fn validate(req: &Request, meta: &FrameMeta) -> Result<(), String> {
    validate_request(req)?;
    if meta.version != VERSION
        || meta.request_id != req.request_id
        || meta.scene_revision != req.scene_revision
        || meta.scene_sha256 != req.scene_sha256
        || meta.semantic_digest != req.semantic_digest
        || meta.rgba_sha256 != req.expected_gpu_rgba_sha256
        || meta.compute_run_log_sha256 != req.compute_run_log_sha256
        || meta.source != SOURCE
        || meta.qualification != QUALIFICATION
        || meta.backend != BACKEND
        || meta.width_px != W
        || meta.height_px != H
        || meta.stride_bytes != STRIDE
        || meta.buffer_bytes != PIXEL_BYTES
        || meta.format != "RGBA8_UNORM_OPAQUE"
        || meta.dispatches_per_frame != 6
        || !meta.gpu_readback_to_memfd
        || !meta.compute_source_verified_in_run
        || meta.compositor_observed
        || meta.gpu_qualified
    {
        return Err("GPU_FRAME_CONTRACT_MISMATCH".into());
    }
    Ok(())
}

impl SourceFrame {
    pub fn validate(&self) -> Result<(), String> {
        if !valid_hash(&self.scene_sha256)
            || !valid_hash(&self.compute_run_log_sha256)
            || self.semantic_digest.parse::<u64>().is_err()
            || self.pixels.len() != PIXEL_BYTES as usize
            || self.pixels.chunks_exact(4).any(|px| px[3] != 255)
        {
            return Err("GPU_SOURCE_FRAME_INVALID".into());
        }
        Ok(())
    }
}
pub fn serve_one(conn: &SeqPacket, source: &SourceFrame) -> Result<(), String> {
    conn.require_same_uid().map_err(|e| e.to_string())?;
    source.validate()?;
    // A stalled same-UID client must not block this bounded one-shot source forever.
    conn.set_read_timeout(Some(Duration::from_secs(5)))
        .map_err(|e| e.to_string())?;
    let packet = conn.recv().map_err(|e| e.to_string())?;
    if !packet.fds.is_empty() {
        return Err("GPU_REQUEST_UNEXPECTED_FDS".into());
    }
    let request: Request =
        serde_json::from_slice(&packet.bytes).map_err(|_| "GPU_REQUEST_MALFORMED")?;
    validate_request(&request)?;
    if request.scene_revision != source.scene_revision
        || request.scene_sha256 != source.scene_sha256
        || request.semantic_digest != source.semantic_digest
        || request.compute_run_log_sha256 != source.compute_run_log_sha256
        || request.expected_gpu_rgba_sha256 != qchain::digest(&source.pixels)
    {
        return Err("GPU_SOURCE_BINDING_MISMATCH".into());
    }
    let meta = FrameMeta {
        version: VERSION.into(),
        request_id: request.request_id,
        scene_revision: source.scene_revision,
        scene_sha256: source.scene_sha256.clone(),
        semantic_digest: source.semantic_digest.clone(),
        rgba_sha256: qchain::digest(&source.pixels),
        compute_run_log_sha256: source.compute_run_log_sha256.clone(),
        source: SOURCE.into(),
        qualification: QUALIFICATION.into(),
        backend: BACKEND.into(),
        width_px: W,
        height_px: H,
        stride_bytes: STRIDE,
        buffer_bytes: PIXEL_BYTES,
        format: "RGBA8_UNORM_OPAQUE".into(),
        dispatches_per_frame: 6,
        gpu_readback_to_memfd: true,
        compute_source_verified_in_run: true,
        compositor_observed: false,
        gpu_qualified: false,
    };
    let fd = sealed_memfd("qchain-gpu-cpf-readback", &source.pixels).map_err(|e| e.to_string())?;
    conn.send(
        &serde_json::to_vec(&meta).map_err(|e| e.to_string())?,
        &[fd.as_fd()],
    )
    .map_err(|e| e.to_string())
}
pub fn receive_one(conn: &SeqPacket, req: &Request) -> Result<(FrameMeta, MappedFrame), String> {
    conn.require_same_uid().map_err(|e| e.to_string())?;
    validate_request(req)?;
    conn.set_read_timeout(Some(Duration::from_secs(5)))
        .map_err(|e| e.to_string())?;
    conn.send(&serde_json::to_vec(req).map_err(|e| e.to_string())?, &[])
        .map_err(|e| e.to_string())?;
    let mut packet = conn.recv().map_err(|e| e.to_string())?;
    if packet.fds.len() != 1 {
        return Err("GPU_EXPECTS_EXACTLY_ONE_MEMFD".into());
    }
    let meta: FrameMeta =
        serde_json::from_slice(&packet.bytes).map_err(|_| "GPU_FRAME_META_MALFORMED")?;
    validate(req, &meta)?;
    let stat = rustix::fs::fstat(&packet.fds[0]).map_err(|e| e.to_string())?;
    if stat.st_size != meta.buffer_bytes as i64 {
        return Err("GPU_MEMFD_SIZE_NOT_EXACT".into());
    }
    let mapped = MappedFrame::map(packet.fds.remove(0), meta.buffer_bytes)
        .map_err(|e| format!("GPU_MEMFD_REJECTED {e}"))?;
    if mapped.bytes().chunks_exact(4).any(|p| p[3] != 255)
        || qchain::digest(mapped.bytes()) != meta.rgba_sha256
    {
        return Err("GPU_PIXEL_INTEGRITY_REJECTED".into());
    }
    Ok((meta, mapped))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread;
    fn fixture() -> (Request, SourceFrame) {
        let pixels = vec![255u8; PIXEL_BYTES as usize];
        let scene = qchain::digest(b"gpu-fixture");
        let run = qchain::digest(b"real-gpu-qualification-log");
        (
            Request {
                version: VERSION.into(),
                request_id: 1,
                scene_revision: 0,
                scene_sha256: scene.clone(),
                semantic_digest: "999".into(),
                expected_gpu_rgba_sha256: qchain::digest(&pixels),
                compute_run_log_sha256: run.clone(),
            },
            SourceFrame {
                scene_revision: 0,
                scene_sha256: scene,
                semantic_digest: "999".into(),
                compute_run_log_sha256: run,
                pixels,
            },
        )
    }
    #[test]
    fn exact_sealed_memfd_gpu_roundtrip() {
        let (req, source) = fixture();
        let (server, client) = SeqPacket::pair().unwrap();
        let worker = thread::spawn(move || serve_one(&server, &source).unwrap());
        let (meta, pixels) = receive_one(&client, &req).unwrap();
        assert_eq!(meta.rgba_sha256, qchain::digest(pixels.bytes()));
        assert!(meta.compute_source_verified_in_run);
        assert!(!meta.compositor_observed && !meta.gpu_qualified);
        worker.join().unwrap();
    }
    #[test]
    fn negative_scene_and_provenance_mutations() {
        let (req, source) = fixture();
        let (server, client) = SeqPacket::pair().unwrap();
        let mut false_epoch = req.clone();
        false_epoch.scene_revision = 1;
        assert!(validate_request(&false_epoch).is_err());
        let mut false_provenance = req.clone();
        false_provenance.compute_run_log_sha256 = qchain::digest(b"other");
        let worker = thread::spawn(move || serve_one(&server, &source));
        client
            .send(&serde_json::to_vec(&false_provenance).unwrap(), &[])
            .unwrap();
        assert!(worker.join().unwrap().is_err());
        let mut invalid = req.clone();
        invalid.expected_gpu_rgba_sha256 = "0".into();
        assert!(validate_request(&invalid).is_err());
    }
    #[test]
    fn cpu_protocol_cannot_impersonate_gpu_provenance() {
        assert_ne!(VERSION, qchain::VERSION);
        assert_ne!(SOURCE, qchain::SOURCE);
        assert_ne!(QUALIFICATION, qchain::QUALIFICATION);
    }
}

#[cfg(test)]
mod hardening_tests {
    use super::*;
    use crate::memfd::{memfd_with, sealed_memfd};
    use std::{os::fd::AsFd, thread};

    fn fixture() -> (Request, SourceFrame) {
        let bytes = vec![255; PIXEL_BYTES as usize];
        let scene = qchain::digest(b"cp-h-scene");
        let run = qchain::digest(b"cp-h-vulkan-execution-receipt");
        (
            Request {
                version: VERSION.into(),
                request_id: 1,
                scene_revision: 0,
                scene_sha256: scene.clone(),
                semantic_digest: "112233".into(),
                expected_gpu_rgba_sha256: qchain::digest(&bytes),
                compute_run_log_sha256: run.clone(),
            },
            SourceFrame {
                scene_revision: 0,
                scene_sha256: scene,
                semantic_digest: "112233".into(),
                compute_run_log_sha256: run,
                pixels: bytes,
            },
        )
    }

    fn metadata(req: &Request) -> FrameMeta {
        FrameMeta {
            version: VERSION.into(),
            request_id: req.request_id,
            scene_revision: req.scene_revision,
            scene_sha256: req.scene_sha256.clone(),
            semantic_digest: req.semantic_digest.clone(),
            rgba_sha256: req.expected_gpu_rgba_sha256.clone(),
            compute_run_log_sha256: req.compute_run_log_sha256.clone(),
            source: SOURCE.into(),
            qualification: QUALIFICATION.into(),
            backend: BACKEND.into(),
            width_px: W,
            height_px: H,
            stride_bytes: STRIDE,
            buffer_bytes: PIXEL_BYTES,
            format: "RGBA8_UNORM_OPAQUE".into(),
            dispatches_per_frame: 6,
            gpu_readback_to_memfd: true,
            compute_source_verified_in_run: true,
            compositor_observed: false,
            gpu_qualified: false,
        }
    }

    #[test]
    fn overflow_and_noncanonical_request_id_fail_closed() {
        let (mut req, _) = fixture();
        req.scene_revision = u64::MAX;
        req.request_id = u64::MAX;
        assert_eq!(validate_request(&req).unwrap_err(), "GPU_REQUEST_INVALID");
        req.scene_revision = 0;
        req.request_id = 2;
        assert!(validate_request(&req).is_err());
        req.request_id = 1;
        req.version = qchain::VERSION.into();
        assert!(validate_request(&req).is_err());
    }

    #[test]
    fn orphaned_source_request_fails_without_hanging() {
        let (_, source) = fixture();
        let (server, client) = SeqPacket::pair().unwrap();
        drop(client);
        assert!(serve_one(&server, &source).is_err());
    }

    #[test]
    fn orphaned_receiver_fails_without_hanging() {
        let (req, _) = fixture();
        let (server, client) = SeqPacket::pair().unwrap();
        drop(server);
        assert!(receive_one(&client, &req).is_err());
    }

    #[test]
    fn malformed_request_and_fd_injection_are_rejected() {
        let (_, source) = fixture();
        let (server, client) = SeqPacket::pair().unwrap();
        let worker = thread::spawn(move || serve_one(&server, &source));
        client.send(b"{broken", &[]).unwrap();
        assert!(worker.join().unwrap().is_err());

        let (req, source) = fixture();
        let (server, client) = SeqPacket::pair().unwrap();
        let worker = thread::spawn(move || serve_one(&server, &source));
        let injected_fd = sealed_memfd("cp-h-request-fd", &[1]).unwrap();
        client
            .send(&serde_json::to_vec(&req).unwrap(), &[injected_fd.as_fd()])
            .unwrap();
        assert_eq!(
            worker.join().unwrap().unwrap_err(),
            "GPU_REQUEST_UNEXPECTED_FDS"
        );
    }

    #[test]
    fn pixel_alpha_and_mismatched_source_hash_are_rejected() {
        let (req, mut source) = fixture();
        source.pixels[3] = 0;
        assert_eq!(source.validate().unwrap_err(), "GPU_SOURCE_FRAME_INVALID");

        let (_, mut source) = fixture();
        source.pixels[0] ^= 1;
        let (server, client) = SeqPacket::pair().unwrap();
        let worker = thread::spawn(move || serve_one(&server, &source));
        client
            .send(&serde_json::to_vec(&req).unwrap(), &[])
            .unwrap();
        assert_eq!(
            worker.join().unwrap().unwrap_err(),
            "GPU_SOURCE_BINDING_MISMATCH"
        );
    }

    #[test]
    fn one_missing_or_two_extra_response_descriptors_are_rejected() {
        let (req, _) = fixture();
        for count in [0, 2] {
            let (server, client) = SeqPacket::pair().unwrap();
            let request = req.clone();
            let worker = thread::spawn(move || {
                let packet = server.recv().unwrap();
                assert!(!packet.bytes.is_empty());
                let fd1 = sealed_memfd("cp-h-1", &[255; 64]).unwrap();
                let fd2 = sealed_memfd("cp-h-2", &[255; 64]).unwrap();
                let all = [fd1.as_fd(), fd2.as_fd()];
                server
                    .send(
                        &serde_json::to_vec(&metadata(&request)).unwrap(),
                        &all[..count],
                    )
                    .unwrap();
            });
            assert_eq!(
                receive_one(&client, &req).err().unwrap(),
                "GPU_EXPECTS_EXACTLY_ONE_MEMFD"
            );
            worker.join().unwrap();
        }
    }

    #[test]
    fn unsealed_response_memfd_is_rejected() {
        let (req, _) = fixture();
        let (server, client) = SeqPacket::pair().unwrap();
        let expected = req.clone();
        let worker = thread::spawn(move || {
            server.recv().unwrap();
            let fd = memfd_with("cp-h-unsealed", &[255; PIXEL_BYTES as usize], false).unwrap();
            server
                .send(
                    &serde_json::to_vec(&metadata(&expected)).unwrap(),
                    &[fd.as_fd()],
                )
                .unwrap();
        });
        assert!(receive_one(&client, &req)
            .unwrap_err()
            .starts_with("GPU_MEMFD_REJECTED"));
        worker.join().unwrap();
    }

    #[test]
    fn truncated_and_oversized_sealed_memfds_are_rejected() {
        for offset in [-4_i64, 4_i64] {
            let (req, _) = fixture();
            let (server, client) = SeqPacket::pair().unwrap();
            let expected = req.clone();
            let worker = thread::spawn(move || {
                server.recv().unwrap();
                let len = (PIXEL_BYTES as i64 + offset) as usize;
                let fd = sealed_memfd("cp-h-wrong-size", &vec![255; len]).unwrap();
                server
                    .send(
                        &serde_json::to_vec(&metadata(&expected)).unwrap(),
                        &[fd.as_fd()],
                    )
                    .unwrap();
            });
            assert_eq!(
                receive_one(&client, &req).unwrap_err(),
                "GPU_MEMFD_SIZE_NOT_EXACT"
            );
            worker.join().unwrap();
        }
    }

    #[test]
    fn forged_response_claims_are_rejected() {
        let (req, _) = fixture();
        for which in 0..5 {
            let mut meta = metadata(&req);
            match which {
                0 => meta.gpu_qualified = true,
                1 => meta.compositor_observed = true,
                2 => meta.dispatches_per_frame = 0,
                3 => meta.scene_sha256 = qchain::digest(b"other-scene"),
                _ => meta.rgba_sha256 = qchain::digest(b"other-image"),
            }
            assert_eq!(
                validate(&req, &meta).unwrap_err(),
                "GPU_FRAME_CONTRACT_MISMATCH"
            );
        }
    }

    #[test]
    fn repeated_new_connections_remain_valid() {
        for _ in 0..64 {
            let (req, source) = fixture();
            let (server, client) = SeqPacket::pair().unwrap();
            let worker = thread::spawn(move || serve_one(&server, &source).unwrap());
            let (meta, mapped) = receive_one(&client, &req).unwrap();
            assert_eq!(meta.rgba_sha256, qchain::digest(mapped.bytes()));
            worker.join().unwrap();
        }
    }

    #[test]
    fn semantic_identity_cannot_be_replaced_by_equal_pixels() {
        let (req, mut source) = fixture();
        source.semantic_digest = "112234".into();
        let (server, client) = SeqPacket::pair().unwrap();
        let worker = thread::spawn(move || serve_one(&server, &source));
        client
            .send(&serde_json::to_vec(&req).unwrap(), &[])
            .unwrap();
        assert_eq!(
            worker.join().unwrap().unwrap_err(),
            "GPU_SOURCE_BINDING_MISMATCH"
        );
    }
}
