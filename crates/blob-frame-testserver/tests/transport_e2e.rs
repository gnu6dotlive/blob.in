//! Client ↔ test server over a real SEQPACKET socket in a private directory.

mod common;

use std::sync::mpsc;
use std::time::Duration;

use blob_frame::{
    decode_server, encode, Backend, Client, ClientConfig, ClientEvent, ClientMessage, RenderRequest, SeqPacket,
    ServerMessage, ViewMode,
};
use blob_frame_testserver::{serve, testcard, Fault, ServerConfig, SERVER_NAME};
use common::Harness;

#[test]
fn valid_frames_all_modes_and_backends() {
    let mut h = Harness::start(ServerConfig::default());
    let s = h.connected();
    assert_eq!(s.server, SERVER_NAME);
    for backend in Backend::ALL {
        for mode in ViewMode::ALL {
            let r = h.request(301, 167, backend, mode);
            let f = h.expect_frame(&r);
            assert_eq!((f.meta.backend_actual, f.meta.view_mode), (backend, mode));
        }
    }
}

#[test]
fn sizes_at_the_limits_and_revision_barcode() {
    let mut h = Harness::start(ServerConfig::default());
    h.connected();
    for (w, hh) in [(16, 16), (17, 999), (1024, 1024), (1024, 16), (640, 480)] {
        let r = h.request(w, hh, Backend::Cpu, ViewMode::Distance);
        let f = h.expect_frame(&r);
        assert_eq!((f.meta.width_px, f.meta.height_px), (w, hh));
        if w >= 160 && hh >= 40 {
            let rev = testcard::decode_revision(f.pixels.bytes(), f.meta.stride_bytes, w, hh).unwrap();
            assert_eq!(rev as u64, r.scene_revision);
        }
    }
}

#[test]
fn invalid_requests_are_refused_without_a_round_trip() {
    let mut h = Harness::start(ServerConfig::default());
    h.connected();
    for (w, hh) in [(0, 10), (15, 100), (1025, 16), (16, 2000)] {
        let r = h.request(w, hh, Backend::Cpu, ViewMode::Distance);
        match h.next() {
            ClientEvent::RequestFailed { request_id, reason } => {
                assert_eq!(request_id, r.request_id);
                assert!(reason.contains("refused locally"), "{reason}");
            }
            other => panic!("{other:?}"),
        }
    }
    let mut r = RenderRequest::new(0, 1, (64, 64), Backend::Cpu, ViewMode::Lit, common::scene());
    h.client.render(r.clone());
    assert!(matches!(h.next(), ClientEvent::RequestFailed { request_id: 0, .. }), "id 0 is reserved");
    r.request_id = 99;
    r.primitives[1].x = 2.5;
    h.client.render(r);
    assert!(matches!(h.next(), ClientEvent::RequestFailed { request_id: 99, .. }));
    let ok = h.request(64, 64, Backend::Cpu, ViewMode::Distance);
    h.expect_frame(&ok);
}

#[test]
fn server_side_rejection_matches_renderd() {
    // Talk to the server directly, bypassing the client's local checks.
    let mut cfg = ServerConfig::default();
    cfg.failing.push(Backend::Cuda);
    let (a, b) = SeqPacket::pair().unwrap();
    std::thread::spawn(move || serve(b, &cfg));
    let ask = |m: &[u8]| {
        a.send(m, &[]).unwrap();
        decode_server(&a.recv().unwrap().bytes).unwrap()
    };
    let send = |m: &ClientMessage| ask(&encode(m).unwrap());
    assert!(matches!(send(&ClientMessage::hello()), ServerMessage::Hello { .. }));
    assert!(matches!(send(&ClientMessage::capabilities()), ServerMessage::Capabilities(_)));
    let r = RenderRequest::new(5, 6, (64, 64), Backend::Cuda, ViewMode::Lit, common::scene());
    match send(&ClientMessage::RenderRequest(r.clone())) {
        ServerMessage::RenderError(e) => assert_eq!((e.request_id, e.scene_revision, e.reason.as_str()), (5, 6, "RENDER_FAILED")),
        m => panic!("{m:?}"),
    }
    let mut bad = r;
    bad.width_px = 4;
    for m in [
        encode(&ClientMessage::RenderRequest(bad)).unwrap(),
        br#"{"version":"BLOB-FRAME-v2","type":"PING"}"#.to_vec(),
        br#"{"version":"BLOB-FRAME-v1","type":"PING","x":1}"#.to_vec(),
        b"garbage".to_vec(),
    ] {
        match ask(&m) {
            ServerMessage::RenderError(e) => assert_eq!((e.request_id, e.reason.as_str()), (0, "INVALID_CONTROL_MESSAGE")),
            m => panic!("{m:?}"),
        }
    }
    assert!(matches!(send(&ClientMessage::ping()), ServerMessage::Pong { .. }));
}

