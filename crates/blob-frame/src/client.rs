//! BLOB-FRAME-v1 client session: connects, negotiates, sends requests and
//! delivers validated, mapped frames as events. Never blocks the caller.
//!
//! The runtime answers every client message, sequentially and in order, and
//! accepts one render request at a time. The client therefore matches each
//! response to the oldest unanswered message (a FIFO) and treats anything else
//! as a protocol violation that ends the session.
//!
//! Threads: one supervisor (connect, handshake, writes, timeouts, reconnect)
//! and, per session, one reader. Events reach the caller's sink in causal
//! order: every event of a session precedes its `Disconnected`.

use std::collections::VecDeque;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError, Sender};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

use crate::memfd::MappedFrame;
use crate::proto::{
    check_frame, decode_server, encode, Capabilities, ClientMessage, FrameReady, FrameReject, RenderError,
    RenderRequest, ServerMessage, MAX_CONTROL_BYTES,
};
use crate::transport::{ensure_private_dir, SeqPacket, TransportError};

#[derive(Clone, Debug)]
pub struct ClientConfig {
    pub socket: PathBuf,
    pub handshake_timeout: Duration,
    /// Unanswered after this long: the request fails and the session is reset
    /// (a late answer would desynchronise the in-order matching).
    pub request_timeout: Duration,
    pub reconnect_min: Duration,
    pub reconnect_max: Duration,
}

impl ClientConfig {
    pub fn new(socket: PathBuf) -> Self {
        Self {
            socket,
            handshake_timeout: Duration::from_secs(5),
            // The runtime's own GPU worker timeout is 15 s.
            request_timeout: Duration::from_secs(20),
            reconnect_min: Duration::from_millis(250),
            reconnect_max: Duration::from_secs(4),
        }
    }
}

#[derive(Debug)]
pub struct Session {
    /// Local counter, increases on every successful connection.
    pub id: u64,
    pub server: String,
    pub max_control_bytes: u32,
    pub capabilities: Capabilities,
}

#[derive(Debug)]
pub struct ReceivedFrame {
    pub session_id: u64,
    pub meta: FrameReady,
    pub request: RenderRequest,
    pub pixels: MappedFrame,
    /// Client-measured: request written → FRAME_READY received and mapped.
    pub round_trip: Duration,
}

#[derive(Debug)]
pub enum ClientEvent {
    Connecting { attempt: u32 },
    ConnectFailed { reason: String, retry_in: Duration },
    Connected(Arc<Session>),
    /// Any request outstanding in that session is void.
    Disconnected { session_id: u64, reason: String },
    Frame(Box<ReceivedFrame>),
    /// A FRAME_READY that failed validation. Its descriptor has been closed.
    FrameRejected { request_id: u64, reason: String },
    /// Not sent, refused locally, or timed out.
    RequestFailed { request_id: u64, reason: String },
    /// RENDER_ERROR, attributed to the request it answers when there is one.
    RenderError { request_id: Option<u64>, error: RenderError },
    Pong { rtt: Duration },
}

enum Command {
    Render(RenderRequest),
    Ping,
    Shutdown,
}

type Sink = Arc<dyn Fn(ClientEvent) + Send + Sync>;

pub struct Client {
    tx: Sender<Command>,
    conn: Arc<Mutex<Option<Arc<SeqPacket>>>>,
    thread: Option<JoinHandle<()>>,
}

impl Client {
    pub fn spawn(cfg: ClientConfig, sink: impl Fn(ClientEvent) + Send + Sync + 'static) -> Self {
        let (tx, rx) = mpsc::channel();
        let conn = Arc::new(Mutex::new(None));
        let slot = conn.clone();
        let sink: Sink = Arc::new(sink);
        let thread = std::thread::Builder::new()
            .name("blob-frame-client".into())
            .spawn(move || supervisor(cfg, rx, sink, slot))
            .expect("spawn client thread");
        Self { tx, conn, thread: Some(thread) }
    }

    /// Queues a request. Its outcome always arrives as exactly one of `Frame`,
    /// `FrameRejected`, `RequestFailed`, `RenderError` or the session's `Disconnected`.
    pub fn render(&self, req: RenderRequest) {
        let _ = self.tx.send(Command::Render(req));
    }

