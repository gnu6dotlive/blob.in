//! Opt-in native Wayland viewer of verified QCHAIN-FRAME-v1 CPU pixels.
use blob_frame::{
    qchain::{self, SceneRequest},
    SeqPacket,
};
use std::{
    env, fs,
    path::{Path, PathBuf},
    sync::Arc,
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
}
fn fetch(socket: &Path, receipt: &Path) -> Result<Vec<Frame>, String> {
    let data = fs::read(receipt).map_err(|e| e.to_string())?;
    let result: serde_json::Value = serde_json::from_slice(&data).map_err(|e| e.to_string())?;
    if result["verdict"] != "F2_F3_F4_CPU_CHAIN_PASS_BRIDGE_NOT_RUN"
        || result["qchain_full_e2e_pass"] != false
    {
        return Err("RECEIPT_NOT_CPU_QUALIFIED".into());
    }
    let stages = result["stages"].as_array().ok_or("MISSING_STAGES")?;
    if stages.len() != 5 {
        return Err("EXPECTED_FIVE_STAGES".into());
    }
    let mut frames = Vec::new();
    for (i, stage) in stages.iter().enumerate() {
        let epoch = stage["epoch"].as_u64().ok_or("MISSING_EPOCH")?;
        if epoch != i as u64 {
            return Err("STAGE_REPLAY".into());
        }
        let scene_sha = stage["scene_sha256"]
            .as_str()
            .ok_or("MISSING_SCENE_SHA")?
            .to_owned();
        let rgba_sha = stage["f4_rgba_sha256"]
            .as_str()
            .ok_or("MISSING_RGBA_SHA")?
            .to_owned();
        let digest = stage["f2_semantic_digest"]
            .as_str()
            .ok_or("MISSING_SEMANTIC_DIGEST")?
            .to_owned();
        let req = SceneRequest {
            version: qchain::VERSION.into(),
            request_id: epoch + 1,
            scene_revision: epoch,
            scene_sha256: scene_sha.clone(),
            expected_rgba_sha256: rgba_sha.clone(),
            semantic_digest: digest,
        };
        let conn = SeqPacket::connect(socket).map_err(|e| e.to_string())?;
        conn.set_read_timeout(Some(Duration::from_secs(3)))
            .map_err(|e| e.to_string())?;
        let (meta, bytes) = qchain::receive_one(&conn, &req)?;
        if meta.gpu_qualified || meta.compositor_observed {
            return Err("FORGED_QUALIFICATION".into());
        }
        let pixels = bytes.bytes().to_vec();
        if qchain::digest(&pixels) != rgba_sha {
            return Err("F4_BYTES_CHANGED".into());
        }
        frames.push(Frame {
            pixels,
            scene_sha,
            rgba_sha,
            epoch,
        });
        println!(
            "QCHAIN_IPC_RECEIVED stage={i} rgba_sha256={}",
            frames[i].rgba_sha
        );
    }
    Ok(frames)
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
    frames: Vec<Frame>,
    gpu: Option<Gpu>,
    stage: usize,
    next: Instant,
    end: Instant,
    submitted: [bool; 5],
    error: Option<String>,
}
impl Viewer {
    fn init(&mut self, el: &ActiveEventLoop) -> Result<(), String> {
        let attrs = Window::default_attributes()
            .with_title("QCHAIN · CPU F4 scene witness")
            .with_name("blobin-qchain-viewer", "blobin-qchain-viewer")
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
            "QCHAIN_WAYLAND_WINDOW_READY adapter={adapter_name} scale={} size={}x{}",
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
        self.next = Instant::now() + Duration::from_millis(2400);
        self.end = Instant::now() + Duration::from_millis(12000);
        self.gpu.as_ref().unwrap().window.request_redraw();
        Ok(())
    }
    fn draw(&mut self) -> Result<(), String> {
        let gpu = self.gpu.as_mut().ok_or("MISSING_GPU")?;
        let frame = &self.frames[self.stage];
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
        gpu.window.pre_present_notify();
        gpu.queue.present(f);
        self.submitted[self.stage] = true;
        println!("QCHAIN_WGPU_PRESENT_SUBMITTED stage={} epoch={} scene_sha256={} rgba_sha256={} dimensions={}x{}",
   self.stage,frame.epoch,frame.scene_sha,frame.rgba_sha,gpu.config.width,gpu.config.height);
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
        let now = Instant::now();
        if now >= self.end {
            el.exit();
            return;
        }
        if now >= self.next && self.stage < 4 {
            self.stage += 1;
            self.next = now + Duration::from_millis(2400);
            if let Some(gpu) = &self.gpu {
                gpu.window.request_redraw()
            }
        }
        el.set_control_flow(ControlFlow::WaitUntil(self.next.min(self.end)));
    }
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = env::args().skip(1);
    let socket = PathBuf::from(args.next().ok_or("expected private qchain socket")?);
    let receipt = PathBuf::from(args.next().ok_or("expected actual CPU receipt JSON")?);
    if args.next().is_some() {
        return Err("too many args".into());
    }
    if env::var_os("WAYLAND_DISPLAY").is_none() {
        return Err("WAYLAND_DISPLAY missing".into());
    }
    let frames = fetch(&socket, &receipt)?;
    let mut viewer = Viewer {
        frames,
        gpu: None,
        stage: 0,
        next: Instant::now(),
        end: Instant::now(),
        submitted: [false; 5],
        error: None,
    };
    let el = EventLoop::new()?;
    el.set_control_flow(ControlFlow::Wait);
    el.run_app(&mut viewer)?;
    if let Some(err) = viewer.error {
        return Err(err.into());
    }
    if !viewer.submitted.iter().all(|v| *v) {
        return Err("NOT_ALL_FRAMES_SUBMITTED".into());
    }
    println!("QCHAIN_ALL_FIVE_WGPU_FRAMES_SUBMITTED compositor_capture=NOT_YET_QUALIFIED");
    Ok(())
}
