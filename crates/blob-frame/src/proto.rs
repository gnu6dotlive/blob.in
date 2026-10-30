//! BLOB-FRAME-v1 wire types, bounds and validation, as specified by the runtime
//! owner in `CUDA-05/contracts/BLOB-FRAME-v1.md` (status `01A-runtime-implementation`)
//! and as observed in `blobin_renderd` at commit 823fdbd. Points where the two
//! differ, or where the contract is silent, are listed in `docs/BLOB-FRAME-v1-viewer-notes.md`.
//!
//! One JSON object per SEQPACKET datagram, internally tagged by `"type"`, every
//! message carrying `"version": "BLOB-FRAME-v1"`. Unknown fields are rejected in
//! both directions.

use serde::de::{DeserializeOwned, Error as _};
use serde::{Deserialize, Deserializer, Serialize, Serializer};
use thiserror::Error;

pub const VERSION: &str = "BLOB-FRAME-v1";
pub const MAX_CONTROL_BYTES: usize = 16_384;
pub const MIN_DIMENSION: u32 = 16;
pub const MAX_DIMENSION: u32 = 1024;
pub const MAX_PIXELS: u64 = 1_048_576;
pub const MAX_FRAME_BYTES: u64 = MAX_PIXELS * 4;
pub const MAX_PRIMITIVES: usize = 64;
/// Primitive centres must lie in [-COORD_LIMIT, COORD_LIMIT].
pub const COORD_LIMIT: f32 = 2.0;
/// Radii must lie in (0, MAX_RADIUS].
pub const MAX_RADIUS: f32 = 2.0;
pub const FORMAT_RGBA8_UNORM_OPAQUE: &str = "RGBA8_UNORM_OPAQUE";
/// Smooth-union radius hard-coded in the engine (CUDA-02 `signed_field`, k = 0.08). Not on the wire.
pub const ENGINE_SMOOTH_K: f32 = 0.08;
const MAX_TEXT_BYTES: usize = 128;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Backend {
    Cpu,
    Cuda,
    Vulkan,
}

impl Backend {
    pub const ALL: [Backend; 3] = [Backend::Cpu, Backend::Cuda, Backend::Vulkan];
    pub fn as_str(self) -> &'static str {
        match self {
            Backend::Cpu => "cpu",
            Backend::Cuda => "cuda",
            Backend::Vulkan => "vulkan",
        }
    }
}

/// 2D signed-field visualisations computed by the runtime. `Lit` is derived
/// surface-normal shading, not 3D or physically based rendering.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ViewMode {
    Lit,
    Normals,
    Distance,
    Coverage,
}

impl ViewMode {
    pub const ALL: [ViewMode; 4] = [ViewMode::Distance, ViewMode::Normals, ViewMode::Coverage, ViewMode::Lit];
    pub fn as_str(self) -> &'static str {
        match self {
            ViewMode::Lit => "lit",
            ViewMode::Normals => "normals",
            ViewMode::Distance => "distance",
            ViewMode::Coverage => "coverage",
        }
    }
}

/// Left-fold CSG operator; on the wire `0=union 1=subtraction 2=intersection 3=smooth_union`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum CsgOp {
    Union,
    Subtract,
    Intersect,
    SmoothUnion,
}

impl CsgOp {
    pub const ALL: [CsgOp; 4] = [CsgOp::Union, CsgOp::Subtract, CsgOp::Intersect, CsgOp::SmoothUnion];
    pub fn code(self) -> u32 {
        match self {
            CsgOp::Union => 0,
            CsgOp::Subtract => 1,
            CsgOp::Intersect => 2,
            CsgOp::SmoothUnion => 3,
        }
    }
    pub fn from_code(c: u32) -> Option<Self> {
        Self::ALL.into_iter().find(|o| o.code() == c)
    }
    pub fn as_str(self) -> &'static str {
        match self {
            CsgOp::Union => "union",
            CsgOp::Subtract => "subtraction",
            CsgOp::Intersect => "intersection",
            CsgOp::SmoothUnion => "smooth_union",
        }
    }
}

impl Serialize for CsgOp {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        s.serialize_u32(self.code())
    }
}

impl<'de> Deserialize<'de> for CsgOp {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let c = u32::deserialize(d)?;
        CsgOp::from_code(c).ok_or_else(|| D::Error::custom(format!("unknown op {c}")))
    }
}

