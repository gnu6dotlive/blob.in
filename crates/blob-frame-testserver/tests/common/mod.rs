//! Shared harness: a real test server on a private socket plus a real client.
#![allow(dead_code)]

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::mpsc::{self, Receiver};
use std::sync::Arc;
use std::time::Duration;

use blob_frame::{
    Backend, Client, ClientConfig, ClientEvent, CsgOp, Primitive, ReceivedFrame, RenderRequest, SeqListener,
    SeqPacket, Session, ViewMode,
};
use blob_frame_testserver::{serve, testcard, ServerConfig, QUALIFICATION};

static SEQ: AtomicU64 = AtomicU64::new(0);

pub fn private_dir(tag: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "blob-frame-{tag}-{}-{}",
        std::process::id(),
        SEQ.fetch_add(1, Ordering::Relaxed)
    ));
    let _ = std::fs::remove_dir_all(&dir);
    dir
}

pub fn scene() -> Vec<Primitive> {
    vec![
        Primitive { x: 0.0, y: 0.0, radius: 0.3, op: CsgOp::Union },
        Primitive { x: 0.2, y: 0.0, radius: 0.2, op: CsgOp::Subtract },
    ]
}

pub struct Harness {
    dir: PathBuf,
    socket: PathBuf,
    pub events: Receiver<ClientEvent>,
    pub client: Client,
    next_id: u64,
    stop: Arc<AtomicBool>,
    server: Option<std::thread::JoinHandle<()>>,
}

impl Harness {
    pub fn start(cfg: ServerConfig) -> Self {
        Self::start_with(cfg, |c| c)
    }

    pub fn start_with(cfg: ServerConfig, tweak: impl FnOnce(ClientConfig) -> ClientConfig) -> Self {
        let dir = private_dir("e2e");
        let socket = dir.join("render.sock");
        let listener = SeqListener::bind(&socket).unwrap();
        let stop = Arc::new(AtomicBool::new(false));
        let stop2 = stop.clone();
        // Sequential, one client at a time, like the runtime.
        let server = std::thread::spawn(move || {
            while let Ok(conn) = listener.accept() {
                if stop2.load(Ordering::Acquire) {
                    break;
                }
                let _ = serve(conn, &cfg);
            }
        });
        let (tx, events) = mpsc::channel();
        let mut ccfg = ClientConfig::new(socket.clone());
        ccfg.reconnect_min = Duration::from_millis(20);
        ccfg.reconnect_max = Duration::from_millis(100);
        let tx = std::sync::Mutex::new(tx);
        let client = Client::spawn(tweak(ccfg), move |e| {
            let _ = tx.lock().unwrap().send(e);
        });
        Self { dir, socket, events, client, next_id: 0, stop, server: Some(server) }
    }

    pub fn next(&self) -> ClientEvent {
        self.events.recv_timeout(Duration::from_secs(5)).expect("event within 5 s")
    }

    pub fn connected(&self) -> Arc<Session> {
        loop {
            match self.next() {
                ClientEvent::Connected(s) => return s,
                ClientEvent::Connecting { .. } => {}
                other => panic!("expected Connected, got {other:?}"),
            }
        }
    }

    pub fn request(&mut self, w: u32, h: u32, backend: Backend, mode: ViewMode) -> RenderRequest {
        self.next_id += 1;
        let r = RenderRequest::new(self.next_id, self.next_id * 10, (w, h), backend, mode, scene());
        self.client.render(r.clone());
        r
    }

    pub fn expect_frame(&self, req: &RenderRequest) -> Box<ReceivedFrame> {
        match self.next() {
            ClientEvent::Frame(f) => {
                assert_eq!(f.meta.request_id, req.request_id);
                check_pixels(&f);
                f
            }
            other => panic!("expected frame for {}, got {other:?}", req.request_id),
        }
    }
}

impl Drop for Harness {
    fn drop(&mut self) {
        self.client.shutdown();
        self.stop.store(true, Ordering::Release);
        let _ = SeqPacket::connect(&self.socket); // wakes accept()
        if let Some(t) = self.server.take() {
            t.join().unwrap();
        }
        let _ = std::fs::remove_dir_all(&self.dir);
    }
}

pub fn check_pixels(f: &ReceivedFrame) {
    let (w, h, s) = (f.meta.width_px, f.meta.height_px, f.meta.stride_bytes);
    assert_eq!(s, w * 4);
    testcard::verify(f.pixels.bytes(), s, w, h).unwrap();
    if let Some(rev) = testcard::decode_revision(f.pixels.bytes(), s, w, h) {
        assert_eq!(rev as u64, f.meta.scene_revision & 0xffff_ffff);
    }
    assert_eq!(f.meta.qualification, QUALIFICATION);
}

/// Open descriptors of this process.
pub fn open_fds() -> usize {
    std::fs::read_dir("/proc/self/fd").unwrap().count()
}

/// Live mappings of test-card memfds in this process.
pub fn frame_mappings() -> usize {
    std::fs::read_to_string("/proc/self/maps").unwrap().lines().filter(|l| l.contains("blob-frame-")).count()
}
