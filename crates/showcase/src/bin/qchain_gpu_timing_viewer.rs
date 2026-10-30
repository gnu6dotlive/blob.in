//! CP-J instrumented bounded native Wayland consumer of freshly computed GPU frames via sealed memfd.
use blob_frame::{qchain, MappedFrame, SeqPacket};
use std::{
    env, fs,
    path::PathBuf,
    sync::{
        mpsc::{self, Receiver},
        Arc,
    },
    thread,
    time::{Duration, Instant},
};
use winit::platform::wayland::WindowAttributesExtWayland;
use winit::{
    application::ApplicationHandler,
    event::WindowEvent,
    event_loop::{ActiveEventLoop, ControlFlow, EventLoop},
    window::{Window, WindowId},
};

const SHADER: &str = r#"
struct V { @builtin(position) pos:vec4<f32>, @location(0) uv:vec2<f32> }
@vertex fn vs_main(@builtin(vertex_index) i:u32)->V {
 let p=array<vec2<f32>,3>(vec2<f32>(-1.0,-1.0),vec2<f32>(3.0,-1.0),vec2<f32>(-1.0,3.0));
 var v:V;v.pos=vec4<f32>(p[i],0.0,1.0);
 v.uv=vec2<f32>((p[i].x+1.0)*0.5,(1.0-p[i].y)*0.5);return v;
}
@group(0) @binding(0) var pixels:texture_2d<f32>;
@group(0) @binding(1) var nearest:sampler;
@fragment fn fs_main(v:V)->@location(0) vec4<f32> {return textureSample(pixels,nearest,v.uv);}
"#;
struct Frame {
    pixels: Vec<u8>,
    scene_sha: String,
    rgba_sha: String,
    epoch: u64,
    seq: usize,
    received: Instant,
}
fn stream(
    socket: PathBuf,
    receipt: PathBuf,
    frames: usize,
    sender: mpsc::SyncSender<Result<Frame, String>>,
) {
    let execute = || -> Result<(), String> {
        let cpu: serde_json::Value =
            serde_json::from_slice(&fs::read(&receipt).map_err(|e| e.to_string())?)
                .map_err(|e| e.to_string())?;
        let canonical = cpu["stages"].as_array().ok_or("CPU_STAGES_MISSING")?;
        if canonical.len() != 5 {
            return Err("CANONICAL_FIVE_SCENES_REQUIRED".into());
        }
        for seq in 0..frames {
            let conn = SeqPacket::connect(&socket).map_err(|e| e.to_string())?;
            conn.require_same_uid().map_err(|e| e.to_string())?;
            conn.set_read_timeout(Some(Duration::from_secs(5)))
                .map_err(|e| e.to_string())?;
            let request = serde_json::json!({"version":"QCHAIN-GPU-STREAM-v1","seq":seq});
            conn.send(
                &serde_json::to_vec(&request).map_err(|e| e.to_string())?,
                &[],
            )
            .map_err(|e| e.to_string())?;
            let mut packet = conn.recv().map_err(|e| e.to_string())?;
            if packet.fds.len() != 1 {
                return Err("STREAM_MEMFD_COUNT_INVALID".into());
            }
            let m: serde_json::Value = serde_json::from_slice(&packet.bytes)
                .map_err(|_| "STREAM_METADATA_JSON_INVALID")?;
            let stage = seq.min(4);
            let canonical_scene = &canonical[stage];
            if m["version"] != "QCHAIN-GPU-STREAM-v1"
                || m["seq"].as_u64() != Some(seq as u64)
                || m["stage"].as_u64() != Some(stage as u64)
                || m["scene_sha256"] != canonical_scene["scene_sha256"]
                || m["semantic_digest"] != canonical_scene["f2_semantic_digest"]
                || m["backend"] != "Vulkan/WGSL"
                || m["source"] != "CP-F-PersistentSession"
                || m["compute_source_commit"] != "5132cf59b3842e27dcacf89bfe7060e807706e90"
                || m["bytes"] != 786432
                || m["stride"] != 2048
                || m["width"] != 512
                || m["height"] != 384
                || m["zero_copy"] != false
            {
                return Err("STREAM_METADATA_AUTHORITY_MISMATCH".into());
            }
            let stat = rustix::fs::fstat(&packet.fds[0]).map_err(|e| e.to_string())?;
            if stat.st_size != 786432 {
                return Err("STREAM_MEMFD_SIZE_INVALID".into());
            }
            let mapped =
                MappedFrame::map(packet.fds.remove(0), 786432).map_err(|e| e.to_string())?;
            let hash = qchain::digest(mapped.bytes());
            if m["pixel_sha256"].as_str() != Some(hash.as_str()) {
                return Err("STREAM_PIXEL_INTEGRITY_FAILED".into());
            }
            let received = Instant::now();
            let frame = Frame {
                pixels: mapped.bytes().to_vec(),
                seq,
                scene_sha: m["scene_sha256"].as_str().unwrap().into(),
                rgba_sha: hash,
                epoch: stage as u64,
                received,
            };
            if sender.send(Ok(frame)).is_err() {
                return Ok(());
            }
        }
        Ok(())
    };
    if let Err(error) = execute() {
        let _ = sender.send(Err(error));
    }
}
struct Gpu {
    window: Arc<Window>,
    surface: wgpu::Surface<'static>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    config: wgpu::SurfaceConfiguration,
    texture: wgpu::Texture,
    group: wgpu::BindGroup,
    pipeline: wgpu::RenderPipeline,
}
struct Viewer {
    frame: Option<Frame>,
    receiver: Receiver<Result<Frame, String>>,
    gpu: Option<Gpu>,
    next: Instant,
    end: Instant,
    submitted: usize,
    drain_until: Option<Instant>,
    target: usize,
    started: Instant,
    error: Option<String>,
}
impl Viewer {
    fn init(&mut self, el: &ActiveEventLoop) -> Result<(), String> {
        let attrs = Window::default_attributes()
            .with_title("QCHAIN · LIVE GPU compute → Wayland")
            .with_name("blobin-qchain-stream-viewer", "blobin-qchain-stream-viewer")
            .with_inner_size(winit::dpi::LogicalSize::new(512.0, 384.0))
            .with_min_inner_size(winit::dpi::LogicalSize::new(512.0, 384.0))
            .with_resizable(false);
        let window = Arc::new(el.create_window(attrs).map_err(|e| e.to_string())?);
        // Suppress a client cursor sprite inside the opt-in witness window only.
        window.set_cursor_visible(false);
        let mut d = wgpu::InstanceDescriptor::new_without_display_handle();
        d.backends = wgpu::Backends::VULKAN;
        let instance = wgpu::Instance::new(d);
        let surface = instance
            .create_surface(window.clone())
            .map_err(|e| e.to_string())?;
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::HighPerformance,
            compatible_surface: Some(&surface),
            ..Default::default()
        }))
        .map_err(|e| e.to_string())?;
        let adapter_name = adapter.get_info().name;
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
            label: Some("QCHAIN independent Vulkan presentation"),
            ..Default::default()
        }))
        .map_err(|e| e.to_string())?;
        let size = window.inner_size();
        let mut config = surface
            .get_default_config(&adapter, size.width.max(1), size.height.max(1))
            .ok_or("WAYLAND_SURFACE_UNSUPPORTED")?;
        config.present_mode = wgpu::PresentMode::AutoVsync;
        config.alpha_mode = wgpu::CompositeAlphaMode::Opaque;
        surface.configure(&device, &config);
        let texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("verified F4 frame"),
            size: wgpu::Extent3d {
                width: qchain::W,
                height: qchain::H,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8UnormSrgb,
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
            view_formats: &[],
        });
        let view = texture.create_view(&Default::default());
        let layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("F4 witness bind layout"),
            entries: &[
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Texture {
                        sample_type: wgpu::TextureSampleType::Float { filterable: true },
                        view_dimension: wgpu::TextureViewDimension::D2,
                        multisampled: false,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                    count: None,
                },
            ],
        });
        let sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            mag_filter: wgpu::FilterMode::Nearest,
            min_filter: wgpu::FilterMode::Nearest,
            ..Default::default()
        });
        let group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("F4 received frame group"),
            layout: &layout,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: wgpu::BindingResource::TextureView(&view),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: wgpu::BindingResource::Sampler(&sampler),
                },
            ],
        });
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("F4 native full-frame shader"),
            source: wgpu::ShaderSource::Wgsl(SHADER.into()),
        });
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("F4 viewer layout"),
            bind_group_layouts: &[Some(&layout)],
            immediate_size: 0,
        });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("F4 witness draw"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: Some("vs_main"),
                buffers: &[],
                compilation_options: Default::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: Some("fs_main"),
                targets: &[Some(wgpu::ColorTargetState {
                    format: config.format,
                    blend: None,
                    write_mask: wgpu::ColorWrites::ALL,
                })],
                compilation_options: Default::default(),
            }),
            primitive: Default::default(),
            depth_stencil: None,
            multisample: Default::default(),
            multiview_mask: None,
            cache: None,
        });
        println!(
            "QCHAIN_GPU_WAYLAND_WINDOW_READY adapter={adapter_name} scale={} size={}x{}",
            window.scale_factor(),
            config.width,
            config.height
        );
        self.gpu = Some(Gpu {
            window,
            surface,
            device,
            queue,
            config,
            texture,
            group,
            pipeline,
        });
        self.next = Instant::now() + Duration::from_millis(100);
        self.end = Instant::now() + Duration::from_millis((self.target as u64) * 90 + 10000);
        self.gpu.as_ref().unwrap().window.request_redraw();
        Ok(())
    }
    fn draw(&mut self) -> Result<(), String> {
        let gpu = self.gpu.as_mut().ok_or("MISSING_GPU")?;
        let Some(frame) = self.frame.as_ref() else {
            return Ok(());
        };
        let draw_begin = Instant::now();
        gpu.queue.write_texture(
            wgpu::TexelCopyTextureInfo {
                texture: &gpu.texture,
                mip_level: 0,
                origin: wgpu::Origin3d::ZERO,
                aspect: wgpu::TextureAspect::All,
            },
            &frame.pixels,
            wgpu::TexelCopyBufferLayout {
                offset: 0,
                bytes_per_row: Some(qchain::STRIDE),
                rows_per_image: Some(qchain::H),
            },
            wgpu::Extent3d {
                width: qchain::W,
                height: qchain::H,
                depth_or_array_layers: 1,
            },
        );
        let f = match gpu.surface.get_current_texture() {
            wgpu::CurrentSurfaceTexture::Success(f)
            | wgpu::CurrentSurfaceTexture::Suboptimal(f) => f,
            wgpu::CurrentSurfaceTexture::Outdated | wgpu::CurrentSurfaceTexture::Lost => {
                gpu.surface.configure(&gpu.device, &gpu.config);
                return Err("SURFACE_FRAME_NOT_PRESENTED".into());
            }
            other => return Err(format!("UNAVAILABLE_SURFACE_FRAME {other:?}")),
        };
        let acquired = draw_begin.elapsed().as_micros();
        let view = f.texture.create_view(&Default::default());
        let mut encoder = gpu
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("F4 presenter command"),
            });
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("QCHAIN draw"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    depth_slice: None,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                ..Default::default()
            });
            pass.set_pipeline(&gpu.pipeline);
            pass.set_bind_group(0, &gpu.group, &[]);
            pass.draw(0..3, 0..1);
        }
        gpu.queue.submit([encoder.finish()]);
        let queued = draw_begin.elapsed().as_micros();
        gpu.window.pre_present_notify();
        gpu.queue.present(f);
        let clock = rustix::time::clock_gettime(rustix::time::ClockId::MonotonicRaw);
        let raw_ns = clock.tv_sec as i128 * 1_000_000_000 + clock.tv_nsec as i128;
        println!(
            "CPJ_RAW_PRESENT seq={} monotonic_raw_ns={}",
            frame.seq, raw_ns
        );
        let presented = draw_begin.elapsed().as_micros();
        println!(
            "CPJ_WGPU_PHASES seq={} acquire_us={} queue_us={} present_call_us={} draw_total_us={}",
            frame.seq,
            acquired,
            queued.saturating_sub(acquired),
            presented.saturating_sub(queued),
            presented
        );
        self.submitted += 1;
        if self.submitted == self.target {
            self.drain_until = Some(Instant::now() + Duration::from_millis(300));
            println!("CPJ_PROTOCOL_DRAIN_START submitted={}", self.submitted);
        }
        println!("CPI02_WGPU_PRESENT_SUBMITTED seq={} stage={} elapsed_us={} received_to_submit_us={} epoch={} scene_sha256={} rgba_sha256={} dimensions={}x{}",
            frame.seq,frame.epoch,self.started.elapsed().as_micros(),
            frame.received.elapsed().as_micros(),frame.epoch,frame.scene_sha,
            frame.rgba_sha,gpu.config.width,gpu.config.height);
        self.frame = None;
        Ok(())
    }
}
impl ApplicationHandler for Viewer {
    fn resumed(&mut self, el: &ActiveEventLoop) {
        if self.gpu.is_none() {
            if let Err(err) = self.init(el) {
                self.error = Some(err);
                el.exit()
            }
        }
    }
    fn window_event(&mut self, el: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        match event {
            WindowEvent::CloseRequested => {
                self.error = Some("VIEWER_CLOSED_BEFORE_COMPLETION".into());
                el.exit()
            }
            WindowEvent::RedrawRequested => {
                if let Err(err) = self.draw() {
                    self.error = Some(err);
                    el.exit()
                }
            }
            _ => {}
        }
    }
    fn about_to_wait(&mut self, el: &ActiveEventLoop) {
        if self.gpu.is_none() {
            return;
        }
        if self.submitted == self.target {
            if let Some(until) = self.drain_until {
                if Instant::now() >= until {
                    el.exit();
                } else {
                    el.set_control_flow(ControlFlow::WaitUntil(until));
                }
            } else {
                self.error = Some("CPJ_DRAIN_STATE_MISSING".into());
                el.exit();
            }
            return;
        }
        let now = Instant::now();
        if now >= self.end {
            self.error = Some("CPI02_PRESENTATION_TIMEOUT".into());
            el.exit();
            return;
        }
        if now >= self.next && self.frame.is_none() {
            match self.receiver.try_recv() {
                Ok(Ok(frame)) => {
                    if frame.seq != self.submitted {
                        self.error = Some("STREAM_FRAME_SEQUENCE_GAP".into());
                        el.exit();
                        return;
                    }
                    self.frame = Some(frame);
                    self.next = now + Duration::from_millis(33);
                    if let Some(gpu) = &self.gpu {
                        gpu.window.request_redraw();
                    }
                }
                Ok(Err(err)) => {
                    self.error = Some(err);
                    el.exit();
                    return;
                }
                Err(mpsc::TryRecvError::Disconnected) => {
                    self.error = Some("CPI02_SOURCE_DISCONNECTED".into());
                    el.exit();
                    return;
                }
                Err(mpsc::TryRecvError::Empty) => {
                    self.next = now + Duration::from_millis(4);
                }
            }
        }
        el.set_control_flow(ControlFlow::WaitUntil(self.next.min(self.end)));
    }
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = env::args().skip(1);
    let socket = PathBuf::from(args.next().ok_or("PRIVATE_SOCKET_REQUIRED")?);
    let receipt = PathBuf::from(args.next().ok_or("CANONICAL_CPU_RECEIPT_REQUIRED")?);
    let target: usize = args.next().ok_or("FRAMES_REQUIRED")?.parse()?;
    if args.next().is_some() || !(40..=300).contains(&target) {
        return Err("CPI02_FRAME_TARGET_INVALID".into());
    }
    if env::var_os("WAYLAND_DISPLAY").is_none() {
        return Err("WAYLAND_DISPLAY_MISSING".into());
    }
    let (sender, receiver) = mpsc::sync_channel(1);
    let worker = thread::spawn(move || stream(socket, receipt, target, sender));
    let mut viewer = Viewer {
        frame: None,
        receiver,
        gpu: None,
        next: Instant::now(),
        end: Instant::now(),
        submitted: 0,
        drain_until: None,
        target,
        started: Instant::now(),
        error: None,
    };
    let el = EventLoop::new()?;
    el.set_control_flow(ControlFlow::Wait);
    el.run_app(&mut viewer)?;
    if let Some(error) = viewer.error {
        return Err(error.into());
    }
    if viewer.submitted != target {
        return Err("CPI02_INCOMPLETE_STREAM".into());
    }
    worker.join().map_err(|_| "CPI02_STREAM_THREAD_PANICKED")?;
    println!("CPI02_WGPU_STREAM_COMPLETE submitted={target}");
    Ok(())
}
