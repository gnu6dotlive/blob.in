//! Headless pipeline test: the surface's scheduler and size fitting driven by a
//! storm of viewport changes, over the real client and the test server. No
//! window is needed; the real-window counterpart is `scripts/e2e_hyprland.py`.

use std::sync::mpsc;
use std::time::{Duration, Instant};

use blob_frame::{Client, ClientConfig, ClientEvent, RenderRequest, SeqListener, ViewMode};
use blob_frame_testserver::{serve, testcard, ServerConfig};
use blobin_showcase::scene::{Camera, Lab, SceneState};
use blobin_showcase::scheduler::{fit, Fit, Scheduler, Verdict};

fn start_server(cfg: ServerConfig) -> (std::path::PathBuf, std::path::PathBuf) {
    let dir = std::env::temp_dir().join(format!("blobin-showcase-resize-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    let socket = dir.join("render.sock");
    let listener = SeqListener::bind(&socket).unwrap();
    std::thread::spawn(move || {
        while let Ok(conn) = listener.accept() {
            let _ = serve(conn, &cfg);
        }
    });
    (dir, socket)
}

#[test]
fn resize_storm_is_coalesced_and_ends_on_the_final_size() {
    let (dir, socket) = start_server(ServerConfig { delay: Duration::from_millis(15), ..ServerConfig::default() });
    let (tx, rx) = mpsc::channel();
    let tx = std::sync::Mutex::new(tx);
    let mut client = Client::spawn(ClientConfig::new(socket), move |e| {
        let _ = tx.lock().unwrap().send(e);
    });
    let session = loop {
        if let ClientEvent::Connected(s) = rx.recv_timeout(Duration::from_secs(5)).unwrap() {
            break s;
        }
    };
    let caps = &session.capabilities;
    let scene = SceneState::new(Lab::Csg);
    let mut sched = Scheduler::new();
    let mut presented = Vec::new();
    let mut in_flight_max = 0;
    let mut pending: Option<RenderRequest> = None;

    // 300 viewport changes at ~1 ms intervals, including sizes beyond the
    // runtime limits and below its minimum.
    let sizes: Vec<(u32, u32)> = (0..300u32)
        .map(|i| match i % 50 {
            7 => (10, 600),
            13 => (2560, 1440),
            _ => (400 + (i * 37) % 1500, 300 + (i * 53) % 900),
        })
        .chain([(1253, 777)])
        .collect();
    let final_size = *sizes.last().unwrap();
    let mut viewport = sizes[0];

    let issue = |sched: &mut Scheduler, viewport: (u32, u32), pending: &mut Option<RenderRequest>| {
        if let Fit::Render { w, h, .. } = fit(viewport, caps) {
            if let Some(f) = sched.issue(Instant::now()) {
                let req = RenderRequest::new(
                    f.request_id,
                    f.revision,
                    (w, h),
                    blob_frame::Backend::Cpu,
                    ViewMode::Coverage,
                    scene.to_wire(&Camera::default()).unwrap(),
                );
                *pending = Some(req.clone());
                client.render(req);
            }
        }
    };

    let handle = |e: ClientEvent, sched: &mut Scheduler, pending: &mut Option<RenderRequest>, presented: &mut Vec<(u64, u32, u32)>| match e {
        ClientEvent::Frame(f) => {
            let req = pending.take().expect("a frame answers the pending request");
            assert_eq!(f.meta.request_id, req.request_id);
            assert_eq!((f.meta.width_px, f.meta.height_px), (req.width_px, req.height_px));
            testcard::verify(f.pixels.bytes(), f.meta.stride_bytes, f.meta.width_px, f.meta.height_px).unwrap();
            if sched.on_frame(f.meta.request_id, f.meta.scene_revision) == Verdict::Present {
                presented.push((f.meta.scene_revision, f.meta.width_px, f.meta.height_px));
            }
        }
        other => panic!("unexpected {other:?}"),
    };

    for s in &sizes {
        viewport = *s;
        sched.invalidate();
        issue(&mut sched, viewport, &mut pending);
        in_flight_max = in_flight_max.max(sched.in_flight().map_or(0, |_| 1));
        while let Ok(e) = rx.try_recv() {
            handle(e, &mut sched, &mut pending, &mut presented);
            issue(&mut sched, viewport, &mut pending);
        }
        std::thread::sleep(Duration::from_millis(1));
    }
    // Drain until the final size is on screen.
    let deadline = Instant::now() + Duration::from_secs(10);
    while sched.dirty() || sched.in_flight().is_some() {
        assert!(Instant::now() < deadline, "did not settle");
        let e = rx.recv_timeout(Duration::from_secs(5)).unwrap();
        handle(e, &mut sched, &mut pending, &mut presented);
        issue(&mut sched, viewport, &mut pending);
    }

    let Fit::Render { w, h, .. } = fit(final_size, caps) else { panic!() };
    let last = *presented.last().unwrap();
    assert_eq!((last.1, last.2), (w, h), "final frame matches the final viewport");
    assert_eq!(last.0, sched.revision(), "final frame carries the latest revision");
    assert!(presented.windows(2).all(|p| p[0].0 < p[1].0), "revisions strictly increase");
    assert_eq!(in_flight_max, 1);
    let c = sched.counters;
    assert!(c.issued < sizes.len() as u64 / 2, "{} requests for {} changes", c.issued, sizes.len());
    for (_, w, h) in &presented {
        assert!(caps.accepts_size(*w, *h), "{w}x{h} within runtime limits");
    }
    eprintln!("{} viewport changes -> {} requests, {} presented", sizes.len(), c.issued, c.presented);
    client.shutdown();
    let _ = std::fs::remove_dir_all(dir);
}
