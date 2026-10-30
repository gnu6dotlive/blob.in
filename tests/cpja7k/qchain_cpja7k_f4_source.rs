//! Bounded CPI02 GPU compute producer, binary stdout frames (not a CPU image replay).
use blobin_f2_topology::qualification_trace;
use blobin_f3_material_height::{Material, Params};
use blobin_f4_effects::{gpu_session::PersistentSession, Plan, Rect};
use std::{
    env, fs::File,
    io::{self, Write},
    time::Instant,
};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let n: usize = env::args().nth(1).ok_or("FRAMES_MISSING")?.parse()?;
    if env::var("CPJA7K_COPY_TIMESTAMPS").as_deref()!=Ok("1") {
        return Err("CPJA7K_REAL_COPY_TIMESTAMP_FEATURE_NOT_ENABLED".into());
    }
    if env::var("CPJA7JC_F4_TIMESTAMPS").as_deref()!=Ok("1") {
        return Err("CPJA7JC_F4_TIMESTAMP_FEATURE_NOT_ENABLED".into());
    }
    let file_path=env::var("CPJA7JC_GPU_QUERY_RAW_PATH")
        .map_err(|_|"CPJA7JC_RAW_QUERY_PATH_REQUIRED")?;
    let mut f4_queries=File::create(file_path)?;
    let mut last_period_ns=None;
    if !(300..=4800).contains(&n) {
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
        let render_started=Instant::now();
        let output = gpu.render_next(scene, params, &plan)?;
        let compute_readback_host_us=render_started.elapsed().as_micros();
        let ticks_raw=output.cpja7jc_gpu_query_raw.as_deref()
            .ok_or("CPJA7JC_NO_REAL_GPU_QUERY_FROM_F4")?;
        if ticks_raw.len()!=144 {
            return Err("CPJA7JC_F4_GPU_QUERY_RAW_LENGTH_INVALID".into());
        }
        let period=output.cpja7jc_gpu_timestamp_period_ns
            .ok_or("CPJA7JC_F4_GPU_TIMESTAMP_PERIOD_MISSING")?;
        if !period.is_finite()||period<=0.0 {
            return Err("CPJA7JC_F4_GPU_TIMESTAMP_PERIOD_INVALID".into());
        }
        last_period_ns=Some(period);
        let ticks=ticks_raw.chunks_exact(8)
            .map(|v|u64::from_le_bytes(v.try_into().unwrap()))
            .collect::<Vec<_>>();
        let mut ns=[0.0_f64;6];
        for index in 0..6 {
            let a=ticks[index*2];
            let b=ticks[index*2+1];
            if b<=a{return Err("CPJA7JC_NEGATIVE_F4_GPU_QUERY".into());}
            ns[index]=((b-a) as f64)*f64::from(period);
        }
        let mut copy_ns=[0.0_f64;3];
        for index in 0..3 {
            let a=ticks[12+index*2];
            let b=ticks[12+index*2+1];
            if b<=a{return Err("CPJA7K_NEGATIVE_GPU_COPY_TIMESTAMP".into());}
            copy_ns[index]=((b-a) as f64)*f64::from(period);
        }
        eprintln!("CPJA7K_F4_GPU_COPY_TIMING seq={seq} period_ns={period} rgba_ns={:.0} mask_ns={:.0} fields_ns={:.0}",
            copy_ns[0],copy_ns[1],copy_ns[2]);
        f4_queries.write_all(ticks_raw)?;
        let wait_us=output.cpja7jc_host_readback_wait_us
            .ok_or("CPJA7JC_HOST_READBACK_WAIT_MISSING")?;
        eprintln!("CPJA7JC_F4_KERNEL_TIMING seq={seq} period_ns={period} f2_ns={:.0} f3_ns={:.0} shadow_ns={:.0} blur_ns={:.0} bloom_ns={:.0} echo_ns={:.0} host_readback_wait_us={} inclusive_render_next_us={}",
            ns[0],ns[1],ns[2],ns[3],ns[4],ns[5],wait_us,compute_readback_host_us);
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
        let pipe_started=Instant::now();
        pipe.write_all(b"QCI02v1!")?;
        pipe.write_all(&(seq as u32).to_le_bytes())?;
        pipe.write_all(&(stage as u32).to_le_bytes())?;
        pipe.write_all(&(variant as u32).to_le_bytes())?;
        pipe.write_all(&(output.rgba.len() as u32).to_le_bytes())?;
        pipe.write_all(&output.rgba)?;
        pipe.flush()?;
        println_timing_on_stderr(seq,compute_readback_host_us,pipe_started.elapsed().as_micros());
        if seq % 30 == 0 {
            eprintln!("CPJA7G_GPU_COMPUTED seq={seq} stage={stage} backend=Vulkan dispatches=6 submissions=1");
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
    f4_queries.flush()?;
    eprintln!("CPJA7K_F4_QUERY_STREAM_COMPLETE frames={n} records={n} gpu_queries={} query_bytes={} period_ns={}",
        n*18,n*144,last_period_ns.ok_or("CPJA7K_NO_GPU_PERIOD")?);
    eprintln!("CPJA7G_GPU_STREAM_COMPLETE frames={n} device=1 pipelines=3 buffers=5 dispatches_per_frame=6 queue_submissions_per_frame=1");
    Ok(())
}

fn println_timing_on_stderr(seq:usize,compute_readback_host_us:u128,pipe_write_us:u128) {
    eprintln!("CPJA7H_ENGINE_TIMING seq={} compute_readback_host_us={} pipe_write_us={}",
        seq,compute_readback_host_us,pipe_write_us);
}
