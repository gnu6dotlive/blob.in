use blob_frame::{
    qchain::{self, SceneRequest, SourceFrame},
    SeqPacket,
};
use std::{fs, path::PathBuf, thread};
fn evidence() -> PathBuf {
    PathBuf::from(std::env::var("QCHAIN_EVIDENCE_ROOT").expect("QCHAIN_EVIDENCE_ROOT required"))
}
#[test]
#[ignore = "needs QCHAIN_EVIDENCE_ROOT: the F4 frames of the runtime, kept outside this repository; run with --ignored"]
fn real_five_f4_frames_roundtrip_over_sealed_seqpacket() {
    let dir = evidence();
    for stage in 0..5u64 {
        let stem = format!("scene-{stage:02}");
        let canonical = fs::read(dir.join(format!("{stem}.scene.txt"))).unwrap();
        let rgba = fs::read(dir.join(format!("{stem}.f4-rgba.bin"))).unwrap();
        let text = String::from_utf8(canonical.clone()).unwrap();
        let epoch = text
            .lines()
            .find_map(|x| x.strip_prefix("epoch="))
            .unwrap()
            .parse::<u64>()
            .unwrap();
        let semantic = text
            .lines()
            .find_map(|x| x.strip_prefix("digest="))
            .unwrap()
            .to_owned();
        assert_eq!(epoch, stage);
        let scene_sha = qchain::digest(&canonical);
        let rgba_sha = qchain::digest(&rgba);
        let req = SceneRequest {
            version: qchain::VERSION.into(),
            request_id: stage + 1,
            scene_revision: stage,
            scene_sha256: scene_sha.clone(),
            expected_rgba_sha256: rgba_sha.clone(),
            semantic_digest: semantic.clone(),
        };
        let source = SourceFrame {
            scene_revision: stage,
            scene_sha256: scene_sha,
            semantic_digest: semantic,
            pixels: rgba.clone(),
        };
        let (server, client) = SeqPacket::pair().unwrap();
        let worker = thread::spawn(move || qchain::serve_one(&server, &source));
        let (meta, mapped) = qchain::receive_one(&client, &req).unwrap();
        worker.join().unwrap().unwrap();
        assert_eq!(mapped.bytes(), rgba.as_slice());
        assert_eq!(meta.rgba_sha256, rgba_sha);
        assert_eq!(meta.buffer_bytes, qchain::PIXEL_BYTES);
        assert!(!meta.gpu_qualified && !meta.compositor_observed);
    }
}
#[test]
#[ignore = "needs QCHAIN_EVIDENCE_ROOT: the F4 frames of the runtime, kept outside this repository; run with --ignored"]
fn real_evidence_wrong_pixel_hash_is_rejected() {
    let dir = evidence();
    let scene = fs::read(dir.join("scene-02.scene.txt")).unwrap();
    let rgba = fs::read(dir.join("scene-02.f4-rgba.bin")).unwrap();
    let semantic = String::from_utf8(scene.clone())
        .unwrap()
        .lines()
        .find_map(|x| x.strip_prefix("digest="))
        .unwrap()
        .to_owned();
    let source = SourceFrame {
        scene_revision: 2,
        scene_sha256: qchain::digest(&scene),
        semantic_digest: semantic.clone(),
        pixels: rgba,
    };
    let req = SceneRequest {
        version: qchain::VERSION.into(),
        request_id: 40,
        scene_revision: 2,
        scene_sha256: source.scene_sha256.clone(),
        expected_rgba_sha256: qchain::digest(b"forged"),
        semantic_digest: semantic,
    };
    let (server, client) = SeqPacket::pair().unwrap();
    let worker = thread::spawn(move || qchain::serve_one(&server, &source));
    client
        .send(&serde_json::to_vec(&req).unwrap(), &[])
        .unwrap();
    assert!(worker.join().unwrap().is_err());
}
