//! UI-G04/B isolated compositor input probe. This is a native Wayland fixture,
//! not the production scene, and its submitted frames are not presentation feedback.
use blobin_ui_core::input::{EventKind, InputEvent, InputReceipt, InputRouter, Key, Point, Units};
use blobin_ui_core::layout::{
    self, Axis, Insets, LayoutSnapshot, LayoutStyles, Length, Size, Style, Viewport,
};
use blobin_ui_core::{NodeId, NodeProperties, Role, SurfaceId, UiTree};
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
    tree: UiTree,
    styles: LayoutStyles,
    router: InputRouter,
    surface_id: SurfaceId,
    left: NodeId,
    right: NodeId,
    geometry: Option<LayoutSnapshot>,
    viewport: Viewport,
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
}
impl Probe {
    fn make(trace: File, until: Duration) -> Result<Self, String> {
        let mut tree = UiTree::new();
        let s = SurfaceId(1);
        let mut ids = Vec::new();
        tree.transact(|tx| {
            tx.open_surface(s)?;
            let root = tx.append_root(s, NodeProperties::new(Role::Container, "UI-G04B"))?;
            ids.push(root);
            ids.push(tx.append_child(root, NodeProperties::new(Role::Button, "A / left"))?);
            ids.push(tx.append_child(root, NodeProperties::new(Role::Button, "B / right"))?);
            Ok(())
        })
        .map_err(|e| format!("{e}"))?;
        let mut styles = LayoutStyles::new();
        let mut root = Style::fill();
        root.axis = Axis::Row;
        root.padding = Insets::uniform(24.0);
        root.gap = 16.0;
        root.clip_children = true;
        styles
            .set(&tree.snapshot(), ids[0], root)
            .map_err(|e| format!("{e}"))?;
        for id in [ids[1], ids[2]] {
            styles
                .set(
                    &tree.snapshot(),
                    id,
                    Style {
                        width: Length::Px(170.0),
                        height: Length::Px(120.0),
                        ..Style::default()
                    },
                )
                .map_err(|e| format!("{e}"))?;
        }
        Ok(Self {
            gpu: None,
            tree,
            styles,
            router: InputRouter::new(),
            surface_id: s,
            left: ids[1],
            right: ids[2],
            geometry: None,
            viewport: Viewport::new(Size::new(520.0, 280.0), 1.0, 1),
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
        })
    }
    fn log(&mut self, record: serde_json::Value) {
        let _ = writeln!(self.trace, "{record}");
        let _ = self.trace.flush();
    }
    fn recalc(&mut self) {
        match layout::compute(
            &self.tree.snapshot(),
            &self.styles,
            self.surface_id,
            self.viewport,
        ) {
            Ok(layout) => {
                self.log(json!({"kind":"layout","epoch":layout.stamp.geometry_epoch,
                    "width":self.viewport.logical.width,"height":self.viewport.logical.height,
                    "scale":self.viewport.scale_factor,"left":format!("{:?}",layout.get(self.left).unwrap().rect),
                    "right":format!("{:?}",layout.get(self.right).unwrap().rect)}));
                self.geometry = Some(layout);
            }
            Err(e) => self.failure = Some(format!("layout: {e}")),
        }
    }