    pub fn ping(&self) {
        let _ = self.tx.send(Command::Ping);
    }

    /// Closes the session and joins all threads; descriptors not yet delivered are closed.
    /// Idempotent.
    pub fn shutdown(&mut self) {
        let _ = self.tx.send(Command::Shutdown);
        if let Some(c) = self.conn.lock().unwrap().as_ref() {
            c.shutdown();
        }
        if let Some(t) = self.thread.take() {
            let _ = t.join();
        }
    }
}

impl Drop for Client {
    fn drop(&mut self) {
        self.shutdown();
    }
}

enum Flow {
    Continue,
    Stop,
}

fn supervisor(cfg: ClientConfig, rx: Receiver<Command>, sink: Sink, slot: Arc<Mutex<Option<Arc<SeqPacket>>>>) {
    let mut attempt = 0;
    let mut backoff = cfg.reconnect_min;
    let mut session_id = 0;
    loop {
        attempt += 1;
        sink(ClientEvent::Connecting { attempt });
        match handshake(&cfg, &slot, session_id + 1) {
            Err(reason) => {
                if let Some(c) = slot.lock().unwrap().take() {
                    c.shutdown();
                }
                sink(ClientEvent::ConnectFailed { reason, retry_in: backoff });
                if let Flow::Stop = idle(&rx, &sink, backoff) {
                    return;
                }
                backoff = (backoff * 2).min(cfg.reconnect_max);
            }
            Ok((conn, session)) => {
                session_id = session.id;
                attempt = 0;
                backoff = cfg.reconnect_min;
                let session = Arc::new(session);
                sink(ClientEvent::Connected(session.clone()));
                let flow = run_session(&cfg, &rx, &sink, conn, session);
                slot.lock().unwrap().take();
                if let Flow::Stop = flow {
                    return;
                }
            }
        }
    }
}

/// While disconnected: fail requests immediately, wait out the backoff.
fn idle(rx: &Receiver<Command>, sink: &Sink, wait: Duration) -> Flow {
    let deadline = Instant::now() + wait;
    loop {
        match rx.recv_timeout(deadline.saturating_duration_since(Instant::now())) {
            Ok(Command::Render(r)) => sink(ClientEvent::RequestFailed {
                request_id: r.request_id,
                reason: "not connected to a runtime".into(),
            }),
            Ok(Command::Ping) => {}
            Ok(Command::Shutdown) | Err(RecvTimeoutError::Disconnected) => return Flow::Stop,
            Err(RecvTimeoutError::Timeout) => return Flow::Continue,
        }
    }
}

fn exchange(conn: &SeqPacket, msg: &ClientMessage) -> Result<ServerMessage, String> {
    conn.send(&encode(msg).map_err(|e| e.to_string())?, &[]).map_err(|e| e.to_string())?;
    let pkt = conn.recv().map_err(|e| e.to_string())?;
    if !pkt.fds.is_empty() {
        return Err("protocol violation: descriptor attached to a handshake reply".into());
    }
    decode_server(&pkt.bytes).map_err(|e| format!("protocol violation: {e}"))
}

fn handshake(
    cfg: &ClientConfig,
    slot: &Mutex<Option<Arc<SeqPacket>>>,
    id: u64,
) -> Result<(Arc<SeqPacket>, Session), String> {
    let dir = cfg.socket.parent().ok_or("socket path has no parent directory")?;
    ensure_private_dir(dir, false).map_err(|e| e.to_string())?;
    let conn =
        Arc::new(SeqPacket::connect(&cfg.socket).map_err(|e| format!("connect {}: {e}", cfg.socket.display()))?);
    *slot.lock().unwrap() = Some(conn.clone());
    conn.require_same_uid().map_err(|e| e.to_string())?;
    conn.set_read_timeout(Some(cfg.handshake_timeout)).map_err(|e| e.to_string())?;
    let (server, max_control_bytes) = match exchange(&conn, &ClientMessage::hello())? {
        ServerMessage::Hello { server, max_control_bytes, .. } => {
            if (max_control_bytes as usize) < MAX_CONTROL_BYTES {
                return Err(format!("server control limit {max_control_bytes} below the contract's {MAX_CONTROL_BYTES}"));
            }
            (server, max_control_bytes)
        }
        ServerMessage::RenderError(e) => return Err(format!("runtime refused HELLO: {}", e.reason)),
        other => return Err(format!("protocol violation: expected HELLO, got {}", other.kind())),
    };
    let capabilities = match exchange(&conn, &ClientMessage::capabilities())? {
        ServerMessage::Capabilities(c) => c,
        ServerMessage::RenderError(e) => return Err(format!("runtime refused CAPABILITIES: {}", e.reason)),
        other => return Err(format!("protocol violation: expected CAPABILITIES, got {}", other.kind())),
    };
    conn.set_read_timeout(None).map_err(|e| e.to_string())?;
    Ok((conn, Session { id, server, max_control_bytes, capabilities }))
}