#[test]
fn failing_backend_is_reported_never_substituted() {
    let mut cfg = ServerConfig::default();
    cfg.failing.push(Backend::Vulkan);
    let mut h = Harness::start(cfg);
    h.connected();
    let r = h.request(64, 64, Backend::Vulkan, ViewMode::Distance);
    match h.next() {
        ClientEvent::RenderError { request_id, error } => {
            assert_eq!((request_id, error.reason.as_str()), (Some(r.request_id), "RENDER_FAILED"))
        }
        other => panic!("{other:?}"),
    }
    let r = h.request(64, 64, Backend::Cpu, ViewMode::Distance);
    h.expect_frame(&r);
}

#[test]
fn unconfigured_cuda_is_not_offered() {
    let mut cfg = ServerConfig::default();
    cfg.capabilities.cuda_configured = false;
    let mut h = Harness::start(cfg);
    let s = h.connected();
    assert!(!s.capabilities.backend_offered(Backend::Cuda));
    let r = h.request(64, 64, Backend::Cuda, ViewMode::Distance);
    match h.next() {
        ClientEvent::RequestFailed { request_id, reason } => {
            assert_eq!(request_id, r.request_id);
            assert!(reason.contains("cuda"), "{reason}");
        }
        other => panic!("{other:?}"),
    }
}

#[test]
fn one_request_at_a_time() {
    let mut h = Harness::start(ServerConfig { delay: Duration::from_millis(100), ..ServerConfig::default() });
    h.connected();
    let r1 = h.request(64, 64, Backend::Cpu, ViewMode::Distance);
    let r2 = h.request(64, 64, Backend::Cpu, ViewMode::Distance);
    match h.next() {
        ClientEvent::RequestFailed { request_id, reason } => {
            assert_eq!(request_id, r2.request_id);
            assert!(reason.contains("one at a time"), "{reason}");
        }
        other => panic!("{other:?}"),
    }
    h.expect_frame(&r1);
}

fn faulty(fault: Fault) -> ServerConfig {
    ServerConfig { fault, fault_every: 2, ..ServerConfig::default() }
}

#[test]
fn bad_frames_are_rejected_and_the_session_survives() {
    for fault in [
        Fault::WrongSize,
        Fault::Truncated,
        Fault::Unsealed,
        Fault::BackendMismatch,
        Fault::WrongRevision,
        Fault::PaddedStride,
        Fault::BadFormat,
        Fault::BadDigest,
        Fault::ExtraDescriptor,
        Fault::NoDescriptor,
    ] {
        let mut h = Harness::start(faulty(fault));
        let s = h.connected();
        let r1 = h.request(128, 96, Backend::Cuda, ViewMode::Normals);
        h.expect_frame(&r1);
        let r2 = h.request(128, 96, Backend::Cuda, ViewMode::Normals);
        match h.next() {
            ClientEvent::FrameRejected { request_id, reason } => {
                assert_eq!(request_id, r2.request_id, "{fault:?}");
                eprintln!("{fault:?}: {reason}");
            }
            other => panic!("{fault:?}: expected rejection, got {other:?}"),
        }
        let r3 = h.request(128, 96, Backend::Cuda, ViewMode::Normals);
        assert_eq!(h.expect_frame(&r3).session_id, s.id, "{fault:?}: same session");
    }
}

#[test]
fn render_errors_are_attributed_and_the_session_survives() {
    for (fault, reason) in [(Fault::Error, "RENDER_FAILED"), (Fault::Timeout, "WORKER_TIMEOUT")] {
        let mut h = Harness::start(faulty(fault));
        h.connected();
        let r1 = h.request(64, 64, Backend::Cpu, ViewMode::Coverage);
        h.expect_frame(&r1);
        let r2 = h.request(64, 64, Backend::Cpu, ViewMode::Coverage);
        match h.next() {
            ClientEvent::RenderError { request_id, error } => {
                assert_eq!((request_id, error.reason.as_str()), (Some(r2.request_id), reason))
            }
            other => panic!("{other:?}"),
        }
        let r3 = h.request(64, 64, Backend::Cpu, ViewMode::Coverage);
        h.expect_frame(&r3);
    }
}

