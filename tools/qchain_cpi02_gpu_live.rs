//! Bounded CPI02 GPU compute producer, binary stdout frames (not a CPU image replay).
use blobin_f2_topology::qualification_trace;
use blobin_f3_material_height::{Material, Params};
use blobin_f4_effects::{gpu_session::PersistentSession, Plan, Rect};
use std::{
    env,
    io::{self, Write},
};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let n: usize = env::args().nth(1).ok_or("FRAMES_MISSING")?.parse()?;
    if !(40..=300).contains(&n) {
        return Err("CPI02_FRAME_COUNT_BOUNDS".into());
    }
    let mut scenes = qualification_trace()?;
    if scenes.len() != 5 {
        return Err("CPI02_SCENE_COUNT".into());
    }
    for s in &mut scenes {
        s.dpr = 2;
    }
    let mut gpu = PersistentSession::new(scenes[0])?;
    let stdout = io::stdout();
    let mut pipe = stdout.lock();
    for seq in 0..n {
        let stage = seq.min(4);
        let variant = if seq < 5 { 0 } else { ((seq - 5) / 12) % 8 };
        let params = Params {
            material: Material::ALL[variant / 2],
            heat_strength: if variant % 2 == 0 { 0.62 } else { 0.18 },
        };
        let scene = scenes[stage];
        let plan = Plan {
            reduced_motion: true,
            dirty: Rect {
                x: 0,
                y: 0,
                w: scene.width(),
                h: scene.height(),
            },
            ..Plan::default()
        };
        let output = gpu.render_next(scene, params, &plan)?;
        if output.rgba.len() != 786432
            || output.compute_dispatches != 6
            || output.queue_submissions != 1
            || output.intermediate_host_transfers != 0
            || output.semantic_digest != scene.digest()
            || !output.adapter.contains("RTX 3070")
        {
            return Err("CPI02_GPU_COMPUTE_INTEGRITY_FAILED".into());
        }
        // Exact 24-byte header. All fields are little-endian.
        pipe.write_all(b"QCI02v1!")?;
        pipe.write_all(&(seq as u32).to_le_bytes())?;
        pipe.write_all(&(stage as u32).to_le_bytes())?;
        pipe.write_all(&(variant as u32).to_le_bytes())?;
        pipe.write_all(&(output.rgba.len() as u32).to_le_bytes())?;
        pipe.write_all(&output.rgba)?;
        pipe.flush()?;
        if seq % 30 == 0 {
            eprintln!("CPI02_GPU_COMPUTED seq={seq} stage={stage} backend=Vulkan");
        }
    }
    let stats = gpu.stats();
    if stats.frames_rendered != n as u64
        || stats.device_creations != 1
        || stats.pipeline_creations != 3
        || stats.reusable_storage_allocations != 5
    {
        return Err("CPI02_GPU_SESSION_NOT_PERSISTENT".into());
    }
    eprintln!("CPI02_GPU_STREAM_COMPLETE frames={n} device=1 pipelines=3 buffers=5");
    Ok(())
}
