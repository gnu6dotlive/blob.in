//! Isolated BLOB-FRAME-v1 test server.
//!
//! Exists only to exercise the presentation surface independently of the real
//! Render Bridge: it speaks the same wire format as `blobin_renderd`, answers
//! RENDER_REQUEST with a reference test card (see [`testcard`]) and can inject
//! controlled faults. It never evaluates the scene. Every frame carries
//! `qualification: TEST_FIXTURE_NOT_RENDERED` and an all-zero geometry digest,
//! and HELLO names it as a test fixture, so it cannot pass for the runtime.

pub mod testcard;

use std::os::fd::AsFd;
use std::str::FromStr;
use std::time::Duration;

use blob_frame::memfd::{memfd_with, sealed_memfd};
use blob_frame::{
    decode, encode, Backend, Capabilities, ClientMessage, FrameReady, RenderError, RenderRequest, SeqPacket,
    ServerMessage, TransportError, ViewMode, FORMAT_RGBA8_UNORM_OPAQUE, MAX_CONTROL_BYTES, VERSION,
};

pub const SERVER_NAME: &str = "blob-frame-testserver TEST-FIXTURE (no geometry evaluated)";
pub const QUALIFICATION: &str = "TEST_FIXTURE_NOT_RENDERED";
pub const ZERO_DIGEST: &str = "0000000000000000000000000000000000000000000000000000000000000000";

/// A fault applied to every `every`-th RENDER_REQUEST (or to the handshake).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Fault {
    None,
    /// RENDER_ERROR `RENDER_FAILED` for the request.
    Error,
    /// RENDER_ERROR `WORKER_TIMEOUT` for the request.
    Timeout,
    /// Close the connection instead of answering.
    Disconnect,
    /// Never answer (exercises the client request timeout).
    Drop,
    /// FRAME_READY dimensions differ from the request.
    WrongSize,
    /// buffer_bytes claims more than the memfd holds.
    Truncated,
    /// Pixel memfd sent without seals.
    Unsealed,
    /// backend_actual differs from backend_requested (a silent fallback).
    BackendMismatch,
    /// scene_revision differs from the request.
    WrongRevision,
    /// FRAME_READY answers another request_id (sequence violation).
    WrongId,
    /// Rows padded beyond width*4 (the contract requires exact stride).
    PaddedStride,
    /// format other than RGBA8_UNORM_OPAQUE.
    BadFormat,
    /// geometry_sha256 not 64 lowercase hex.
    BadDigest,
    /// FRAME_READY with a field outside the contract.
    ExtraField,
    /// Two descriptors attached.
    ExtraDescriptor,
    /// No descriptor attached.
    NoDescriptor,
    /// Datagram larger than the control limit.
    Oversize,
    /// Datagram that is not JSON.
    Malformed,
    /// HELLO answered with another protocol version.
    BadVersion,
}

impl Fault {
    pub const ALL: [(&'static str, Fault); 20] = [
        ("none", Fault::None),
        ("error", Fault::Error),
        ("timeout", Fault::Timeout),
        ("disconnect", Fault::Disconnect),
        ("drop", Fault::Drop),
        ("wrong-size", Fault::WrongSize),
        ("truncated", Fault::Truncated),
        ("unsealed", Fault::Unsealed),
        ("backend-mismatch", Fault::BackendMismatch),
        ("wrong-revision", Fault::WrongRevision),
        ("wrong-id", Fault::WrongId),
        ("padded-stride", Fault::PaddedStride),
        ("bad-format", Fault::BadFormat),
        ("bad-digest", Fault::BadDigest),
        ("extra-field", Fault::ExtraField),
        ("extra-fd", Fault::ExtraDescriptor),
        ("no-fd", Fault::NoDescriptor),
        ("oversize", Fault::Oversize),
        ("malformed", Fault::Malformed),
        ("bad-version", Fault::BadVersion),
    ];

    pub fn names() -> String {
        Fault::ALL.iter().map(|(n, _)| *n).collect::<Vec<_>>().join(" ")
    }
}

impl FromStr for Fault {
    type Err = String;
    fn from_str(s: &str) -> Result<Self, String> {
        Fault::ALL
            .iter()
            .find(|(n, _)| *n == s)
            .map(|(_, f)| *f)
            .ok_or_else(|| format!("unknown fault {s:?}; one of: {}", Fault::names()))
    }
}

#[derive(Clone, Debug)]
pub struct ServerConfig {
    pub capabilities: Capabilities,
    /// Backends answered with RENDER_FAILED, like renderd when a device is not usable.
    pub failing: Vec<Backend>,
    /// Artificial latency per frame.
    pub delay: Duration,
    pub fault: Fault,
    /// Apply `fault` to requests n where n % fault_every == 0 (1-based).
    pub fault_every: u64,
}

impl Default for ServerConfig {
    fn default() -> Self {
        Self {
            capabilities: Capabilities {
                version: VERSION.into(),
                backends_implemented: Backend::ALL.to_vec(),
                cuda_configured: true,
                view_modes: vec![ViewMode::Lit, ViewMode::Normals, ViewMode::Distance, ViewMode::Coverage],
                max_width_px: 1024,
                max_height_px: 1024,
                max_pixels: 1_048_576,
                device_healthy_now: "TEST_FIXTURE_NO_DEVICE".into(),
            },
            failing: vec![],
            delay: Duration::ZERO,
            fault: Fault::None,
            fault_every: 1,
        }
    }
}

#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct Summary {
    pub requests: u64,
    pub frames: u64,
    pub errors: u64,
    pub faults: u64,
}