/// A circle in engine units: pixel (ix, iy) of a w×h frame samples
/// ((ix + 0.5 - w/2) / min(w, h), (iy + 0.5 - h/2) / min(w, h)); y points down.
#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Primitive {
    pub x: f32,
    pub y: f32,
    pub radius: f32,
    pub op: CsgOp,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RenderRequest {
    pub version: String,
    pub request_id: u64,
    pub scene_revision: u64,
    pub width_px: u32,
    pub height_px: u32,
    pub backend_requested: Backend,
    pub view_mode: ViewMode,
    pub primitives: Vec<Primitive>,
}

impl RenderRequest {
    pub fn new(
        request_id: u64,
        scene_revision: u64,
        (width_px, height_px): (u32, u32),
        backend_requested: Backend,
        view_mode: ViewMode,
        primitives: Vec<Primitive>,
    ) -> Self {
        Self {
            version: VERSION.into(),
            request_id,
            scene_revision,
            width_px,
            height_px,
            backend_requested,
            view_mode,
            primitives,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "SCREAMING_SNAKE_CASE", deny_unknown_fields)]
pub enum ClientMessage {
    Hello { version: String },
    Capabilities { version: String },
    Ping { version: String },
    RenderRequest(RenderRequest),
}

impl ClientMessage {
    pub fn hello() -> Self {
        Self::Hello { version: VERSION.into() }
    }
    pub fn capabilities() -> Self {
        Self::Capabilities { version: VERSION.into() }
    }
    pub fn ping() -> Self {
        Self::Ping { version: VERSION.into() }
    }
    pub fn version(&self) -> &str {
        match self {
            Self::Hello { version } | Self::Capabilities { version } | Self::Ping { version } => version,
            Self::RenderRequest(r) => &r.version,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Capabilities {
    pub version: String,
    /// Implemented, not necessarily device-ready: health is only known after a render.
    pub backends_implemented: Vec<Backend>,
    pub cuda_configured: bool,
    pub view_modes: Vec<ViewMode>,
    pub max_width_px: u32,
    pub max_height_px: u32,
    pub max_pixels: u64,
    pub device_healthy_now: String,
}

impl Capabilities {
    /// Whether a request for `b` can be attempted. A `true` here is not a health claim.
    pub fn backend_offered(&self, b: Backend) -> bool {
        self.backends_implemented.contains(&b) && (b != Backend::Cuda || self.cuda_configured)
    }

    pub fn accepts_size(&self, w: u32, h: u32) -> bool {
        (MIN_DIMENSION..=self.max_width_px).contains(&w)
            && (MIN_DIMENSION..=self.max_height_px).contains(&h)
            && w as u64 * h as u64 <= self.max_pixels
    }

    pub fn validate(&self) -> Result<(), ProtocolError> {
        check_version(&self.version)?;
        if !(MIN_DIMENSION..=MAX_DIMENSION).contains(&self.max_width_px)
            || !(MIN_DIMENSION..=MAX_DIMENSION).contains(&self.max_height_px)
        {
            return Err(invalid("max_width_px/max_height_px outside 16..=1024"));
        }
        let min_px = (MIN_DIMENSION * MIN_DIMENSION) as u64;
        if !(min_px..=MAX_PIXELS).contains(&self.max_pixels) {
            return Err(invalid("max_pixels outside the contract bounds"));
        }
        if self.backends_implemented.is_empty() || self.view_modes.is_empty() {
            return Err(invalid("empty backend or view mode list"));
        }
        check_text("device_healthy_now", &self.device_healthy_now)
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameReady {
    pub version: String,
    pub request_id: u64,
    pub scene_revision: u64,
    pub width_px: u32,
    pub height_px: u32,
    pub stride_bytes: u32,
    pub format: String,
    pub buffer_bytes: u64,
    pub backend_requested: Backend,
    pub backend_actual: Backend,
    pub view_mode: ViewMode,
    /// Gate generation for GPU backends; 0 for CPU (observed in renderd, not in the contract text).
    pub generation: u64,
    /// Verbatim runtime label, e.g. `CUDA05F_GATE_PASS`, `CPU_LOCAL_PREVIEW_NOT_GPU_QUALIFIED`.
    pub qualification: String,
    pub cache_hit: bool,
    pub geometry_sha256: String,
    /// Sent by renderd 823fdbd but absent from the contract text; accepted, displayed, never required.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub frame_sequence: Option<u64>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RenderError {
    pub version: String,
    /// 0 when the error is not tied to a request (e.g. `INVALID_CONTROL_MESSAGE`).
    pub request_id: u64,
    pub scene_revision: u64,
    pub reason: String,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "SCREAMING_SNAKE_CASE", deny_unknown_fields)]
pub enum ServerMessage {
    Hello { version: String, server: String, max_control_bytes: u32 },
    Capabilities(Capabilities),
    Pong { version: String },
    FrameReady(FrameReady),
    RenderError(RenderError),
}

impl ServerMessage {
    pub fn kind(&self) -> &'static str {
        match self {
            Self::Hello { .. } => "HELLO",
            Self::Capabilities(_) => "CAPABILITIES",
            Self::Pong { .. } => "PONG",
            Self::FrameReady(_) => "FRAME_READY",
            Self::RenderError(_) => "RENDER_ERROR",
        }
    }
    pub fn version(&self) -> &str {
        match self {
            Self::Hello { version, .. } | Self::Pong { version } => version,
            Self::Capabilities(c) => &c.version,
            Self::FrameReady(f) => &f.version,
            Self::RenderError(e) => &e.version,
        }
    }
}

#[derive(Debug, Error, PartialEq)]
pub enum ProtocolError {
    #[error("control message is {0} bytes, limit is {MAX_CONTROL_BYTES}")]
    TooLarge(usize),
    #[error("malformed control message: {0}")]
    Malformed(String),
    #[error("invalid value: {0}")]
    Invalid(String),
}

fn invalid(msg: impl Into<String>) -> ProtocolError {
    ProtocolError::Invalid(msg.into())
}

fn check_version(v: &str) -> Result<(), ProtocolError> {
    if v != VERSION {
        return Err(invalid(format!("version {v:?}, expected {VERSION:?}")));
    }
    Ok(())
}

fn check_text(what: &str, s: &str) -> Result<(), ProtocolError> {
    if s.len() > MAX_TEXT_BYTES || s.chars().any(|c| c.is_control()) {
        return Err(invalid(format!("{what} is longer than {MAX_TEXT_BYTES} bytes or has control characters")));
    }
    Ok(())
}

pub fn encode<T: Serialize>(msg: &T) -> Result<Vec<u8>, ProtocolError> {
    let bytes = serde_json::to_vec(msg).map_err(|e| ProtocolError::Malformed(e.to_string()))?;
    if bytes.len() > MAX_CONTROL_BYTES {
        return Err(ProtocolError::TooLarge(bytes.len()));
    }
    Ok(bytes)
}

pub fn decode<T: DeserializeOwned>(bytes: &[u8]) -> Result<T, ProtocolError> {
    if bytes.len() > MAX_CONTROL_BYTES {
        return Err(ProtocolError::TooLarge(bytes.len()));
    }
    serde_json::from_slice(bytes).map_err(|e| ProtocolError::Malformed(e.to_string()))
}

/// Decodes a server datagram and checks its version and free-text fields.
pub fn decode_server(bytes: &[u8]) -> Result<ServerMessage, ProtocolError> {
    let m: ServerMessage = decode(bytes)?;
    check_version(m.version())?;
    match &m {
        ServerMessage::Hello { server, .. } => check_text("server", server)?,
        ServerMessage::RenderError(e) => check_text("reason", &e.reason)?,
        ServerMessage::FrameReady(f) => check_text("qualification", &f.qualification)?,
        ServerMessage::Capabilities(c) => c.validate()?,
        ServerMessage::Pong { .. } => {}
    }
    Ok(m)
}

impl RenderRequest {
    /// Contract bounds plus the session's advertised limits.
    pub fn validate(&self, caps: &Capabilities) -> Result<(), ProtocolError> {
        check_version(&self.version)?;
        if !caps.accepts_size(self.width_px, self.height_px) {
            return Err(invalid(format!(
                "size {}x{} outside runtime limits (16..={} x 16..={}, <= {} px)",
                self.width_px, self.height_px, caps.max_width_px, caps.max_height_px, caps.max_pixels
            )));
        }
        if !caps.view_modes.contains(&self.view_mode) {
            return Err(invalid(format!("view mode {} not offered", self.view_mode.as_str())));
        }
        let p = &self.primitives;
        if p.is_empty() || p.len() > MAX_PRIMITIVES {
            return Err(invalid(format!("{} primitives, contract allows 1..={MAX_PRIMITIVES}", p.len())));
        }
        if p[0].op != CsgOp::Union {
            return Err(invalid("first primitive op must be union"));
        }
        for (i, q) in p.iter().enumerate() {
            let in_range = |v: f32| v.is_finite() && (-COORD_LIMIT..=COORD_LIMIT).contains(&v);
            if !in_range(q.x) || !in_range(q.y) {
                return Err(invalid(format!("primitive {i}: centre outside [-{COORD_LIMIT}, {COORD_LIMIT}]")));
            }
            if !(q.radius.is_finite() && q.radius > 0.0 && q.radius <= MAX_RADIUS) {
                return Err(invalid(format!("primitive {i}: radius outside (0, {MAX_RADIUS}]")));
            }
        }
        Ok(())
    }
}

/// Why a FRAME_READY was not presented.
#[derive(Debug, Error, PartialEq)]
pub enum FrameReject {
    #[error("scene_revision {got} does not match request ({want})")]
    RevisionMismatch { want: u64, got: u64 },
    #[error("frame is {got_w}x{got_h}, request was {want_w}x{want_h}")]
    DimensionMismatch { want_w: u32, want_h: u32, got_w: u32, got_h: u32 },
    #[error("stride {stride} != width*4 ({want})")]
    BadStride { stride: u32, want: u32 },
    #[error("buffer_bytes {got} != stride*height {want}")]
    BadLength { want: u64, got: u64 },
    #[error("format {0:?} is not RGBA8_UNORM_OPAQUE")]
    BadFormat(String),
    #[error("backend {requested} requested but frame reports actual {actual}; never presented as such")]
    BackendMismatch { requested: &'static str, actual: &'static str },
    #[error("frame echoes backend_requested {0}, which is not what was requested")]
    RequestEchoMismatch(&'static str),
    #[error("view mode {requested} requested but frame reports {used}")]
    ViewModeMismatch { requested: &'static str, used: &'static str },
    #[error("geometry_sha256 is not 64 lowercase hex digits")]
    BadDigest,
    #[error("expected exactly one pixel descriptor, got {0}")]
    DescriptorCount(usize),
    #[error("pixel buffer: {0}")]
    Buffer(String),
}

/// Checks FRAME_READY metadata against the request it answers.
pub fn check_frame(meta: &FrameReady, req: &RenderRequest) -> Result<(), FrameReject> {
    if meta.scene_revision != req.scene_revision {
        return Err(FrameReject::RevisionMismatch { want: req.scene_revision, got: meta.scene_revision });
    }
    if meta.width_px != req.width_px || meta.height_px != req.height_px {
        return Err(FrameReject::DimensionMismatch {
            want_w: req.width_px,
            want_h: req.height_px,
            got_w: meta.width_px,
            got_h: meta.height_px,
        });
    }
    if meta.stride_bytes != meta.width_px * 4 {
        return Err(FrameReject::BadStride { stride: meta.stride_bytes, want: meta.width_px * 4 });
    }
    let want = meta.stride_bytes as u64 * meta.height_px as u64;
    if meta.buffer_bytes != want {
        return Err(FrameReject::BadLength { want, got: meta.buffer_bytes });
    }
    if meta.format != FORMAT_RGBA8_UNORM_OPAQUE {
        return Err(FrameReject::BadFormat(meta.format.clone()));
    }
    if meta.backend_requested != req.backend_requested {
        return Err(FrameReject::RequestEchoMismatch(meta.backend_requested.as_str()));
    }
    if meta.backend_actual != req.backend_requested {
        return Err(FrameReject::BackendMismatch {
            requested: req.backend_requested.as_str(),
            actual: meta.backend_actual.as_str(),
        });
    }
    if meta.view_mode != req.view_mode {
        return Err(FrameReject::ViewModeMismatch {
            requested: req.view_mode.as_str(),
            used: meta.view_mode.as_str(),
        });
    }
    let d = meta.geometry_sha256.as_bytes();
    if d.len() != 64 || !d.iter().all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(c)) {
        return Err(FrameReject::BadDigest);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    pub(crate) fn caps() -> Capabilities {
        Capabilities {
            version: VERSION.into(),
            backends_implemented: Backend::ALL.to_vec(),
            cuda_configured: true,
            view_modes: ViewMode::ALL.to_vec(),
            max_width_px: 1024,
            max_height_px: 1024,
            max_pixels: MAX_PIXELS,
            device_healthy_now: "UNVERIFIED_UNTIL_RENDER".into(),
        }
    }

    fn req(n: usize) -> RenderRequest {
        let prims = (0..n)
            .map(|i| Primitive {
                x: -1.987_654_3,
                y: 1.987_654_3,
                radius: 0.012_345_679,
                op: if i == 0 { CsgOp::Union } else { CsgOp::SmoothUnion },
            })
            .collect();
        RenderRequest::new(u64::MAX, u64::MAX, (1024, 1024), Backend::Cuda, ViewMode::Lit, prims)
    }

    #[test]
    fn matches_the_contract_example_byte_for_byte_semantics() {
        let doc = br#"{
          "version": "BLOB-FRAME-v1", "type": "RENDER_REQUEST", "request_id": 101,
          "scene_revision": 7, "width_px": 512, "height_px": 384,
          "backend_requested": "cuda", "view_mode": "lit",
          "primitives": [
            {"x": 0.0, "y": 0.0, "radius": 0.19, "op": 0},
            {"x": 0.07, "y": 0.0, "radius": 0.10, "op": 3}
          ]
        }"#;
        let m: ClientMessage = decode(doc).unwrap();
        let ClientMessage::RenderRequest(r) = &m else { panic!() };
        assert_eq!(r.primitives[1].op, CsgOp::SmoothUnion);
        r.validate(&caps()).unwrap();
        // Compare what goes on the wire (f32 shortest form), not an f64-widened Value.
        let wire: serde_json::Value = serde_json::from_slice(&encode(&m).unwrap()).unwrap();
        assert_eq!(wire, serde_json::from_slice::<serde_json::Value>(doc).unwrap());

        let ready = br#"{
          "version":"BLOB-FRAME-v1", "type":"FRAME_READY", "request_id":101,
          "scene_revision":7, "width_px":512, "height_px":384,
          "stride_bytes":2048, "format":"RGBA8_UNORM_OPAQUE", "buffer_bytes":786432,
          "backend_requested":"cuda", "backend_actual":"cuda", "view_mode":"lit",
          "generation": 1, "qualification":"CUDA05F_GATE_PASS", "cache_hit":false,
          "geometry_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        }"#;
        let ServerMessage::FrameReady(f) = decode_server(ready).unwrap() else { panic!() };
        check_frame(&f, r).unwrap();
    }

    #[test]
    fn accepts_renderd_frame_sequence_and_handshake_shapes() {
        for msg in [
            &br#"{"version":"BLOB-FRAME-v1","type":"HELLO","server":"blobin-cuda05f-render-bridge","max_control_bytes":16384}"#[..],
            br#"{"version":"BLOB-FRAME-v1","type":"CAPABILITIES","backends_implemented":["cpu","cuda","vulkan"],"cuda_configured":true,"view_modes":["lit","normals","distance","coverage"],"max_width_px":1024,"max_height_px":1024,"max_pixels":1048576,"device_healthy_now":"UNVERIFIED_UNTIL_RENDER"}"#,
            br#"{"version":"BLOB-FRAME-v1","type":"PONG"}"#,
            br#"{"version":"BLOB-FRAME-v1","type":"RENDER_ERROR","request_id":0,"scene_revision":0,"reason":"INVALID_CONTROL_MESSAGE"}"#,
            br#"{"version":"BLOB-FRAME-v1","type":"FRAME_READY","request_id":1,"scene_revision":1,"width_px":16,"height_px":16,"stride_bytes":64,"format":"RGBA8_UNORM_OPAQUE","buffer_bytes":1024,"backend_requested":"cpu","backend_actual":"cpu","view_mode":"lit","generation":0,"qualification":"CPU_LOCAL_PREVIEW_NOT_GPU_QUALIFIED","cache_hit":false,"geometry_sha256":"aa","frame_sequence":3}"#,
        ] {
            decode_server(msg).unwrap_or_else(|e| panic!("{e}: {}", String::from_utf8_lossy(msg)));
        }
    }

    #[test]
    fn rejects_wrong_version_unknown_fields_and_types() {
        assert!(decode_server(br#"{"version":"BLOB-FRAME-v2","type":"PONG"}"#).is_err());
        assert!(decode_server(br#"{"version":"BLOB-FRAME-v1","type":"PONG","x":1}"#).is_err());
        assert!(decode_server(br#"{"version":"BLOB-FRAME-v1","type":"SHELL"}"#).is_err());
        assert!(decode_server(b"not json").is_err());
        assert!(decode::<ClientMessage>(br#"{"version":"BLOB-FRAME-v1","type":"PING","nonce":1}"#).is_err());
        assert!(decode::<Primitive>(br#"{"x":0,"y":0,"radius":1,"op":4}"#).is_err());
    }

    #[test]
    fn maximal_request_fits_control_limit() {
        let r = req(MAX_PRIMITIVES);
        r.validate(&caps()).unwrap();
        let b = encode(&ClientMessage::RenderRequest(r)).unwrap();
        assert!(b.len() <= MAX_CONTROL_BYTES, "{}", b.len());
    }

    #[test]
    fn request_validation() {
        let c = caps();
        let ok = req(3);
        ok.validate(&c).unwrap();
        let bad = |f: &dyn Fn(&mut RenderRequest)| {
            let mut r = req(3);
            f(&mut r);
            r.validate(&c).is_err()
        };
        assert!(bad(&|r| r.width_px = 15));
        assert!(bad(&|r| r.width_px = 1025));
        assert!(bad(&|r| r.primitives[0].op = CsgOp::Subtract));
        assert!(bad(&|r| r.primitives[1].x = 2.01));
        assert!(bad(&|r| r.primitives[1].y = f32::NAN));
        assert!(bad(&|r| r.primitives[1].radius = 0.0));
        assert!(bad(&|r| r.primitives[1].radius = 2.5));
        assert!(bad(&|r| r.primitives.clear()));
        assert!(bad(&|r| r.primitives = req(65).primitives));
        assert!(bad(&|r| r.version = "BLOB-FRAME-v2".into()));
        let mut small = c.clone();
        small.view_modes = vec![ViewMode::Lit];
        let mut r = req(1);
        r.view_mode = ViewMode::Normals;
        assert!(r.validate(&small).is_err());
    }

    #[test]
    fn backend_offer_requires_cuda_configured() {
        let mut c = caps();
        c.cuda_configured = false;
        assert!(!c.backend_offered(Backend::Cuda));
        assert!(c.backend_offered(Backend::Vulkan));
    }

    fn frame_for(r: &RenderRequest) -> FrameReady {
        FrameReady {
            version: VERSION.into(),
            request_id: r.request_id,
            scene_revision: r.scene_revision,
            width_px: r.width_px,
            height_px: r.height_px,
            stride_bytes: r.width_px * 4,
            format: FORMAT_RGBA8_UNORM_OPAQUE.into(),
            buffer_bytes: r.width_px as u64 * 4 * r.height_px as u64,
            backend_requested: r.backend_requested,
            backend_actual: r.backend_requested,
            view_mode: r.view_mode,
            generation: 1,
            qualification: "CUDA05F_GATE_PASS".into(),
            cache_hit: false,
            geometry_sha256: "f".repeat(64),
            frame_sequence: None,
        }
    }

    #[test]
    fn frame_checks() {
        let r = req(2);
        let ok = frame_for(&r);
        check_frame(&ok, &r).unwrap();
        let rejects = |f: &dyn Fn(&mut FrameReady)| {
            let mut m = ok.clone();
            f(&mut m);
            check_frame(&m, &r).unwrap_err()
        };
        assert!(matches!(rejects(&|m| m.backend_actual = Backend::Cpu), FrameReject::BackendMismatch { .. }));
        assert!(matches!(rejects(&|m| m.backend_requested = Backend::Cpu), FrameReject::RequestEchoMismatch(_)));
        assert!(matches!(rejects(&|m| m.stride_bytes += 64), FrameReject::BadStride { .. }));
        assert!(matches!(rejects(&|m| m.buffer_bytes -= 1), FrameReject::BadLength { .. }));
        assert!(matches!(rejects(&|m| m.width_px -= 1), FrameReject::DimensionMismatch { .. }));
        assert!(matches!(rejects(&|m| m.scene_revision -= 1), FrameReject::RevisionMismatch { .. }));
        assert!(matches!(rejects(&|m| m.format = "BGRA8".into()), FrameReject::BadFormat(_)));
        assert!(matches!(rejects(&|m| m.view_mode = ViewMode::Coverage), FrameReject::ViewModeMismatch { .. }));
        assert_eq!(rejects(&|m| m.geometry_sha256 = "F".repeat(64)), FrameReject::BadDigest);
    }
}