enum Expect {
    Frame { req: RenderRequest, sent: Instant },
    Pong { sent: Instant },
}

impl Expect {
    fn sent(&self) -> Instant {
        match self {
            Expect::Frame { sent, .. } | Expect::Pong { sent } => *sent,
        }
    }
}

struct Shared {
    expect: Mutex<VecDeque<Expect>>,
    done: AtomicBool,
    reason: Mutex<Option<String>>,
}

fn run_session(cfg: &ClientConfig, rx: &Receiver<Command>, sink: &Sink, conn: Arc<SeqPacket>, session: Arc<Session>) -> Flow {
    let shared = Arc::new(Shared { expect: Mutex::new(VecDeque::new()), done: AtomicBool::new(false), reason: Mutex::new(None) });
    let reader = {
        let (conn, shared, sink, session) = (conn.clone(), shared.clone(), sink.clone(), session.clone());
        std::thread::Builder::new()
            .name("blob-frame-reader".into())
            .spawn(move || reader(&conn, &shared, &sink, &session))
            .expect("spawn reader thread")
    };
    let mut local_reason = None;
    let flow = loop {
        if shared.done.load(Ordering::Acquire) {
            break Flow::Continue;
        }
        match rx.recv_timeout(Duration::from_millis(100)) {
            Ok(Command::Render(req)) => {
                let id = req.request_id;
                let fail = |reason: String| sink(ClientEvent::RequestFailed { request_id: id, reason });
                if id == 0 {
                    // 0 is how the runtime reports errors not tied to a request.
                    fail("refused locally: request_id 0 is reserved by this client".into());
                    continue;
                }
                if let Err(e) = req.validate(&session.capabilities) {
                    fail(format!("refused locally: {e}"));
                    continue;
                }
                if !session.capabilities.backend_offered(req.backend_requested) {
                    fail(format!("backend {} is not offered by this runtime", req.backend_requested.as_str()));
                    continue;
                }
                let bytes = match encode(&ClientMessage::RenderRequest(req.clone())) {
                    Ok(b) => b,
                    Err(e) => {
                        fail(format!("refused locally: {e}"));
                        continue;
                    }
                };
                {
                    let mut q = shared.expect.lock().unwrap();
                    if q.iter().any(|e| matches!(e, Expect::Frame { .. })) {
                        drop(q);
                        fail("a render request is already in flight (contract: one at a time)".into());
                        continue;
                    }
                    q.push_back(Expect::Frame { req, sent: Instant::now() });
                }
                if let Err(e) = conn.send(&bytes, &[]) {
                    local_reason = Some(format!("send failed: {e}"));
                    break Flow::Continue;
                }
            }
            Ok(Command::Ping) => {
                shared.expect.lock().unwrap().push_back(Expect::Pong { sent: Instant::now() });
                if let Err(e) = conn.send(&encode(&ClientMessage::ping()).expect("ping encodes"), &[]) {
                    local_reason = Some(format!("send failed: {e}"));
                    break Flow::Continue;
                }
            }
            Ok(Command::Shutdown) | Err(RecvTimeoutError::Disconnected) => {
                local_reason = Some("client shutdown".into());
                break Flow::Stop;
            }
            Err(RecvTimeoutError::Timeout) => {
                let late = shared.expect.lock().unwrap().front().is_some_and(|e| e.sent().elapsed() > cfg.request_timeout);
                if late {
                    local_reason = Some(format!("runtime did not answer within {:?}; session reset", cfg.request_timeout));
                    break Flow::Continue;
                }
            }
        }
    };
    conn.shutdown();
    let _ = reader.join();
    let reason = local_reason
        .or_else(|| shared.reason.lock().unwrap().take())
        .unwrap_or_else(|| "session ended".into());
    for e in shared.expect.lock().unwrap().drain(..) {
        if let Expect::Frame { req, .. } = e {
            sink(ClientEvent::RequestFailed { request_id: req.request_id, reason: reason.clone() });
        }
    }
    sink(ClientEvent::Disconnected { session_id: session.id, reason });
    flow
}

