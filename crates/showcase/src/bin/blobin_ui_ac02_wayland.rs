//! BLOB-AC-02 dedicated native gesture consumer fixture. This is a native Wayland fixture,
//! not the production renderer and its submitted frames are not compositor presentation feedback.
use blobin_showcase::ac02_scene::{Change, NativeGestureScene};
use blobin_ui_core::input::{EventKind, Key, Point, Units};
use blobin_ui_core::layout::{Size, Viewport};
use serde_json::json;
use std::fs::File;
use std::io::Write;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};
use winit::application::ApplicationHandler;
use winit::dpi::LogicalSize;
use winit::event::{ElementState, MouseButton, WindowEvent};
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop};
use winit::keyboard::{Key as WinitKey, ModifiersState, NamedKey};
use winit::platform::wayland::WindowAttributesExtWayland;
use winit::window::{Window, WindowId};

const SHADER: &str = r#"
struct Params { xywh: vec4<f32>, color: vec4<f32>, viewport: vec4<f32> }
@group(0) @binding(0) var<uniform> params: Params;
struct Vert { @builtin(position) pos: vec4<f32>, @location(0) color:vec4<f32> }
@vertex fn vs(@builtin(vertex_index) i:u32)->Vert{
    let corners=array<vec2<f32>,6>(
        vec2<f32>(0.0,0.0),vec2<f32>(1.0,0.0),vec2<f32>(0.0,1.0),
        vec2<f32>(1.0,0.0),vec2<f32>(1.0,1.0),vec2<f32>(0.0,1.0));
    let logical=params.xywh.xy + corners[i]*params.xywh.zw;
    var v:Vert;
    v.pos=vec4<f32>(2.0*logical.x/params.viewport.x-1.0,
                     1.0-2.0*logical.y/params.viewport.y,0.0,1.0);
    v.color=params.color;
    return v;
}
@fragment fn fs(v:Vert)->@location(0) vec4<f32>{return v.color;}
"#;
struct Graphics {
    window: Arc<Window>,
    surface: wgpu::Surface<'static>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    config: wgpu::SurfaceConfiguration,
    pipeline: wgpu::RenderPipeline,
    group_layout: wgpu::BindGroupLayout,
}
struct Probe {
    gpu: Option<Graphics>,
    scene: NativeGestureScene,
    cursor: Point,
    cursor_seen: bool,
    shift: bool,
    serial: u64,
    receipts: u64,
    activations: u64,
    frame_submissions: u64,
    trace: File,
    begin: Instant,
    until: Duration,
    failure: Option<String>,
    pixel_dir: Option<PathBuf>,
    pixels_before: bool,
    pixels_preview: bool,
    pixels_after: bool,
}
impl Probe {
    fn make(trace: File, until: Duration, pixel_dir: Option<PathBuf>) -> Result<Self, String> {
        Ok(Self {
            gpu: None,
            scene: NativeGestureScene::new(Viewport::new(Size::new(720.0, 420.0), 1.0, 1))?,
            cursor: Point::new(0.0, 0.0),
            cursor_seen: false,
            shift: false,
            serial: 0,
            receipts: 0,
            activations: 0,
            frame_submissions: 0,
            trace,
            begin: Instant::now(),
            until,
            failure: None,
            pixel_dir,
            pixels_before: false,
            pixels_preview: false,
            pixels_after: false,
        })
    }
    fn log(&mut self, record: serde_json::Value) {
        let _ = writeln!(self.trace, "{record}");
        let _ = self.trace.flush();
    }
    /// Only winit-delivered events enter this path. The scene owns G04 routing
    /// and BLOB-AC-01 preview/commit; this fixture owns its own GPU quads.
    fn ingress(&mut self, event_name: &str, kind: EventKind) {
        self.serial += 1;
        let serial = self.serial;
        let timestamp = self.begin.elapsed().as_micros() as u64;
        self.log(json!({"kind":"ingress","source":"winit_window_event",
            "event":event_name,"serial":serial,
            "surface":self.scene.surface().0, "geometry_epoch":self.scene.geometry_epoch()}));
        match self.scene.ingest(serial, timestamp, kind) {
            Ok(actions) => {
                self.receipts += 1;
                self.log(json!({"kind":"receipt","source":"blobin_ui_core_input",
                    "serial":serial,"change_count":actions.len(),"revision":self.scene.revision()}));
                for action in actions {
                    match action {
                        Change::Begin { target } => self.log(json!({"kind":"gesture_begin","serial":serial,"target":target.slot})),
                        Change::Preview { target,delta } => self.log(json!({"kind":"gesture_preview","serial":serial,"target":target.slot,"dx":delta.x,"dy":delta.y})),
                        Change::Reordered { target,revision } => self.log(json!({"kind":"gesture_reorder","serial":serial,"target":target.slot,"revision":revision})),
                        Change::NoReorder { target } => self.log(json!({"kind":"gesture_noop","serial":serial,"target":target.slot})),
                        Change::Cancel { target,reason } => self.log(json!({"kind":"gesture_cancel","serial":serial,"target":target.slot,"reason":format!("{reason:?}")})),
                        Change::Activated { target } => {
                            self.activations += 1;
                            self.log(json!({"kind":"activation","serial":serial,"target":target.slot}));
                        }
                    }
                }
                if let Some(g) = &self.gpu {
                    g.window.request_redraw();
                }
            }
            Err(e) => self.log(json!({"kind":"rejected","serial":serial,"reason":e})),
        }
    }
    fn init(&mut self, el: &ActiveEventLoop) -> Result<(), String> {
        let window = Arc::new(
            el.create_window(
                Window::default_attributes()
                    .with_title("blob.in / BLOB-AC-02 Native Gesture Consumer")
                    .with_name("live.gnu6.blobin-ac02", "blobin-ac02")
                    .with_inner_size(LogicalSize::new(720, 420))
                    .with_min_inner_size(LogicalSize::new(560, 330)),
            )
            .map_err(|e| e.to_string())?,
        );
        let mut desc = wgpu::InstanceDescriptor::new_without_display_handle();
        // An isolated RDP namespace may not expose NVIDIA Vulkan. Opt-in to
        // Mesa GL for the transport qualification only; the normal path stays Vulkan.
        desc.backends = if std::env::var_os("BLOBIN_AC02_ALLOW_GL").is_some() {
            wgpu::Backends::VULKAN | wgpu::Backends::GL
        } else {
            wgpu::Backends::VULKAN
        };
        let instance = wgpu::Instance::new(desc);
        let surface = instance
            .create_surface(window.clone())
            .map_err(|e| e.to_string())?;
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::HighPerformance,
            compatible_surface: Some(&surface),
            ..Default::default()
        }))
        .map_err(|e| e.to_string())?;
        let backend = format!("{:?}", adapter.get_info().backend);
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
            label: Some("blobin-ac02-vulkan"),
            ..Default::default()
        }))
        .map_err(|e| e.to_string())?;
        let size = window.inner_size();
        let mut config = surface
            .get_default_config(&adapter, size.width.max(1), size.height.max(1))
            .ok_or("wgpu surface config absent")?;
        config.present_mode = wgpu::PresentMode::AutoVsync;
        if self.pixel_dir.is_some() {
            if !surface
                .get_capabilities(&adapter)
                .usages
                .contains(wgpu::TextureUsages::COPY_SRC)
            {
                return Err("AC03_SURFACE_COPY_SRC_UNSUPPORTED".into());
            }
            match config.format {
                wgpu::TextureFormat::Bgra8Unorm
                | wgpu::TextureFormat::Bgra8UnormSrgb
                | wgpu::TextureFormat::Rgba8Unorm
                | wgpu::TextureFormat::Rgba8UnormSrgb => {}
                other => return Err(format!("AC03_CAPTURE_FORMAT_UNSUPPORTED: {other:?}")),
            }
            config.usage |= wgpu::TextureUsages::COPY_SRC;
        }
        surface.configure(&device, &config);
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("blobin-ac02-geometry"),
            source: wgpu::ShaderSource::Wgsl(SHADER.into()),
        });
        let group_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("rect-uniform"),
            entries: &[wgpu::BindGroupLayoutEntry {
                binding: 0,
                visibility: wgpu::ShaderStages::VERTEX,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset: false,
                    min_binding_size: None,
                },
                count: None,
            }],
        });
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("blobin-ac02-layout"),
            bind_group_layouts: &[Some(&group_layout)],
            immediate_size: 0,
        });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("blobin-ac02-solid-rects"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: Some("vs"),
                buffers: &[],
                compilation_options: Default::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: Some("fs"),
                targets: &[Some(config.format.into())],
                compilation_options: Default::default(),
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: None,
            multisample: wgpu::MultisampleState::default(),
            multiview_mask: None,
            cache: None,
        });
        let viewport = Viewport::new(
            Size::new(
                size.width as f32 / window.scale_factor() as f32,
                size.height as f32 / window.scale_factor() as f32,
            ),
            window.scale_factor() as f32,
            self.scene.geometry_epoch() + 1,
        );
        self.scene.resize(viewport)?;
        self.log(json!({"kind":"window_ready","backend":backend,
            "native_window":true,"physical":[size.width,size.height],
            "scale":window.scale_factor(),"source":"winit_wayland"}));
        println!(
            "BLOBIN_AC02_NATIVE_READY backend={backend} scale={}",
            window.scale_factor()
        );
        self.gpu = Some(Graphics {
            window,
            surface,
            device,
            queue,
            config,
            pipeline,
            group_layout,
        });
        self.gpu.as_ref().unwrap().window.request_redraw();
        Ok(())
    }

    fn draw(&mut self) -> Result<(), String> {
        let Some(gpu) = self.gpu.as_mut() else {
            return Ok(());
        };
        let frame = match gpu.surface.get_current_texture() {
            wgpu::CurrentSurfaceTexture::Success(v)
            | wgpu::CurrentSurfaceTexture::Suboptimal(v) => v,
            wgpu::CurrentSurfaceTexture::Lost | wgpu::CurrentSurfaceTexture::Outdated => {
                gpu.surface.configure(&gpu.device, &gpu.config);
                return Ok(());
            }
            other => return Err(format!("swapchain: {other:?}")),
        };
        let mut groups = Vec::new();
        let viewport = self.scene.viewport();
        for card in self.scene.cards() {
            let rect = card.bounds;
            let base: [f32; 4] = if card.identity == 0 {
                [0.10, 0.53, 0.83, 1.0]
            } else {
                [0.88, 0.38, 0.14, 1.0]
            };
            let lift: f32 = if card.is_dragging {
                0.16
            } else if card.is_focused {
                0.07
            } else {
                0.0
            };
            let color = [
                (base[0] + lift).min(1.0f32),
                (base[1] + lift).min(1.0f32),
                (base[2] + lift).min(1.0f32),
                1.0,
            ];
            let values = [
                rect.x,
                rect.y,
                rect.width,
                rect.height,
                color[0],
                color[1],
                color[2],
                color[3],
                viewport.logical.width,
                viewport.logical.height,
                0.0,
                0.0,
            ];
            let bytes: Vec<u8> = values.iter().flat_map(|v| (*v).to_ne_bytes()).collect();
            let buffer = gpu.device.create_buffer(&wgpu::BufferDescriptor {
                label: Some("AC02 presentation-only quad"),
                size: bytes.len() as u64,
                usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
                mapped_at_creation: false,
            });
            gpu.queue.write_buffer(&buffer, 0, &bytes);
            let group = gpu.device.create_bind_group(&wgpu::BindGroupDescriptor {
                label: Some("AC02 quad bind"),
                layout: &gpu.group_layout,
                entries: &[wgpu::BindGroupEntry {
                    binding: 0,
                    resource: buffer.as_entire_binding(),
                }],
            });
            groups.push((buffer, group));
        }
        let view = frame
            .texture
            .create_view(&wgpu::TextureViewDescriptor::default());
        let mut encoder = gpu
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("AC02 native input frame"),
            });
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("AC02 native 2D controls"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    depth_slice: None,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color {
                            r: 0.055,
                            g: 0.075,
                            b: 0.105,
                            a: 1.0,
                        }),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                ..Default::default()
            });
            pass.set_pipeline(&gpu.pipeline);
            for (_, group) in &groups {
                pass.set_bind_group(0, group, &[]);
                pass.draw(0..6, 0..1);
            }
        }
        // Optional AC-03 witness of the ACTUAL window swapchain texture before
        // present. This is GPU/client pixel evidence, NOT compositor presentation feedback.
        let capture_stage = if self.pixel_dir.is_some() {
            if self.scene.commits() > 0 && !self.pixels_after {
                Some("after")
            } else if self.scene.cards().iter().any(|c| c.is_dragging) && !self.pixels_preview {
                Some("preview")
            } else if self.frame_submissions == 0 && !self.pixels_before {
                Some("before")
            } else {
                None
            }
        } else {
            None
        };
        let capture = if let Some(stage) = capture_stage {
            let width = gpu.config.width;
            let height = gpu.config.height;
            if width == 0 || height == 0 || width > 2048 || height > 2048 {
                return Err("AC03_CAPTURE_SIZE_OUT_OF_BOUNDS".into());
            }
            let pitch = (width * 4).div_ceil(256) * 256;
            let size = u64::from(pitch) * u64::from(height);
            let staging = gpu.device.create_buffer(&wgpu::BufferDescriptor {
                label: Some("AC03 GPU swapchain-readback"),
                size,
                usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
                mapped_at_creation: false,
            });
            encoder.copy_texture_to_buffer(
                wgpu::TexelCopyTextureInfo {
                    texture: &frame.texture,
                    mip_level: 0,
                    origin: wgpu::Origin3d::ZERO,
                    aspect: wgpu::TextureAspect::All,
                },
                wgpu::TexelCopyBufferInfo {
                    buffer: &staging,
                    layout: wgpu::TexelCopyBufferLayout {
                        offset: 0,
                        bytes_per_row: Some(pitch),
                        rows_per_image: Some(height),
                    },
                },
                wgpu::Extent3d {
                    width,
                    height,
                    depth_or_array_layers: 1,
                },
            );
            Some((stage, staging, pitch, width, height))
        } else {
            None
        };
        gpu.queue.submit([encoder.finish()]);
        gpu.window.pre_present_notify();
        gpu.queue.present(frame);
        self.frame_submissions += 1;
        if let Some((stage, staging, pitch, width, height)) = capture {
            let (sender, receiver) = std::sync::mpsc::channel();
            staging.slice(..).map_async(wgpu::MapMode::Read, move |r| {
                let _ = sender.send(r);
            });
            gpu.device
                .poll(wgpu::PollType::Wait {
                    submission_index: None,
                    timeout: Some(Duration::from_secs(8)),
                })
                .map_err(|e| format!("AC03_GPU_POLL_FAILED: {e:?}"))?;
            receiver
                .recv_timeout(Duration::from_secs(2))
                .map_err(|_| "AC03_GPU_MAP_TIMEOUT")?
                .map_err(|e| format!("AC03_GPU_MAP_FAILED: {e:?}"))?;
            let mapped = staging
                .slice(..)
                .get_mapped_range()
                .map_err(|e| format!("AC03_GPU_READ_RANGE_FAILED: {e:?}"))?;
            let mut contiguous = Vec::with_capacity(width as usize * height as usize * 4);
            for row in mapped.chunks_exact(pitch as usize) {
                contiguous.extend_from_slice(&row[..width as usize * 4]);
            }
            drop(mapped);
            staging.unmap();
            let path = self
                .pixel_dir
                .as_ref()
                .ok_or("AC03_PIXEL_PATH_LOST")?
                .join(format!("{stage}.rgba"));
            std::fs::write(&path, &contiguous).map_err(|e| format!("AC03_PIXEL_WRITE: {e}"))?;
            match stage {
                "before" => self.pixels_before = true,
                "preview" => self.pixels_preview = true,
                "after" => self.pixels_after = true,
                _ => {}
            }
            let capture_format = format!("{:?}", gpu.config.format);
            self.log(json!({"kind":"gpu_swapchain_copy","stage":stage,
                "width":width,"height":height,
                "format":capture_format,
                "bytes":contiguous.len(),
                "ui_revision":self.scene.revision(),
                "gesture_commits":self.scene.commits(),
                "compositor_presentation_feedback":false}));
        }
        Ok(())
    }
    fn finish(&mut self) {
        let cancelled = self.scene.close();
        for action in cancelled {
            self.log(json!({"kind":"gesture_shutdown_cancel", "action":format!("{action:?}")}));
        }
        self.log(json!({"kind":"summary","ingress_count":self.serial,
            "receipt_count":self.receipts,"activation_count":self.activations,
            "gesture_commits":self.scene.commits(),"gesture_cancels":self.scene.cancellations(),
            "ui_revision":self.scene.revision(),"frame_submissions":self.frame_submissions,
            "compositor_presented_feedback":false,"physical_input_oracle":false,
            "renderer_owner":"ac02_standalone_fixture","source":"winit_window_event"}));
        println!(
            "BLOBIN_AC02_NATIVE_FINISHED ingress={} receipts={} commits={} submissions={}",
            self.serial,
            self.receipts,
            self.scene.commits(),
            self.frame_submissions
        );
    }
}
impl ApplicationHandler for Probe {
    fn resumed(&mut self, el: &ActiveEventLoop) {
        if self.gpu.is_none() {
            if let Err(e) = self.init(el) {
                self.failure = Some(e);
                el.exit();
            }
        }
    }
    fn window_event(&mut self, el: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        let Some(g) = self.gpu.as_ref() else { return };
        match event {
            WindowEvent::CloseRequested => {
                self.finish();
                el.exit();
            }
            WindowEvent::RedrawRequested => {
                if let Err(e) = self.draw() {
                    self.failure = Some(e);
                    el.exit();
                }
            }
            WindowEvent::Resized(size) => {
                if size.width > 0 && size.height > 0 {
                    let factor = g.window.scale_factor() as f32;
                    let viewport = Viewport::new(
                        Size::new(size.width as f32 / factor, size.height as f32 / factor),
                        factor,
                        self.scene.geometry_epoch() + 1,
                    );
                    if let Err(e) = self.scene.resize(viewport) {
                        self.failure = Some(e);
                        el.exit();
                        return;
                    }
                    if let Some(gpu) = self.gpu.as_mut() {
                        gpu.config.width = size.width;
                        gpu.config.height = size.height;
                        gpu.surface.configure(&gpu.device, &gpu.config);
                        gpu.window.request_redraw();
                    }
                    self.log(
                        json!({"kind":"resize","geometry_epoch":self.scene.geometry_epoch(),
                        "physical":[size.width,size.height],"scale":factor}),
                    );
                }
            }
            WindowEvent::ScaleFactorChanged { scale_factor, .. } => {
                let size = g.window.inner_size();
                let viewport = Viewport::new(
                    Size::new(
                        size.width as f32 / scale_factor as f32,
                        size.height as f32 / scale_factor as f32,
                    ),
                    scale_factor as f32,
                    self.scene.geometry_epoch() + 1,
                );
                if let Err(e) = self.scene.resize(viewport) {
                    self.failure = Some(e);
                    el.exit();
                }
            }
            WindowEvent::CursorMoved { position, .. } => {
                self.cursor = Point::new(position.x as f32, position.y as f32);
                self.cursor_seen = true;
                self.ingress(
                    "cursor_moved",
                    EventKind::PointerMove {
                        pointer: 1,
                        position: self.cursor,
                        units: Units::Physical,
                    },
                );
            }
            WindowEvent::MouseInput {
                state,
                button: MouseButton::Left,
                ..
            } => {
                if self.cursor_seen {
                    let position = self.cursor;
                    let kind = if state == ElementState::Pressed {
                        EventKind::PointerDown {
                            pointer: 1,
                            button: 1,
                            position,
                            units: Units::Physical,
                        }
                    } else {
                        EventKind::PointerUp {
                            pointer: 1,
                            button: 1,
                            position,
                            units: Units::Physical,
                        }
                    };
                    self.ingress(
                        if state == ElementState::Pressed {
                            "mouse_down"
                        } else {
                            "mouse_up"
                        },
                        kind,
                    );
                }
            }
            WindowEvent::KeyboardInput { event, .. } => {
                let key = match event.logical_key {
                    WinitKey::Named(NamedKey::Tab) => Some(Key::Tab),
                    WinitKey::Named(NamedKey::Enter) => Some(Key::Enter),
                    WinitKey::Named(NamedKey::Space) => Some(Key::Space),
                    WinitKey::Named(NamedKey::Escape) => Some(Key::Escape),
                    _ => None,
                };
                if let Some(key) = key {
                    let kind = if event.state == ElementState::Pressed {
                        EventKind::KeyDown {
                            key,
                            shift: self.shift,
                            repeat: event.repeat,
                        }
                    } else {
                        EventKind::KeyUp { key }
                    };
                    self.ingress("key", kind);
                }
            }
            WindowEvent::ModifiersChanged(modifiers) => {
                self.shift = modifiers.state().contains(ModifiersState::SHIFT);
            }
            WindowEvent::Focused(false) => self.ingress("blur", EventKind::WindowBlur),
            WindowEvent::Focused(true) => {
                self.log(json!({"kind":"focus_enter","source":"winit_window_event"}))
            }
            _ => {}
        }
    }
    fn about_to_wait(&mut self, el: &ActiveEventLoop) {
        if self.begin.elapsed() >= self.until {
            self.finish();
            el.exit();
        } else {
            el.set_control_flow(ControlFlow::WaitUntil(self.begin + self.until));
        }
    }
}
fn main() -> Result<(), String> {
    let mut trace = None;
    let mut run_ms = 12_000u64;
    let mut pixel_dir: Option<PathBuf> = None;
    for arg in std::env::args().skip(1) {
        if let Some(value) = arg.strip_prefix("--trace=") {
            trace = Some(PathBuf::from(value));
        } else if let Some(value) = arg.strip_prefix("--pixel-evidence-dir=") {
            pixel_dir = Some(PathBuf::from(value));
        } else if let Some(value) = arg.strip_prefix("--run-ms=") {
            run_ms = value.parse().map_err(|e| format!("{e}"))?;
            if !(1000..=60_000).contains(&run_ms) {
                return Err("run-ms must be 1000..=60000".into());
            }
        } else {
            return Err(format!("unknown argument: {arg}"));
        }
    }
    let trace = File::create(trace.ok_or("missing --trace=PATH")?).map_err(|e| e.to_string())?;
    if let Some(dir) = &pixel_dir {
        if !dir.is_dir() {
            return Err("AC03_PIXEL_EVIDENCE_DIRECTORY_REQUIRED".into());
        }
    }
    let mut app = Probe::make(trace, Duration::from_millis(run_ms), pixel_dir)?;
    let loop_ = EventLoop::new().map_err(|e| e.to_string())?;
    loop_.set_control_flow(ControlFlow::Wait);
    loop_.run_app(&mut app).map_err(|e| e.to_string())?;
    if let Some(error) = app.failure {
        return Err(error);
    }
    if app.frame_submissions == 0 {
        return Err("no native frame submissions".into());
    }
    Ok(())
}
