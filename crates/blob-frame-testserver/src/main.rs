use std::path::PathBuf;
use std::process::ExitCode;
use std::time::Duration;

use blob_frame::{default_test_socket_path, Backend, SeqListener};
use blob_frame_testserver::{serve, Fault, ServerConfig};

fn usage() -> String {
    format!(
        "\
blob-frame-testserver — BLOB-FRAME-v1 TEST server
Answers with reference test cards. Evaluates no geometry. Its frames are NOT blob.in output.

USAGE: blob-frame-testserver [OPTIONS]

  --socket PATH        listen path (default $XDG_RUNTIME_DIR/blobin-showcase-test/render.sock)
  --delay-ms N         artificial latency per frame (default 0)
  --fault NAME         inject a fault (see below)
  --fault-every N      apply the fault to every N-th render request (default 1)
  --failing BACKEND    answer cpu|cuda|vulkan requests with RENDER_FAILED (repeatable)
  --no-cuda            advertise cuda_configured=false
  --once               exit after the first connection ends
  -h, --help

FAULTS: {}
",
        Fault::names()
    )
}

fn parse() -> Result<(PathBuf, ServerConfig, bool), String> {
    let mut cfg = ServerConfig::default();
    let mut socket = None;
    let mut once = false;
    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        let mut val = |name: &str| args.next().ok_or_else(|| format!("{name} needs a value"));
        match a.as_str() {
            "--socket" => socket = Some(PathBuf::from(val("--socket")?)),
            "--delay-ms" => {
                cfg.delay = Duration::from_millis(val("--delay-ms")?.parse().map_err(|e| format!("--delay-ms: {e}"))?)
            }
            "--fault" => cfg.fault = val("--fault")?.parse()?,
            "--fault-every" => {
                cfg.fault_every = val("--fault-every")?.parse().map_err(|e| format!("--fault-every: {e}"))?
            }
            "--failing" => {
                let v = val("--failing")?;
                let b = Backend::ALL.into_iter().find(|b| b.as_str() == v).ok_or_else(|| format!("unknown backend {v:?}"))?;
                cfg.failing.push(b);
            }
            "--no-cuda" => cfg.capabilities.cuda_configured = false,
            "--once" => once = true,
            "-h" | "--help" => {
                print!("{}", usage());
                std::process::exit(0);
            }
            other => return Err(format!("unknown argument {other:?}\n\n{}", usage())),
        }
    }
    let socket = match socket {
        Some(s) => s,
        None => default_test_socket_path().map_err(|e| e.to_string())?,
    };
    Ok((socket, cfg, once))
}

fn main() -> ExitCode {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();
    let (socket, cfg, once) = match parse() {
        Ok(v) => v,
        Err(e) => {
            eprintln!("{e}");
            return ExitCode::from(2);
        }
    };
    let listener = match SeqListener::bind(&socket) {
        Ok(l) => l,
        Err(e) => {
            eprintln!("cannot listen on {}: {e}", socket.display());
            return ExitCode::FAILURE;
        }
    };
    log::warn!("TEST SERVER — frames are reference test cards, not blob.in output");
    log::info!(
        "listening on {} fault={:?}/{} delay={:?}",
        listener.path().display(),
        cfg.fault,
        cfg.fault_every,
        cfg.delay
    );
    // One client at a time, like the runtime.
    loop {
        match listener.accept() {
            Ok(conn) => match serve(conn, &cfg) {
                Ok(s) => log::info!("connection ended: {s:?}"),
                Err(e) => log::warn!("connection failed: {e}"),
            },
            Err(e) => log::error!("accept: {e}"),
        }
        if once {
            return ExitCode::SUCCESS;
        }
    }
}