    fn ingress(&mut self, event_name: &str, kind: EventKind) {
        let Some(layout) = self.geometry.as_ref() else {
            return;
        };
        self.serial += 1;
        let event = InputEvent::for_layout(
            layout,
            self.serial,
            self.begin.elapsed().as_micros() as u64,
            kind,
        );
        self.log(json!({"kind":"ingress","source":"winit_window_event",
            "event":event_name,"serial":event.serial,"surface":event.surface.0,
            "surface_epoch":event.surface_epoch,"geometry_epoch":event.geometry_epoch}));
        let layout = self
            .geometry
            .as_ref()
            .expect("layout not removed by logging");
        match self.router.dispatch(
            &self.tree.snapshot(),
            &self.styles,
            layout,
            self.viewport,
            event,
        ) {
            Ok(r) => self.receipt(event_name, r),
            Err(e) => self.log(json!({"kind":"rejected","serial":self.serial,
                "reason":format!("{e:?}")})),
        }
    }
    fn receipt(&mut self, event_name: &str, receipt: InputReceipt) {
        self.receipts += 1;
        let target = receipt.route.as_ref().map(|r| {
            if r.target == self.left {
                "left"
            } else if r.target == self.right {
                "right"
            } else {
                "other"
            }
        });
        let activation = receipt.activated.map(|id| {
            if id == self.left {
                "left"
            } else if id == self.right {
                "right"
            } else {
                "other"
            }
        });
        if activation.is_some() {
            self.activations += 1;
        }
        self.log(json!({"kind":"receipt","source":"blobin_ui_core_input",
            "serial":receipt.serial,"event":event_name,
            "target":target,"activation":activation,
            "capture":receipt.pointer_capture.map(|id|id.slot),
            "focus":receipt.focus.map(|id|id.slot),
            "capture_path":receipt.route.as_ref().map(|r|r.capture_path.iter().map(|id|id.slot).collect::<Vec<_>>()),
            "bubble_path":receipt.route.as_ref().map(|r|r.bubble_path.iter().map(|id|id.slot).collect::<Vec<_>>())}));
        if let Some(g) = &self.gpu {
            g.window.request_redraw();
        }
    }
    fn init(&mut self, el: &ActiveEventLoop) -> Result<(), String> {
        let window = Arc::new(
            el.create_window(
                Window::default_attributes()
                    .with_title("blob.in / UI-G04B Wayland input trace")
                    .with_name("live.gnu6.blobin-g04b", "blobin-g04b")
                    .with_inner_size(LogicalSize::new(520, 280))
                    .with_min_inner_size(LogicalSize::new(440, 240)),
            )
            .map_err(|e| e.to_string())?,
        );
        let mut desc = wgpu::InstanceDescriptor::new_without_display_handle();
        // An isolated RDP namespace may not expose NVIDIA Vulkan. Opt-in to
        // Mesa GL for the transport qualification only; the normal path stays Vulkan.
        desc.backends = if std::env::var_os("BLOBIN_G04B_ALLOW_GL").is_some() {
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
            label: Some("blobin-g04b-vulkan"),
            ..Default::default()
        }))
        .map_err(|e| e.to_string())?;
        let size = window.inner_size();
        let mut config = surface
            .get_default_config(&adapter, size.width.max(1), size.height.max(1))
            .ok_or("wgpu surface config absent")?;
        config.present_mode = wgpu::PresentMode::AutoVsync;
        surface.configure(&device, &config);
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("blobin-g04b-geometry"),
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
            label: Some("blobin-g04b-layout"),
            bind_group_layouts: &[Some(&group_layout)],
            immediate_size: 0,
        });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("blobin-g04b-solid-rects"),
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
        self.viewport = Viewport::new(
            Size::new(
                size.width as f32 / window.scale_factor() as f32,
                size.height as f32 / window.scale_factor() as f32,
            ),
            window.scale_factor() as f32,
            1,
        );
        self.log(json!({"kind":"window_ready","backend":backend,
            "native_window":true,"physical":[size.width,size.height],
            "scale":window.scale_factor(),"source":"winit_wayland"}));
        println!(
            "BLOBIN_G04B_NATIVE_READY backend={backend} scale={}",
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
        self.recalc();
        self.gpu.as_ref().unwrap().window.request_redraw();
        Ok(())
    }

    fn draw(&mut self) -> Result<(), String> {
        let Some(gpu) = self.gpu.as_mut() else {
            return Ok(());
        };
        let Some(layout) = self.geometry.as_ref() else {
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
        for (id, rgb) in [
            (self.left, [0.10, 0.53, 0.83, 1.0]),
            (self.right, [0.88, 0.38, 0.14, 1.0]),
        ] {
            if let Some(rect) = layout.get(id).map(|b| b.rect) {
                let color = if self.router.focus(self.surface_id) == Some(id) {
                    [rgb[0] + 0.09, rgb[1] + 0.09, rgb[2] + 0.09, 1.0]
                } else {
                    rgb
                };
                let values = [
                    rect.x,
                    rect.y,
                    rect.width,
                    rect.height,
                    color[0],
                    color[1],
                    color[2],
                    color[3],
                    self.viewport.logical.width,
                    self.viewport.logical.height,
                    0.0,
                    0.0,
                ];
                let bytes: Vec<u8> = values.iter().flat_map(|v| (*v).to_ne_bytes()).collect();
                let buffer = gpu.device.create_buffer(&wgpu::BufferDescriptor {
                    label: Some("G04B quad geometry"),
                    size: bytes.len() as u64,
                    usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
                    mapped_at_creation: false,
                });
                gpu.queue.write_buffer(&buffer, 0, &bytes);
                let group = gpu.device.create_bind_group(&wgpu::BindGroupDescriptor {
                    label: Some("G04B rect bind"),
                    layout: &gpu.group_layout,
                    entries: &[wgpu::BindGroupEntry {
                        binding: 0,
                        resource: buffer.as_entire_binding(),
                    }],
                });
                groups.push((buffer, group));
            }
        }
        let view = frame
            .texture
            .create_view(&wgpu::TextureViewDescriptor::default());
        let mut encoder = gpu
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("G04B native input frame"),
            });
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("G04B native 2D controls"),
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
        gpu.queue.submit([encoder.finish()]);
        gpu.window.pre_present_notify();
        gpu.queue.present(frame);
        self.frame_submissions += 1;
        Ok(())
    }
    fn finish(&mut self) {
        self.log(json!({"kind":"summary","ingress_count":self.serial,
            "receipt_count":self.receipts,"activation_count":self.activations,
            "frame_submissions":self.frame_submissions,"g04b_visual_frame_presented_verified":false,
            "source":"winit_window_event"}));
        println!(
            "BLOBIN_G04B_NATIVE_FINISHED ingress={} receipts={} activations={} submissions={}",
            self.serial, self.receipts, self.activations, self.frame_submissions
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
                    self.viewport.logical =
                        Size::new(size.width as f32 / factor, size.height as f32 / factor);
                    self.viewport.geometry_epoch += 1;
                    if let Some(gpu) = self.gpu.as_mut() {
                        gpu.config.width = size.width;
                        gpu.config.height = size.height;
                        gpu.surface.configure(&gpu.device, &gpu.config);
                    }
                    self.recalc();
                    if let Some(gpu) = self.gpu.as_ref() {
                        gpu.window.request_redraw();
                    }
                }
            }
            WindowEvent::ScaleFactorChanged { scale_factor, .. } => {
                let size = g.window.inner_size();
                self.viewport.scale_factor = scale_factor as f32;
                self.viewport.logical = Size::new(
                    size.width as f32 / scale_factor as f32,
                    size.height as f32 / scale_factor as f32,
                );
                self.viewport.geometry_epoch += 1;
                self.recalc();
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
    for arg in std::env::args().skip(1) {
        if let Some(value) = arg.strip_prefix("--trace=") {
            trace = Some(PathBuf::from(value));
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
    let mut app = Probe::make(trace, Duration::from_millis(run_ms))?;
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
