//! CP-H2 bounded single Vulkan-session soak, separate from production.
use blobin_f2_topology::qualification_trace;
use blobin_f3_material_height::{Material, Params};
use blobin_f4_effects::{gpu_session::PersistentSession, Plan, Rect};
use std::{env, fs, path::PathBuf, time::Instant};

fn percentile(values: &[u64], p: f64) -> u64 {
    let mut v = values.to_vec();
    v.sort_unstable();
    let pos = ((v.len() as f64) * p).ceil() as usize;
    v[pos.saturating_sub(1).min(v.len() - 1)]
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = env::args().skip(1);
    let canonical = PathBuf::from(args.next().ok_or("CPH2_CANONICAL_ROOT_REQUIRED")?);
    let output = PathBuf::from(args.next().ok_or("CPH2_FRESH_OUTPUT_REQUIRED")?);
    let frames: usize = args.next().ok_or("CPH2_FRAME_COUNT_REQUIRED")?.parse()?;
    if args.next().is_some() || frames < 40 || frames > 5000 {
        return Err("CPH2_FRAME_COUNT_OUT_OF_BOUNDS".into());
    }
    if !output.is_dir() || output.read_dir()?.next().is_some() {
        return Err("CPH2_OUTPUT_DIRECTORY_NOT_EMPTY".into());
    }
    let mut scenes = qualification_trace()?;
    if scenes.len() != 5 {
        return Err("CPH2_EXPECTED_FIVE_CANONICAL_SCENES".into());
    }
    for scene in &mut scenes {
        scene.dpr = 2;
    }
    let mut session = PersistentSession::new(scenes[0])?;
    let mut durations = Vec::<u64>::with_capacity(frames);
    let mut expected_final = Vec::new();
    for material in Material::ALL {
        let mut options = Vec::new();
        for frame in 0..2 {
            let stem = format!("state4-{}-frame{frame}-dpr2.gpu-rgba.bin", material.name());
            options.push(fs::read(canonical.join(stem))?);
        }
        expected_final.push(options);
    }

    let masks = (0..5)
        .map(|i| fs::read(canonical.join(format!("scene-{i:02}.gpu-f2-mask.bin"))))
        .collect::<Result<Vec<_>, _>>()?;
    let mut rejected = 0u64;
    for i in 0..frames {
        let stage = i.min(4);
        let scene = scenes[stage];
        let (material, heat_frame) = if i < 5 {
            (Material::Ceramic, 0)
        } else {
            let slot = (i - 5) % 8;
            (Material::ALL[slot / 2], slot % 2)
        };
        let params = Params {
            material,
            heat_strength: if heat_frame == 0 { 0.62 } else { 0.18 },
        };
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
        if i == 150 {
            let mut changed = scene;
            changed.phase += 0.001;
            let before = session.stats().frames_rendered;
            let error = session
                .render_next(changed, params, &plan)
                .err()
                .ok_or("CPH2_WRONG_DIGEST_WAS_ACCEPTED")?;
            if error != "CP_F_SAME_EPOCH_DIGEST_DRIFT" || session.stats().frames_rendered != before
            {
                return Err("CPH2_LIVE_SESSION_REJECTION_FAILED".into());
            }
            rejected += 1;
        }
        let start = Instant::now();
        let result = session.render_next(scene, params, &plan)?;
        let micros = start.elapsed().as_micros() as u64;
        durations.push(micros);
        let expected = if i < 5 {
            let stem = format!("state{i}-ceramic-frame0-dpr2.gpu-rgba.bin");
            fs::read(canonical.join(stem))?
        } else {
            expected_final[(i - 5) % 8 / 2][(i - 5) % 2].clone()
        };
        if result.rgba != expected
            || result.signed_mask != masks[stage]
            || result.compute_dispatches != 6
            || result.queue_submissions != 1
            || result.intermediate_host_transfers != 0
        {
            return Err(format!("CPH2_SINGLE_SESSION_FRAME_DRIFT frame={i}").into());
        }
        if (i + 1) % 200 == 0 {
            println!("CPH2_IN_PROCESS_PROGRESS frames={} gpu_device=1", i + 1);
        }
    }
    let stats = session.stats();
    if stats.frames_rendered != frames as u64
        || stats.device_creations != 1
        || stats.pipeline_creations != 3
        || stats.reusable_storage_allocations != 5
        || rejected != 1
    {
        return Err("CPH2_PERSISTENCE_COUNTS_WRONG".into());
    }
    let median = percentile(&durations, 0.5);
    let p95 = percentile(&durations, 0.95);
    let p99 = percentile(&durations, 0.99);
    let maximum = durations.iter().copied().max().ok_or("EMPTY_TIMINGS")?;
    fs::write(output.join("single-session-stats.tsv"),format!(
      "frames\tdevice_creations\tpipelines\treusable_buffers\trejected_invalid\tmedian_frame_us\tp95_frame_us\tp99_frame_us\tmax_frame_us\n{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n",
       frames,stats.device_creations,stats.pipeline_creations,
       stats.reusable_storage_allocations,rejected,median,p95,p99,maximum
    ))?;
    println!("QCHAIN_H2_SINGLE_SESSION_PASS frames={} device=1 pipelines=3 reusable_buffers=5 rejected_invalid=1 median_us={} p99_us={} max_us={}",
       frames,median,p99,maximum);
    Ok(())
}