fn send(conn: &SeqPacket, msg: &ServerMessage) -> Result<(), TransportError> {
    conn.send(&encode(msg).expect("server messages fit"), &[])
}

fn render_error(request_id: u64, scene_revision: u64, reason: &str) -> ServerMessage {
    ServerMessage::RenderError(RenderError { version: VERSION.into(), request_id, scene_revision, reason: reason.into() })
}

fn frame_meta(req: &RenderRequest, seq: u64) -> FrameReady {
    FrameReady {
        version: VERSION.into(),
        request_id: req.request_id,
        scene_revision: req.scene_revision,
        width_px: req.width_px,
        height_px: req.height_px,
        stride_bytes: req.width_px * 4,
        format: FORMAT_RGBA8_UNORM_OPAQUE.into(),
        buffer_bytes: req.width_px as u64 * 4 * req.height_px as u64,
        backend_requested: req.backend_requested,
        backend_actual: req.backend_requested,
        view_mode: req.view_mode,
        generation: 0,
        qualification: QUALIFICATION.into(),
        cache_hit: false,
        geometry_sha256: ZERO_DIGEST.into(),
        frame_sequence: Some(seq),
    }
}

fn send_frame(conn: &SeqPacket, meta: &FrameReady, pixels: &[u8]) -> Result<(), TransportError> {
    let fd = sealed_memfd("blob-frame-testcard", pixels)?;
    conn.send(&encode(&ServerMessage::FrameReady(meta.clone())).unwrap(), &[fd.as_fd()])
}

