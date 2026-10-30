use std::path::PathBuf;
use std::process::ExitCode;

use blob_frame::Backend;
use blobin_showcase::app::{run, Options};
use blobin_showcase::scene::Lab;

const USAGE: &str = "\
blobin-showcase — native Wayland surface for the blob.in Render Bridge (BLOB-FRAME-v1)

USAGE: blobin-showcase [OPTIONS]

  --socket PATH     runtime socket (default $XDG_RUNTIME_DIR/blobin-showcase/render.sock)
  --test-server     use the test server socket ($XDG_RUNTIME_DIR/blobin-showcase-test/render.sock)
  --backend NAME    initial backend: cpu | cuda | vulkan (default cpu)
  --lab N           initial lab 1..6 (default 3, Smooth Lab)
  --size WxH        initial logical window size (default 1280x800)
  --trace PATH      write a JSON-lines event trace
  --exercise        apply a fixed edit sequence, one step per presented frame, then quit (E2E)
  -h, --help
";

fn parse() -> Result<Options, String> {
    let mut socket = None;
    let mut opts = Options {
        socket: PathBuf::new(),
        trace: None,
        lab: Lab::Smooth,
        backend: Backend::Cpu,
        size: (1280, 800),
        exercise: false,
    };
    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        let mut val = |n: &str| args.next().ok_or_else(|| format!("{n} needs a value"));
        match a.as_str() {
            "--socket" => socket = Some(PathBuf::from(val("--socket")?)),
            "--test-server" => socket = Some(blob_frame::default_test_socket_path().map_err(|e| e.to_string())?),
            "--backend" => {
                let v = val("--backend")?;
                opts.backend = Backend::ALL.into_iter().find(|b| b.as_str() == v).ok_or(format!("unknown backend {v:?}"))?;
            }
            "--lab" => {
                let n: usize = val("--lab")?.parse().map_err(|e| format!("--lab: {e}"))?;
                opts.lab = *Lab::ALL.get(n.wrapping_sub(1)).ok_or("--lab expects 1..6")?;
            }
            "--size" => {
                let v = val("--size")?;
                let (w, h) = v.split_once('x').ok_or("--size expects WxH")?;
                opts.size = (w.parse().map_err(|e| format!("--size: {e}"))?, h.parse().map_err(|e| format!("--size: {e}"))?);
            }
            "--trace" => opts.trace = Some(PathBuf::from(val("--trace")?)),
            "--exercise" => opts.exercise = true,
            "-h" | "--help" => {
                print!("{USAGE}");
                std::process::exit(0);
            }
            other => return Err(format!("unknown argument {other:?}\n\n{USAGE}")),
        }
    }
    opts.socket = match socket {
        Some(s) => s,
        None => blob_frame::default_socket_path().map_err(|e| e.to_string())?,
    };
    Ok(opts)
}

fn main() -> ExitCode {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info,wgpu_core=warn,wgpu_hal=warn,naga=warn"))
        .init();
    if std::env::var_os("WAYLAND_DISPLAY").is_none() {
        eprintln!("blobin-showcase is a Wayland client: WAYLAND_DISPLAY is not set");
        return ExitCode::from(2);
    }
    let opts = match parse() {
        Ok(o) => o,
        Err(e) => {
            eprintln!("{e}");
            return ExitCode::from(2);
        }
    };
    match run(opts) {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("blobin-showcase: {e}");
            ExitCode::FAILURE
        }
    }
}