#[test]
fn session_ending_faults_fail_the_request_disconnect_then_reconnect() {
    for fault in [Fault::Disconnect, Fault::WrongId, Fault::ExtraField, Fault::Oversize, Fault::Malformed] {
        let mut h = Harness::start(faulty(fault));
        let s1 = h.connected();
        let r1 = h.request(64, 64, Backend::Cpu, ViewMode::Lit);
        h.expect_frame(&r1);
        let r2 = h.request(64, 64, Backend::Cpu, ViewMode::Lit);
        match h.next() {
            ClientEvent::RequestFailed { request_id, .. } => assert_eq!(request_id, r2.request_id, "{fault:?}"),
            other => panic!("{fault:?}: {other:?}"),
        }
        match h.next() {
            ClientEvent::Disconnected { session_id, reason } => {
                assert_eq!(session_id, s1.id);
                eprintln!("{fault:?}: {reason}");
            }
            other => panic!("{fault:?}: {other:?}"),
        }
        let s2 = h.connected();
        assert!(s2.id > s1.id, "{fault:?}");
        let r = h.request(64, 64, Backend::Cpu, ViewMode::Lit);
        h.expect_frame(&r);
    }
}

#[test]
fn unanswered_request_times_out_and_resets_the_session() {
    let mut h = Harness::start_with(faulty(Fault::Drop), |mut c| {
        c.request_timeout = Duration::from_millis(300);
        c
    });
    h.connected();
    let r1 = h.request(64, 64, Backend::Cpu, ViewMode::Distance);
    h.expect_frame(&r1);
    let r2 = h.request(64, 64, Backend::Cpu, ViewMode::Distance);
    match h.next() {
        ClientEvent::RequestFailed { request_id, reason } => {
            assert_eq!(request_id, r2.request_id);
            assert!(reason.contains("did not answer"), "{reason}");
        }
        other => panic!("{other:?}"),
    }
    assert!(matches!(h.next(), ClientEvent::Disconnected { .. }));
    h.connected();
}

#[test]
fn ping_is_answered_in_sequence() {
    let mut h = Harness::start(ServerConfig { delay: Duration::from_millis(30), ..ServerConfig::default() });
    h.connected();
    let r = h.request(64, 64, Backend::Cpu, ViewMode::Distance);
    h.client.ping();
    h.expect_frame(&r);
    assert!(matches!(h.next(), ClientEvent::Pong { .. }));
}

#[test]
fn wrong_server_version_is_refused_and_retried() {
    let h = Harness::start(ServerConfig { fault: Fault::BadVersion, ..ServerConfig::default() });
    let mut failures = 0;
    while failures < 2 {
        match h.next() {
            ClientEvent::Connecting { .. } => {}
            ClientEvent::ConnectFailed { reason, .. } => {
                assert!(reason.contains("BLOB-FRAME-v2"), "{reason}");
                failures += 1;
            }
            other => panic!("{other:?}"),
        }
    }
}

#[test]
fn missing_server_is_retried_with_backoff() {
    let dir = common::private_dir("missing");
    std::fs::create_dir(&dir).unwrap();
    std::fs::set_permissions(&dir, std::os::unix::fs::PermissionsExt::from_mode(0o700)).unwrap();
    let (tx, rx) = mpsc::channel();
    let tx = std::sync::Mutex::new(tx);
    let mut cfg = ClientConfig::new(dir.join("render.sock"));
    cfg.reconnect_min = Duration::from_millis(10);
    cfg.reconnect_max = Duration::from_millis(40);
    let mut client = Client::spawn(cfg, move |e| {
        let _ = tx.lock().unwrap().send(e);
    });
    let mut waits = vec![];
    while waits.len() < 4 {
        if let ClientEvent::ConnectFailed { retry_in, .. } = rx.recv_timeout(Duration::from_secs(2)).unwrap() {
            waits.push(retry_in);
        }
    }
    assert_eq!(waits, [10, 20, 40, 40].map(Duration::from_millis));
    client.render(RenderRequest::new(1, 1, (64, 64), Backend::Cpu, ViewMode::Lit, common::scene()));
    loop {
        if let ClientEvent::RequestFailed { request_id: 1, reason } = rx.recv_timeout(Duration::from_secs(2)).unwrap() {
            assert!(reason.contains("not connected"));
            break;
        }
    }
    client.shutdown();
    std::fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn insecure_socket_directory_is_refused() {
    let dir = common::private_dir("insecure");
    std::fs::create_dir(&dir).unwrap();
    std::fs::set_permissions(&dir, std::os::unix::fs::PermissionsExt::from_mode(0o755)).unwrap();
    let (tx, rx) = mpsc::channel();
    let tx = std::sync::Mutex::new(tx);
    let mut client = Client::spawn(ClientConfig::new(dir.join("render.sock")), move |e| {
        let _ = tx.lock().unwrap().send(e);
    });
    loop {
        if let ClientEvent::ConnectFailed { reason, .. } = rx.recv_timeout(Duration::from_secs(2)).unwrap() {
            assert!(reason.contains("insecure"), "{reason}");
            break;
        }
    }
    client.shutdown();
    std::fs::remove_dir_all(&dir).unwrap();
}