fn reader(conn: &SeqPacket, shared: &Shared, sink: &Sink, session: &Session) {
    let reason = loop {
        let pkt = match conn.recv() {
            Ok(p) => p,
            Err(TransportError::Closed) => break "runtime closed the connection".to_string(),
            Err(e) => break format!("receive failed: {e}"),
        };
        let msg = match decode_server(&pkt.bytes) {
            Ok(m) => m,
            Err(e) => break format!("protocol violation: {e}"),
        };
        if !matches!(msg, ServerMessage::FrameReady(_)) && !pkt.fds.is_empty() {
            break format!("protocol violation: descriptor attached to {}", msg.kind());
        }
        // Check the answer matches the oldest outstanding message before consuming it,
        // so that on a violation the request is still failed by run_session.
        let expect = {
            let mut q = shared.expect.lock().unwrap();
            let violation = match (q.front(), &msg) {
                (None, m) => Some(format!("unsolicited {}", m.kind())),
                (Some(Expect::Frame { req, .. }), ServerMessage::FrameReady(f)) if f.request_id != req.request_id => {
                    Some(format!("FRAME_READY for request {} while {} was outstanding", f.request_id, req.request_id))
                }
                (Some(Expect::Frame { req, .. }), ServerMessage::RenderError(e))
                    if e.request_id != req.request_id && e.request_id != 0 =>
                {
                    Some(format!("RENDER_ERROR for request {} while {} was outstanding", e.request_id, req.request_id))
                }
                (Some(Expect::Frame { .. }), ServerMessage::FrameReady(_) | ServerMessage::RenderError(_)) => None,
                (Some(Expect::Pong { .. }), ServerMessage::Pong { .. } | ServerMessage::RenderError(_)) => None,
                (Some(_), m) => Some(format!("unexpected {} in sequence", m.kind())),
            };
            if let Some(v) = violation {
                break format!("protocol violation: {v}");
            }
            q.pop_front().expect("checked non-empty")
        };
        match (expect, msg) {
            (Expect::Frame { req, sent }, ServerMessage::FrameReady(meta)) => {
                let id = req.request_id;
                match accept_frame(&meta, &req, pkt.fds) {
                    Ok(pixels) => sink(ClientEvent::Frame(Box::new(ReceivedFrame {
                        session_id: session.id,
                        meta,
                        request: req,
                        pixels,
                        round_trip: sent.elapsed(),
                    }))),
                    Err(rej) => sink(ClientEvent::FrameRejected { request_id: id, reason: rej.to_string() }),
                }
            }
            (Expect::Frame { req, .. }, ServerMessage::RenderError(error)) => {
                sink(ClientEvent::RenderError { request_id: Some(req.request_id), error })
            }
            (Expect::Pong { sent }, ServerMessage::Pong { .. }) => sink(ClientEvent::Pong { rtt: sent.elapsed() }),
            (Expect::Pong { .. }, ServerMessage::RenderError(error)) => {
                sink(ClientEvent::RenderError { request_id: None, error })
            }
            _ => unreachable!("pairs checked above"),
        }
    };
    *shared.reason.lock().unwrap() = Some(reason);
    shared.done.store(true, Ordering::Release);
}

fn accept_frame(meta: &FrameReady, req: &RenderRequest, mut fds: Vec<std::os::fd::OwnedFd>) -> Result<MappedFrame, FrameReject> {
    if fds.len() != 1 {
        return Err(FrameReject::DescriptorCount(fds.len()));
    }
    check_frame(meta, req)?;
    MappedFrame::map(fds.pop().unwrap(), meta.buffer_bytes).map_err(|e| FrameReject::Buffer(e.to_string()))
}