/// Serves one connection until the client leaves or a fault closes it.
/// Every client message gets exactly one answer, in order, as with renderd.
pub fn serve(conn: SeqPacket, cfg: &ServerConfig) -> Result<Summary, TransportError> {
    let caps = &cfg.capabilities;
    let mut sum = Summary::default();
    conn.require_same_uid()?;
    loop {
        let pkt = match conn.recv() {
            Ok(p) => p,
            Err(TransportError::Closed) => return Ok(sum),
            Err(e) => return Err(e),
        };
        let msg = match decode::<ClientMessage>(&pkt.bytes) {
            Ok(m) if pkt.fds.is_empty() && m.version() == VERSION => m,
            _ => {
                send(&conn, &render_error(0, 0, "INVALID_CONTROL_MESSAGE"))?;
                continue;
            }
        };
        let req = match msg {
            ClientMessage::Hello { .. } => {
                let version = if cfg.fault == Fault::BadVersion { "BLOB-FRAME-v2" } else { VERSION };
                send(
                    &conn,
                    &ServerMessage::Hello {
                        version: version.into(),
                        server: SERVER_NAME.into(),
                        max_control_bytes: MAX_CONTROL_BYTES as u32,
                    },
                )?;
                continue;
            }
            ClientMessage::Capabilities { .. } => {
                send(&conn, &ServerMessage::Capabilities(caps.clone()))?;
                continue;
            }
            ClientMessage::Ping { .. } => {
                send(&conn, &ServerMessage::Pong { version: VERSION.into() })?;
                continue;
            }
            ClientMessage::RenderRequest(r) => r,
        };
        sum.requests += 1;
        if req.validate(caps).is_err() {
            sum.errors += 1;
            send(&conn, &render_error(0, 0, "INVALID_CONTROL_MESSAGE"))?;
            continue;
        }
        if cfg.failing.contains(&req.backend_requested) || !caps.backend_offered(req.backend_requested) {
            sum.errors += 1;
            send(&conn, &render_error(req.request_id, req.scene_revision, "RENDER_FAILED"))?;
            continue;
        }
        if !cfg.delay.is_zero() {
            std::thread::sleep(cfg.delay);
        }
        let mut meta = frame_meta(&req, sum.frames + 1);
        let mut pixels = testcard::render(&req, meta.stride_bytes);
        if cfg.fault != Fault::None && sum.requests % cfg.fault_every.max(1) == 0 {
            sum.faults += 1;
            log::info!("injecting fault {:?} on request {}", cfg.fault, req.request_id);
            let (id, rev) = (req.request_id, req.scene_revision);
            match cfg.fault {
                Fault::None | Fault::BadVersion => {}
                Fault::Error => {
                    send(&conn, &render_error(id, rev, "RENDER_FAILED"))?;
                    continue;
                }
                Fault::Timeout => {
                    send(&conn, &render_error(id, rev, "WORKER_TIMEOUT"))?;
                    continue;
                }
                Fault::Disconnect => return Ok(sum),
                Fault::Drop => continue,
                Fault::WrongSize => meta.width_px += 1,
                Fault::Truncated => meta.buffer_bytes += 4096,
                Fault::BackendMismatch => {
                    meta.backend_actual = if req.backend_requested == Backend::Cpu { Backend::Cuda } else { Backend::Cpu }
                }
                Fault::WrongRevision => meta.scene_revision = rev.wrapping_add(1),
                Fault::WrongId => meta.request_id = id.wrapping_add(1000),
                Fault::PaddedStride => {
                    meta.stride_bytes += 64;
                    meta.buffer_bytes = meta.stride_bytes as u64 * meta.height_px as u64;
                    pixels = testcard::render(&req, meta.stride_bytes);
                }
                Fault::BadFormat => meta.format = "BGRA8_UNORM".into(),
                Fault::BadDigest => meta.geometry_sha256 = "Z".repeat(64),
                Fault::ExtraField => {
                    let mut v = serde_json_value(&meta);
                    v.push_str(",\"material\":\"gold\"}");
                    let fd = sealed_memfd("blob-frame-testcard", &pixels)?;
                    conn.send(v.as_bytes(), &[fd.as_fd()])?;
                    continue;
                }
                Fault::Unsealed => {
                    let fd = memfd_with("blob-frame-testcard", &pixels, false)?;
                    conn.send(&encode(&ServerMessage::FrameReady(meta)).unwrap(), &[fd.as_fd()])?;
                    continue;
                }
                Fault::ExtraDescriptor => {
                    let a = sealed_memfd("blob-frame-testcard", &pixels)?;
                    let b = sealed_memfd("blob-frame-extra", &[0; 16])?;
                    conn.send(&encode(&ServerMessage::FrameReady(meta)).unwrap(), &[a.as_fd(), b.as_fd()])?;
                    continue;
                }
                Fault::NoDescriptor => {
                    send(&conn, &ServerMessage::FrameReady(meta))?;
                    continue;
                }
                Fault::Oversize => {
                    conn.send_raw(&vec![b' '; MAX_CONTROL_BYTES + 1], &[])?;
                    continue;
                }
                Fault::Malformed => {
                    conn.send(b"{\"version\":\"BLOB-FRAME-v1\",\"type\":\"FRAME_READY\",", &[])?;
                    continue;
                }
            }
        }
        send_frame(&conn, &meta, &pixels)?;
        sum.frames += 1;
    }
}

/// The FRAME_READY JSON without its closing brace, for appending a field.
fn serde_json_value(meta: &FrameReady) -> String {
    let mut s = String::from_utf8(encode(&ServerMessage::FrameReady(meta.clone())).unwrap()).unwrap();
    s.pop();
    s
}
