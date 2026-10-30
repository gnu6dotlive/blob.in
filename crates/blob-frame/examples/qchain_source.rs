//! Opt-in five-scene local CPU source. Never connects to resident renderd.
use blob_frame::{
    qchain::{self, SourceFrame},
    SeqListener,
};
use std::{env, fs, path::PathBuf};

fn field(text: &str, name: &str) -> Result<String, String> {
    text.lines()
        .find_map(|x| x.strip_prefix(&format!("{name}=")))
        .map(str::to_owned)
        .ok_or_else(|| format!("MISSING_{name}"))
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = env::args().skip(1);
    let source = PathBuf::from(args.next().ok_or("need private CPU evidence path")?);
    let socket = PathBuf::from(args.next().ok_or("need distinct private socket path")?);
    if args.next().is_some() {
        return Err("too many args".into());
    }
    let listener = SeqListener::bind(&socket)?;
    println!("QCHAIN_SOURCE_READY socket={} stages=5", socket.display());
    for stage in 0..5u64 {
        let stem = format!("scene-{stage:02}");
        let text = fs::read(source.join(format!("{stem}.scene.txt")))?;
        let canon = String::from_utf8(text.clone())?;
        if field(&canon, "epoch")?.parse::<u64>()? != stage {
            return Err("SOURCE_EPOCH_NOT_CANONICAL".into());
        }
        let rgba = fs::read(source.join(format!("{stem}.f4-rgba.bin")))?;
        let frame = SourceFrame {
            scene_revision: stage,
            scene_sha256: qchain::digest(&text),
            semantic_digest: field(&canon, "digest")?,
            pixels: rgba,
        };
        frame.validate()?;
        let conn = listener.accept()?;
        qchain::serve_one(&conn, &frame)?;
        println!(
            "QCHAIN_SOURCE_TRANSMITTED stage={stage} sha256={}",
            qchain::digest(&frame.pixels)
        );
    }
    println!("QCHAIN_SOURCE_COMPLETE real_f4_frames=5");
    Ok(())
}
