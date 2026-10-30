//! CP-I02 bounded native Wayland consumer of freshly computed GPU frames via sealed memfd.
use blob_frame::{qchain, MappedFrame, SeqPacket};
use std::{
    env, fs,
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, Ordering},
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
#[cfg(feature="cpja7j-mmap-consumer")]
enum PixelOwnership {
    Copy(Vec<u8>),
    Mmap(MappedFrame),
}
#[cfg(feature="cpja7j-mmap-consumer")]
impl PixelOwnership {
    fn as_slice(&self) -> &[u8] {
        match self {
            Self::Copy(bytes)=>bytes.as_slice(),
            Self::Mmap(mapped)=>mapped.bytes(),
        }
    }
}
struct Frame {
    #[cfg(feature="cpja7j-mmap-consumer")]
    pixels: PixelOwnership,
    #[cfg(not(feature="cpja7j-mmap-consumer"))]
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
        #[cfg(feature="cpja7j-mmap-consumer")]
        let pixel_mode=env::var("CPJA7J_CLIENT_PIXELS")
            .map_err(|_|"CPJA7J_CLIENT_PIXEL_MODE_REQUIRED")?;
        #[cfg(feature="cpja7j-mmap-consumer")]
        if !matches!(pixel_mode.as_str(),"copy"|"mmap") {
            return Err("CPJA7J_CLIENT_PIXEL_MODE_INVALID".into());
        }
        #[cfg(feature="cpja7j-mmap-consumer")]
        println!("CPJA7J_CLIENT_OWNERSHIP mode={} immutable_sealed_memfd=1 full_sha256=1",
            pixel_mode);
        let cpu: serde_json::Value =
            serde_json::from_slice(&fs::read(&receipt).map_err(|e| e.to_string())?)
                .map_err(|e| e.to_string())?;
        let canonical = cpu["stages"].as_array().ok_or("CPU_STAGES_MISSING")?;
        if canonical.len() != 5 {
            return Err("CANONICAL_FIVE_SCENES_REQUIRED".into());
        }
        for seq in 0..frames {
            #[cfg(feature="cpja7h-timing")]
            let packet_started=Instant::now();
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
            #[cfg(feature="cpja7h-timing")]
            let ipc_packet_us=packet_started.elapsed().as_micros();
            #[cfg(feature="cpja7h-timing")]
            let integrity_started=Instant::now();
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
            #[cfg(feature="cpja7j-mmap-consumer")]
            let pixels=if pixel_mode=="mmap" {
                PixelOwnership::Mmap(mapped)
            } else {
                PixelOwnership::Copy(mapped.bytes().to_vec())
            };
            #[cfg(not(feature="cpja7j-mmap-consumer"))]
            let pixels=mapped.bytes().to_vec();
            #[cfg(feature="cpja7j-mmap-consumer")]
            if seq%30==0 {
                println!("CPJA7J_CLIENT_PIXEL_MODE seq={} mode={} source_sha256={}",
                    seq,pixel_mode,hash);
            }
            let frame = Frame {
                pixels,
                seq,
                scene_sha: m["scene_sha256"].as_str().unwrap().into(),
                rgba_sha: hash,
                epoch: stage as u64,
                received,
            };
            #[cfg(feature="cpja7h-timing")]
            let integrity_us=integrity_started.elapsed().as_micros();
            #[cfg(feature="cpja7h-timing")]
            let queue_started=Instant::now();
            if sender.send(Ok(frame)).is_err() {
                return Ok(());
            }
            #[cfg(feature="cpja7h-timing")]
            println!("CPJA7H_CLIENT_TIMING seq={} request_to_packet_us={} integrity_copy_us={} channel_block_us={}",
                seq,ipc_packet_us,integrity_us,queue_started.elapsed().as_micros());
        }
        Ok(())
    };
    if let Err(error) = execute() {
        let _ = sender.send(Err(error));
    }
}
struct Gpu {
    secondary_window: Option<Arc<Window>>,
    secondary_surface: Option<wgpu::Surface<'static>>,
    window: Arc<Window>,
    surface: wgpu::Surface<'static>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    config: wgpu::SurfaceConfiguration,
    texture: wgpu::Texture,
    group: wgpu::BindGroup,
    pipeline: wgpu::RenderPipeline,
    #[cfg(feature="cpja7i-gpu-timestamps")]
    query_primary: wgpu::QuerySet,
    #[cfg(feature="cpja7i-gpu-timestamps")]
    query_secondary: wgpu::QuerySet,
    #[cfg(feature="cpja7i-gpu-timestamps")]
    query_primary_resolve: wgpu::Buffer,
    #[cfg(feature="cpja7i-gpu-timestamps")]
    query_secondary_resolve: wgpu::Buffer,
    #[cfg(feature="cpja7i-gpu-timestamps")]
    query_staging: wgpu::Buffer,
    #[cfg(feature="cpja7i-gpu-timestamps")]
    query_period_ns: f32,
}
struct Viewer {
    frame: Option<Frame>,
    receiver: Receiver<Result<Frame, String>>,
    gpu: Option<Gpu>,
    next: Instant,
    end: Instant,
    submitted: usize,
    target: usize,
    frame_interval: Duration,
    started: Instant,
    error: Option<String>,
    drop_secondary_after: Option<usize>,
    lost_signal: Arc<AtomicBool>,
    recovery_epochs: usize,
    allow_loss_recovery: bool,
    #[cfg(feature="cpja7i-gpu-timestamps")]
    empty_polls: usize,
}
impl Viewer {
    fn init(&mut self, el: &ActiveEventLoop) -> Result<(), String> {
        let attrs = Window::default_attributes()
            .with_title("QCHAIN CP-JA7 · Dual Swapchain")
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
        #[cfg(feature="cpja7i-gpu-timestamps")]
        if !adapter.features().contains(wgpu::Features::TIMESTAMP_QUERY) {
            return Err("CPJA7I_REAL_GPU_TIMESTAMP_FEATURE_NOT_SUPPORTED".into());
        }
        let mut device_description=wgpu::DeviceDescriptor {
            label: Some("QCHAIN independent Vulkan presentation"),
            ..Default::default()
        };
        #[cfg(feature="cpja7i-gpu-timestamps")]
        {device_description.required_features=wgpu::Features::TIMESTAMP_QUERY;}
        let (device, queue) = pollster::block_on(adapter.request_device(&device_description))
            .map_err(|e| e.to_string())?;

        let signal = self.lost_signal.clone();
        device.set_device_lost_callback(move |reason, message| {
            if reason != wgpu::DeviceLostReason::Destroyed {
                eprintln!("CPJA7C_WGPU_DEVICE_LOST_CALLBACK reason={reason:?} detail={message}");
                signal.store(true, Ordering::SeqCst);
            }
        });
        let size = window.inner_size();
        let mut config = surface
            .get_default_config(&adapter, size.width.max(1), size.height.max(1))
            .ok_or("WAYLAND_SURFACE_UNSUPPORTED")?;
        config.present_mode = wgpu::PresentMode::AutoVsync;
        config.alpha_mode = wgpu::CompositeAlphaMode::Opaque;
        surface.configure(&device, &config);
        let secondary_window = Arc::new(
            el.create_window(
                Window::default_attributes()
                    .with_title("QCHAIN CP-JA7 · secondary")
                    .with_name("qchain-cpja7-secondary", "qchain-cpja7-secondary")
                    .with_inner_size(winit::dpi::LogicalSize::new(512.0, 384.0))
                    .with_resizable(false),
            )
            .map_err(|e| e.to_string())?,
        );
        secondary_window.set_cursor_visible(false);
        let secondary_surface = instance
            .create_surface(secondary_window.clone())
            .map_err(|e| e.to_string())?;
        let mut secondary_config = secondary_surface
            .get_default_config(&adapter, 512, 384)
            .ok_or("CPJA7_SECONDARY_SURFACE_UNSUPPORTED")?;
        if secondary_config.format != config.format {
            return Err("CPJA7_SECONDARY_FORMAT_MISMATCH".into());
        }
        secondary_config.present_mode = wgpu::PresentMode::AutoVsync;
        secondary_config.alpha_mode = wgpu::CompositeAlphaMode::Opaque;
        secondary_surface.configure(&device, &secondary_config);
        println!("CPJA7_TWO_SWAPS_ONE_DEVICE primary=512x384 secondary=512x384");
        #[cfg(feature="cpja7e-adaptive-scheduler")]
        cpja7e_idle_probe()?;

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
        #[cfg(feature="cpja7i-gpu-timestamps")]
        let query_primary = device.create_query_set(&wgpu::QuerySetDescriptor {
            label: Some("CP-JA7I primary timestamp series"),
            ty: wgpu::QueryType::Timestamp,
            count: (self.target*2) as u32,
        });
        #[cfg(feature="cpja7i-gpu-timestamps")]
        let query_secondary = device.create_query_set(&wgpu::QuerySetDescriptor {
            label: Some("CP-JA7I secondary timestamp series"),
            ty: wgpu::QueryType::Timestamp,
            count: (self.target*2) as u32,
        });
        #[cfg(feature="cpja7i-gpu-timestamps")]
        let query_buffer_size=(self.target as u64)*32;
        #[cfg(feature="cpja7i-gpu-timestamps")]
        let query_primary_resolve = device.create_buffer(&wgpu::BufferDescriptor{
            label: Some("CP-JA7I primary query resolve"),
            size: query_buffer_size/2,
            usage: wgpu::BufferUsages::QUERY_RESOLVE | wgpu::BufferUsages::COPY_SRC,
            mapped_at_creation: false,
        });
        #[cfg(feature="cpja7i-gpu-timestamps")]
        let query_secondary_resolve = device.create_buffer(&wgpu::BufferDescriptor{
            label: Some("CP-JA7I secondary query resolve"),
            size: query_buffer_size/2,
            usage: wgpu::BufferUsages::QUERY_RESOLVE | wgpu::BufferUsages::COPY_SRC,
            mapped_at_creation: false,
        });
        #[cfg(feature="cpja7i-gpu-timestamps")]
        let query_staging = device.create_buffer(&wgpu::BufferDescriptor{
            label: Some("CP-JA7I query readback"),
            size: query_buffer_size,
            usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });
        #[cfg(feature="cpja7i-gpu-timestamps")]
        let query_period_ns=queue.get_timestamp_period();
        #[cfg(feature="cpja7i-gpu-timestamps")]
        if !(query_period_ns.is_finite() && query_period_ns>0.0) {
            return Err("CPJA7I_GPU_TIMESTAMP_PERIOD_INVALID".into());
        }
        #[cfg(feature="cpja7i-gpu-timestamps")]
        println!("CPJA7I_GPU_QUERY_CAPABILITY adapter={} required_feature=TIMESTAMP_QUERY query_count={} period_ns_per_tick={}",
            adapter_name,self.target*4,query_period_ns);
        self.gpu = Some(Gpu {
            secondary_window: Some(secondary_window),
            secondary_surface: Some(secondary_surface),
            window,
            surface,
            device,
            queue,
            config,
            texture,
            group,
            pipeline,
            #[cfg(feature="cpja7i-gpu-timestamps")]
            query_primary,
            #[cfg(feature="cpja7i-gpu-timestamps")]
            query_secondary,
            #[cfg(feature="cpja7i-gpu-timestamps")]
            query_primary_resolve,
            #[cfg(feature="cpja7i-gpu-timestamps")]
            query_secondary_resolve,
            #[cfg(feature="cpja7i-gpu-timestamps")]
            query_staging,
            #[cfg(feature="cpja7i-gpu-timestamps")]
            query_period_ns,
        });
        self.next = Instant::now() + Duration::from_millis(100);
        self.end = Instant::now() + Duration::from_millis(
            (self.target as u64) * (self.frame_interval.as_millis() as u64) + 30_000,
        );
        #[cfg(feature="cpja7f-resident")]
        if self.frame_interval >= Duration::from_secs(1) {
            println!("CPJA7F_RESIDENT_DEVICE_CREATED epoch={} interval_ms={} target={} primary_swapchain=1 secondary_swapchain=1",
                self.recovery_epochs,self.frame_interval.as_millis(),self.target);
        }
        self.gpu.as_ref().unwrap().window.request_redraw();
        Ok(())
    }
    fn draw(&mut self) -> Result<(), String> {
        // Never submit another command to an authority declared lost.
        if self.lost_signal.load(Ordering::SeqCst) {
            return Ok(());
        }
        let gpu = self.gpu.as_mut().ok_or("MISSING_GPU")?;
        let Some(frame) = self.frame.as_ref() else {
            return Ok(());
        };
        #[cfg(feature="cpja7h-timing")]
        let upload_started=Instant::now();
        gpu.queue.write_texture(
            wgpu::TexelCopyTextureInfo {
                texture: &gpu.texture,
                mip_level: 0,
                origin: wgpu::Origin3d::ZERO,
                aspect: wgpu::TextureAspect::All,
            },
            frame.pixels.as_slice(),
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
        #[cfg(feature="cpja7h-timing")]
        let texture_upload_api_us=upload_started.elapsed().as_micros();
        #[cfg(feature="cpja7h-timing")]
        let primary_acquire_start=Instant::now();
        let f = match gpu.surface.get_current_texture() {
            wgpu::CurrentSurfaceTexture::Success(f)
            | wgpu::CurrentSurfaceTexture::Suboptimal(f) => f,
            wgpu::CurrentSurfaceTexture::Outdated | wgpu::CurrentSurfaceTexture::Lost => {
                gpu.surface.configure(&gpu.device, &gpu.config);
                return Err("SURFACE_FRAME_NOT_PRESENTED".into());
            }
            other => return Err(format!("UNAVAILABLE_SURFACE_FRAME {other:?}")),
        };
        #[cfg(feature="cpja7h-timing")]
        let primary_acquire_us=primary_acquire_start.elapsed().as_micros();
        #[cfg(feature="cpja7h-timing")]
        let primary_encode_start=Instant::now();
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
                #[cfg(feature="cpja7i-gpu-timestamps")]
                timestamp_writes: Some(wgpu::RenderPassTimestampWrites {
                    query_set: &gpu.query_primary,
                    beginning_of_pass_write_index: Some((frame.seq*2) as u32),
                    end_of_pass_write_index: Some((frame.seq*2+1) as u32),
                }),
                ..Default::default()
            });
            pass.set_pipeline(&gpu.pipeline);
            pass.set_bind_group(0, &gpu.group, &[]);
            pass.draw(0..3, 0..1);
        }
        #[cfg(feature="cpja7h-timing")]
        let primary_encode_us=primary_encode_start.elapsed().as_micros();
        #[cfg(feature="cpja7h-timing")]
        let primary_submit_start=Instant::now();
        gpu.queue.submit([encoder.finish()]);
        #[cfg(feature="cpja7h-timing")]
        let primary_submit_api_us=primary_submit_start.elapsed().as_micros();
        gpu.window.pre_present_notify();
        #[cfg(feature="cpja7h-timing")]
        let primary_present_start=Instant::now();
        gpu.queue.present(f);
        #[cfg(feature="cpja7h-timing")]
        let primary_present_api_us=primary_present_start.elapsed().as_micros();
        // Queue::present exposes errors through wgpu's device lost callback.
        // Preserve this exact source frame for replay on a new device.
        if self.lost_signal.load(Ordering::SeqCst) {
            println!(
                "CPJA7C_FAIL_CLOSED_PENDING_RECOVERY seq={} completed={} epoch={}",
                frame.seq, self.submitted, self.recovery_epochs
            );
            return Ok(());
        }
        #[cfg(feature="cpja7h-timing")]
        let mut secondary_acquire_us=0_u128;
        #[cfg(feature="cpja7h-timing")]
        let mut secondary_encode_us=0_u128;
        #[cfg(feature="cpja7h-timing")]
        let mut secondary_submit_api_us=0_u128;
        #[cfg(feature="cpja7h-timing")]
        let mut secondary_present_api_us=0_u128;
        if let Some(secondary) = gpu.secondary_surface.as_ref() {
            #[cfg(feature="cpja7h-timing")]
            let secondary_acquire_start=Instant::now();
            let sf = match secondary.get_current_texture() {
                wgpu::CurrentSurfaceTexture::Success(f)
                | wgpu::CurrentSurfaceTexture::Suboptimal(f) => f,
                other => return Err(format!("CPJA7_SECONDARY_SURFACE_FAILURE {other:?}")),
            };
            #[cfg(feature="cpja7h-timing")]
            {secondary_acquire_us=secondary_acquire_start.elapsed().as_micros();}
            #[cfg(feature="cpja7h-timing")]
            let secondary_encode_start=Instant::now();
            let sv = sf.texture.create_view(&Default::default());
            let mut e = gpu
                .device
                .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                    label: Some("CPJA7 secondary frame"),
                });
            {
                let mut pass = e.begin_render_pass(&wgpu::RenderPassDescriptor {
                    label: Some("CPJA7 secondary draw"),
                    color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                        view: &sv,
                        depth_slice: None,
                        resolve_target: None,
                        ops: wgpu::Operations {
                            load: wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                            store: wgpu::StoreOp::Store,
                        },
                    })],
                    #[cfg(feature="cpja7i-gpu-timestamps")]
                    timestamp_writes: Some(wgpu::RenderPassTimestampWrites {
                        query_set: &gpu.query_secondary,
                        beginning_of_pass_write_index: Some((frame.seq*2) as u32),
                        end_of_pass_write_index: Some((frame.seq*2+1) as u32),
                    }),
                    ..Default::default()
                });
                // Distinguish the secondary compositor surface from the primary
                // without changing the authenticated GPU source pixels.
                // 16px on the left stays opaque black; all other pixels are canonical.
                pass.set_scissor_rect(16, 0, 496, 384);
                pass.set_pipeline(&gpu.pipeline);
                pass.set_bind_group(0, &gpu.group, &[]);
                pass.draw(0..3, 0..1);
            }
            #[cfg(feature="cpja7h-timing")]
            {secondary_encode_us=secondary_encode_start.elapsed().as_micros();}
            #[cfg(feature="cpja7h-timing")]
            let secondary_submit_start=Instant::now();
            gpu.queue.submit([e.finish()]);
            #[cfg(feature="cpja7h-timing")]
            {secondary_submit_api_us=secondary_submit_start.elapsed().as_micros();}
            gpu.secondary_window.as_ref().unwrap().pre_present_notify();
            #[cfg(feature="cpja7h-timing")]
            let secondary_present_start=Instant::now();
            gpu.queue.present(sf);
            #[cfg(feature="cpja7h-timing")]
            {secondary_present_api_us=secondary_present_start.elapsed().as_micros();}
            println!(
                "CPJA7_SECONDARY_PRESENT seq={} source_sha256={}",
                frame.seq, frame.rgba_sha
            );
        }
        self.submitted += 1;
        if self.drop_secondary_after == Some(self.submitted) {
            gpu.secondary_surface.take();
            gpu.secondary_window.take();
            println!(
                "CPJA7_SECONDARY_RELEASE after_seq={} primary_preserved=1",
                frame.seq
            );
        }

        #[cfg(feature="cpja7h-timing")]
        println!("CPJA7H_VIEWER_TIMING seq={} texture_upload_api_us={} primary_acquire_us={} primary_encode_us={} primary_submit_api_us={} primary_present_api_us={} secondary_acquire_us={} secondary_encode_us={} secondary_submit_api_us={} secondary_present_api_us={}",
            frame.seq,texture_upload_api_us,primary_acquire_us,primary_encode_us,
            primary_submit_api_us,primary_present_api_us,
            secondary_acquire_us,secondary_encode_us,secondary_submit_api_us,
            secondary_present_api_us);
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
        if self.lost_signal.load(Ordering::SeqCst) {
            if !self.allow_loss_recovery || self.recovery_epochs != 0 {
                println!(
                    "CPJA7C_SECOND_DEVICE_LOSS_FAIL_CLOSED after_epoch={}",
                    self.recovery_epochs
                );
                self.error = Some("CPJA7C_SECOND_DEVICE_LOSS_FAIL_CLOSED".into());
                el.exit();
                return;
            }
            let at_seq = self.frame.as_ref().map(|f| f.seq);
            println!(
                "CPJA7C_RECOVERY_BEGIN old_epoch=0 completed={} pending_seq={at_seq:?}",
                self.submitted
            );
            self.lost_signal.store(false, Ordering::SeqCst);
            self.gpu.take();
            self.recovery_epochs += 1;
            if let Err(error) = self.init(el) {
                self.error = Some(format!("CPJA7C_DEVICE_REBUILD_FAILED {error}"));
                el.exit();
                return;
            }
            println!(
                "CPJA7C_RECOVERY_READY new_epoch=1 completed={} pending_seq={at_seq:?}",
                self.submitted
            );
            if let Err(error) = self.draw() {
                self.error = Some(format!("CPJA7C_REPLAY_FAILED {error}"));
                el.exit();
                return;
            }
            // Attempt replay at most once. If loss occurs again, fail closed.
            el.set_control_flow(ControlFlow::WaitUntil(self.next.min(self.end)));
            return;
        }
        if self.gpu.is_none() {
            return;
        }
        if self.submitted == self.target {
            el.exit();
            return;
        }
        let now = Instant::now();
        if now >= self.end {
            self.error = Some("CPI02_PRESENTATION_TIMEOUT".into());
            el.exit();
            return;
        }
        if now >= self.next && self.frame.is_none() {
            #[cfg(feature="cpja7i-gpu-timestamps")]
            let wake_late_us=now.saturating_duration_since(self.next).as_micros();
            match self.receiver.try_recv() {
                Ok(Ok(frame)) => {
                    if frame.seq != self.submitted {
                        self.error = Some("STREAM_FRAME_SEQUENCE_GAP".into());
                        el.exit();
                        return;
                    }
                    #[cfg(feature="cpja7i-gpu-timestamps")]
                    let (seq,ready_dwell_us)=(frame.seq,frame.received.elapsed().as_micros());
                    self.frame = Some(frame);
                    self.next = now + self.frame_interval;
                    #[cfg(feature="cpja7i-gpu-timestamps")]
                    let draw_started=Instant::now();
                    if let Err(err) = self.draw() {
                        self.error = Some(err);
                        el.exit();
                        return;
                    }
                    #[cfg(feature="cpja7i-gpu-timestamps")]
                    {
                        let draw_api_us=draw_started.elapsed().as_micros();
                        let deadline_remaining_us=self.next
                            .saturating_duration_since(Instant::now()).as_micros();
                        println!("CPJA7I_FRAME_CAUSAL seq={} requested_interval_us={} wake_late_us={} ready_dwell_us={} empty_polls={} draw_api_us={} deadline_remaining_us={}",
                            seq,self.frame_interval.as_micros(),wake_late_us,
                            ready_dwell_us,self.empty_polls,draw_api_us,
                            deadline_remaining_us);
                        self.empty_polls=0;
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
#[cfg(feature="cpja7e-adaptive-scheduler")]
fn cpja7e_idle_probe()->Result<(),String>{
    if let Ok(raw)=env::var("CPJA7E_IDLE_PROBE_MS"){
        let ms=raw.parse::<u64>().map_err(|_|"CPJA7E_IDLE_NOT_INTEGER")?;
        if !(1..=800).contains(&ms){return Err("CPJA7E_IDLE_INVALID_BOUND".into());}
        println!("CPJA7E_IDLE_BEGIN duration_ms={ms}");
        thread::sleep(Duration::from_millis(ms));
        println!("CPJA7E_IDLE_END duration_ms={ms}");
    }
    Ok(())
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let _ = env_logger::Builder::new()
        .filter_module("wgpu_hal::vulkan", log::LevelFilter::Info)
        .try_init();
    let mut args = env::args().skip(1);
    let socket = PathBuf::from(args.next().ok_or("PRIVATE_SOCKET_REQUIRED")?);
    let receipt = PathBuf::from(args.next().ok_or("CANONICAL_CPU_RECEIPT_REQUIRED")?);
    let target: usize = args.next().ok_or("FRAMES_REQUIRED")?.parse()?;
    #[cfg(feature="cpja7g-active-gpu")]
    let max_frames=4800;
    #[cfg(not(feature="cpja7g-active-gpu"))]
    let max_frames=300;
    if args.next().is_some() || !(40..=max_frames).contains(&target) {
        return Err("CPI02_FRAME_TARGET_INVALID".into());
    }
    if env::var_os("WAYLAND_DISPLAY").is_none() {
        return Err("WAYLAND_DISPLAY_MISSING".into());
    }
    #[cfg(feature="cpja7f-resident")]
    let interval_ms=match env::var("CPJA7F_FRAME_INTERVAL_MS"){
        Ok(s)=>{
            let ms=s.parse::<u64>().map_err(|_|"CPJA7F_INTERVAL_NOT_INTEGER")?;
            #[cfg(feature="cpja7h-timing")]
            let minimum=16;
            #[cfg(not(feature="cpja7h-timing"))]
            let minimum=33;
            if !(minimum..=4500).contains(&ms){return Err("CPJA7F_INTERVAL_UNSAFE_BOUND".into());}
            ms
        }
        Err(_)=>33,
    };
    #[cfg(not(feature="cpja7f-resident"))]
    let interval_ms=33_u64;
    #[cfg(feature="cpja7f-resident")]
    println!("CPJA7F_RESIDENCY_CONFIG interval_ms={} source_frames={} device_rebuild_allowed={}",
        interval_ms,target,env::var("CPJA7C_RECOVER_IN_PROCESS").as_deref()==Ok("1"));
    let (sender, receiver) = mpsc::sync_channel(1);
    let worker = thread::spawn(move || stream(socket, receipt, target, sender));
    let drop_secondary_after = match env::var("CPJA7_DROP_SECONDARY_AFTER") {
        Ok(v) => Some(
            v.parse::<usize>()
                .map_err(|_| "CPJA7_INVALID_DROP_BOUNDARY")?,
        ),
        Err(_) => None,
    };
    if drop_secondary_after.is_some_and(|n| n == 0 || n > target) {
        return Err("CPJA7_DROP_BOUNDARY_OUT_OF_RANGE".into());
    }
    let mut viewer = Viewer {
        frame: None,
        receiver,
        gpu: None,
        next: Instant::now(),
        end: Instant::now(),
        submitted: 0,
        target,
        frame_interval: Duration::from_millis(interval_ms),
        started: Instant::now(),
        error: None,
        drop_secondary_after,
        lost_signal: Arc::new(AtomicBool::new(false)),
        recovery_epochs: 0,
        allow_loss_recovery: env::var("CPJA7C_RECOVER_IN_PROCESS").as_deref() == Ok("1"),
        #[cfg(feature="cpja7i-gpu-timestamps")]
        empty_polls: 0,
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
    #[cfg(feature="cpja7i-gpu-timestamps")]
    {
        let gpu=viewer.gpu.as_ref().ok_or("CPJA7I_GPU_NOT_RESIDENT")?;
        let mut encoder=gpu.device.create_command_encoder(&wgpu::CommandEncoderDescriptor{
            label: Some("CP-JA7I final query resolve"),
        });
        encoder.resolve_query_set(&gpu.query_primary,0..((target*2) as u32),
            &gpu.query_primary_resolve,0);
        encoder.resolve_query_set(&gpu.query_secondary,0..((target*2) as u32),
            &gpu.query_secondary_resolve,0);
        encoder.copy_buffer_to_buffer(&gpu.query_primary_resolve,0,
            &gpu.query_staging,0,(target*16) as u64);
        encoder.copy_buffer_to_buffer(&gpu.query_secondary_resolve,0,
            &gpu.query_staging,(target*16) as u64,(target*16) as u64);
        gpu.queue.submit([encoder.finish()]);
        let (tx,rx)=mpsc::channel();
        gpu.query_staging.slice(..).map_async(wgpu::MapMode::Read,move |x|{
            let _=tx.send(x);
        });
        gpu.device.poll(wgpu::PollType::Wait{
            submission_index: None,
            timeout: Some(Duration::from_secs(10)),
        }).map_err(|_|"CPJA7I_GPU_QUERY_POLL_FAILED")?;
        rx.recv_timeout(Duration::from_secs(2))
           .map_err(|_|"CPJA7I_GPU_QUERY_MAP_CALLBACK_TIMEOUT")?
           .map_err(|_|"CPJA7I_GPU_QUERY_MAP_FAILED")?;
        let mapped=gpu.query_staging.slice(..).get_mapped_range()
            .map_err(|_|"CPJA7I_GPU_QUERY_MAP_RANGE_FAILED")?;
        let raw_path=env::var("CPJA7I_GPU_QUERY_RAW")
            .map_err(|_|"CPJA7I_GPU_QUERY_OUTPUT_REQUIRED")?;
        fs::write(&raw_path,mapped.as_ref())?;
        let hash=qchain::digest(mapped.as_ref());
        let pairs=mapped.chunks_exact(8)
            .map(|chunk|u64::from_le_bytes(chunk.try_into().unwrap()))
            .collect::<Vec<_>>();
        if pairs.len()!=target*4 ||
            pairs.chunks_exact(2).any(|t|t[1]<=t[0]) {
            return Err("CPJA7I_GPU_TIMESTAMPS_INVALID".into());
        }
        let primary=(0..target).map(|i|
            ((pairs[2*i+1]-pairs[2*i]) as f64)*f64::from(gpu.query_period_ns))
            .collect::<Vec<_>>();
        let secondary=(0..target).map(|i|
            ((pairs[target*2+2*i+1]-pairs[target*2+2*i]) as f64)*f64::from(gpu.query_period_ns))
            .collect::<Vec<_>>();
        println!("CPJA7I_GPU_QUERY_COMPLETE frames={} queries={} period_ns={} raw_bytes={} raw_sha256={} primary_total_ns={:.0} secondary_total_ns={:.0}",
            target,target*4,gpu.query_period_ns,mapped.len(),hash,
            primary.iter().sum::<f64>(),secondary.iter().sum::<f64>());
        drop(mapped);
        gpu.query_staging.unmap();
    }
    if viewer.allow_loss_recovery {
        if viewer.recovery_epochs != 1 {
            return Err("CPJA7C_RECOVERY_EPOCH_NOT_OBSERVED".into());
        }
        println!(
            "CPJA7C_RECOVERY_COMPLETE epochs={} submitted={target}",
            viewer.recovery_epochs
        );
    }
    #[cfg(feature="cpja7f-resident")]
    println!("CPJA7F_RESIDENCY_COMPLETE frames={target} interval_ms={} elapsed_us={} epochs={}",
        interval_ms,viewer.started.elapsed().as_micros(),viewer.recovery_epochs);
    println!("CPI02_WGPU_STREAM_COMPLETE submitted={target}");
    Ok(())
}
