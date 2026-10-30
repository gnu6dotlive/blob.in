//! Connects to a BLOB-FRAME-v1 runtime with the production client and renders one
//! frame per (backend, view mode). Prints one JSON line per outcome. No pixels are invented.
//!
//! usage: cargo run --example probe -- [SOCKET] [WIDTHxHEIGHT]

use std::sync::mpsc;
use std::time::Duration;

use blob_frame::{Backend, Client, ClientConfig, ClientEvent, CsgOp, Primitive, RenderRequest, ViewMode};

fn main() {
    let mut args = std::env::args().skip(1);
    let socket = args.next().map(Into::into).unwrap_or_else(|| blob_frame::default_socket_path().unwrap());
    let (w, h) = args
        .next()
        .and_then(|s| s.split_once('x').map(|(a, b)| (a.parse().unwrap(), b.parse().unwrap())))
        .unwrap_or((320, 224));
    let (tx, rx) = mpsc::channel();
    let tx = std::sync::Mutex::new(tx);
    let mut client = Client::spawn(ClientConfig::new(socket), move |e| {
        let _ = tx.lock().unwrap().send(e);
    });
    let session = loop {
        match rx.recv_timeout(Duration::from_secs(10)).expect("runtime reachable") {
            ClientEvent::Connected(s) => break s,
            ClientEvent::ConnectFailed { reason, .. } => panic!("connect failed: {reason}"),
            _ => {}
        }
    };
    println!("{}", serde_json::json!({"event":"connected","server":session.server,
        "capabilities":serde_json::to_value(&session.capabilities).unwrap()}));
    let prims = vec![
        Primitive { x: 0.0, y: 0.0, radius: 0.14, op: CsgOp::Union },
        Primitive { x: -0.14, y: -0.05, radius: 0.11, op: CsgOp::SmoothUnion },
        Primitive { x: 0.13, y: 0.07, radius: 0.12, op: CsgOp::SmoothUnion },
        Primitive { x: 0.03, y: -0.11, radius: 0.045, op: CsgOp::Subtract },
    ];
    let mut id = 0;
    let mut cpu: std::collections::HashMap<&str, Vec<u8>> = Default::default();
    for backend in Backend::ALL {
        for mode in ViewMode::ALL {
            id += 1;
            client.render(RenderRequest::new(id, id, (w, h), backend, mode, prims.clone()));
            let line = match rx.recv_timeout(Duration::from_secs(30)).expect("answer") {
                ClientEvent::Frame(f) => {
                    let px = f.pixels.bytes();
                    let opaque = px.chunks_exact(4).all(|p| p[3] == 255);
                    if backend == Backend::Cpu {
                        cpu.insert(mode.as_str(), px.to_vec());
                    }
                    let base = &cpu[mode.as_str()];
                    let diff: Vec<u8> = px.iter().zip(base).map(|(a, b)| a.abs_diff(*b)).collect();
                    let max_diff = diff.iter().copied().max().unwrap_or(0);
                    let differing_px = diff.chunks_exact(4).filter(|p| p.iter().any(|&d| d > 0)).count();
                    serde_json::json!({"event":"frame","request_id":id,"backend":backend.as_str(),"mode":mode.as_str(),
                        "meta":serde_json::to_value(&f.meta).unwrap(),"opaque":opaque,"vs_cpu_max_channel_diff":max_diff,"vs_cpu_differing_px":differing_px,
                        "round_trip_ms":f.round_trip.as_secs_f64()*1e3,
                        "fnv1a64":format!("{:016x}", px.iter().fold(0xcbf29ce484222325u64,|h,b|(h^*b as u64).wrapping_mul(0x100000001b3)))})
                }
                other => serde_json::json!({"event":"other","request_id":id,"backend":backend.as_str(),"mode":mode.as_str(),"detail":format!("{other:?}")}),
            };
            println!("{line}");
        }
    }
    client.ping();
    println!("{}", serde_json::json!({"event":"ping","detail":format!("{:?}", rx.recv_timeout(Duration::from_secs(30)).unwrap())}));
    client.shutdown();
}
