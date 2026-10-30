//! The native surface: a winit Wayland window, wgpu presentation, egui controls.
//!
//! The event loop never blocks on the runtime. IPC runs on the client's own
//! threads and arrives here as user events; frames are uploaded to a GPU
//! texture as they arrive and their mapping is released immediately.

use std::collections::VecDeque;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use blob_frame::{
    Backend, Client, ClientConfig, ClientEvent, CsgOp, FrameReady, ReceivedFrame, RenderRequest, Session, ViewMode,
};
use egui::{Color32, Pos2, Sense, Stroke, Vec2};
use serde_json::json;
use winit::application::ApplicationHandler;
use winit::event::{StartCause, WindowEvent};
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop, EventLoopProxy};
use winit::platform::wayland::WindowAttributesExtWayland;
use winit::window::{Window, WindowId};

use crate::scene::{Camera, Lab, SceneState, MAX_UI_PRIMITIVES, MAX_ZOOM, MIN_ZOOM};
use crate::ac01a_native_gpu::NativeOverlayRenderer;
use crate::ac01a_toggle::{NativeToggleHost, SIZE as NATIVE_TOGGLE_SIZE};
use crate::ac01b_action::{NativeActionHost, SIZE as NATIVE_ACTION_SIZE};
use crate::ac01c_reset::{NativeResetHost, SIZE as NATIVE_RESET_SIZE};
use blobin_ui_scene::{ActionPalette, ActionVisualState};
use blobin_ui_core::layout::{Rect as UiRect, Size as UiSize};
use blobin_ui_scene::{Rgba8, TogglePalette, ToggleVisualState};
use blobin_ui_scene::composition::{compose, LayerStep, SceneLayer, MAX_NATIVE_UI_COMMANDS};
use crate::ac04_scene_gestures::{CanvasTransactions, Commit};
use blobin_ui_core::gestures::Translation;
use crate::scheduler::{fit, Fit, Scheduler, Verdict};
use crate::theme;
use crate::trace::Trace;
use crate::view::{Rect, View};

pub const APP_ID: &str = "live.gnu6.blobin-showcase";
const LOG_LINES: usize = 40;

pub struct Options {
    pub socket: PathBuf,
    pub trace: Option<PathBuf>,
    pub lab: Lab,
    pub backend: Backend,
    pub size: (u32, u32),
    /// Run the scripted edit sequence (see [`EXERCISE`]) and then quit.
    pub exercise: bool,
}

/// A deterministic sequence of edits applied through the same model operations as
/// the controls, one step per presented frame. Used by the E2E to check that the
/// runtime's output follows scene, view and backend changes.
#[derive(Clone, Copy, Debug)]
pub enum Step {
    MoveCircle { index: usize, dx: f32, dy: f32 },
    ScaleRadius { index: usize, factor: f32 },
    CycleOp { index: usize },
    View(ViewMode),
    Backend(Backend),
    Lab(Lab),
    Zoom(f32),
    ResetCamera,
}

pub const EXERCISE: &[Step] = &[
    Step::Lab(Lab::Smooth),
    Step::MoveCircle { index: 1, dx: 0.06, dy: 0.02 },
    Step::ScaleRadius { index: 2, factor: 1.25 },
    Step::CycleOp { index: 3 },
    Step::View(ViewMode::Distance),
    Step::View(ViewMode::Normals),
    Step::View(ViewMode::Coverage),
    Step::View(ViewMode::Lit),
    Step::Lab(Lab::Csg),
    Step::Zoom(1.6),
    Step::ResetCamera,
    Step::Backend(Backend::Cpu),
    Step::Backend(Backend::Vulkan),
    Step::Backend(Backend::Cuda),
];

#[derive(Debug)]
pub enum UserEvent {
    Client(ClientEvent),
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Level {
    Info,
    Warn,
    Error,
}

struct LogLine {
    at: Instant,
    level: Level,
    text: String,
}

enum Conn {
    Connecting { attempt: u32 },
    Failed { reason: String, retry_in: Duration },
    Connected(Arc<Session>),
}

/// The frame on screen and the client-side context it was requested with.
struct Presented {
    meta: FrameReady,
    camera: Camera,
    scale: f32,
    round_trip: Duration,
    at: Instant,
}

/// Client-side context of the request in flight (the wire carries no camera).
struct Pending {
    request_id: u64,
    camera: Camera,
    scale: f32,
    backend: Backend,
    size: (u32, u32),
}

#[derive(Clone, Copy, PartialEq)]
struct Viewport {
    rect: Rect,
    physical: (u32, u32),
}

struct Model {
    scene: SceneState,
    camera: Camera,
    backend: Backend,
    view: ViewMode,
    sched: Scheduler,
    conn: Conn,
    presented: Option<Presented>,
    pending: Option<Pending>,
    viewport: Option<Viewport>,
    fit: Option<Fit>,
    bounds_error: Option<String>,
    log: VecDeque<LogLine>,
    overlay: bool,
    native_toggle: NativeToggleHost,
    native_toggle_enabled: bool,
    native_action: NativeActionHost,
    native_action_enabled: bool,
    native_reset:NativeResetHost,
    native_reset_enabled:bool,
    help: bool,
    gestures: CanvasTransactions,
    ping_rtt: Option<Duration>,
    rejected: u64,
    errors: u64,
    quit: bool,
}

impl Model {
    fn new(opts: &Options) -> Self {
        Self {
            scene: SceneState::new(opts.lab),
            camera: Camera::default(),
            backend: opts.backend,
            view: opts.lab.default_view(),
            sched: Scheduler::new(),
            conn: Conn::Connecting { attempt: 0 },
            presented: None,
            pending: None,
            viewport: None,
            fit: None,
            bounds_error: None,
            log: VecDeque::new(),
            overlay: true,
            native_toggle: NativeToggleHost::new().expect("01A core initializes"),
            native_toggle_enabled: std::env::var_os("BLOB_UI_01A_LEGACY").is_none(),
            native_action: NativeActionHost::new().expect("01B core initializes"),
            native_action_enabled: std::env::var_os("BLOB_UI_01B_LEGACY").is_none(),
            native_reset:NativeResetHost::new().expect("01C G02 control initializes"),
            native_reset_enabled:std::env::var_os("BLOB_UI_01C_LEGACY").is_none(),
            help: false,
            gestures: CanvasTransactions::new(),
            ping_rtt: None,
            rejected: 0,
            errors: 0,
            quit: false,
        }
    }

    fn log(&mut self, level: Level, text: impl Into<String>) {
        let text = text.into();
        match level {
            Level::Info => log::info!("{text}"),
            Level::Warn => log::warn!("{text}"),
            Level::Error => log::error!("{text}"),
        }
        if self.log.len() == LOG_LINES {
            self.log.pop_front();
        }
        self.log.push_back(LogLine { at: Instant::now(), level, text });
    }

    fn session(&self) -> Option<&Arc<Session>> {
        match &self.conn {
            Conn::Connected(s) => Some(s),
            _ => None,
        }
    }

    /// True when the peer identifies itself, or its frames, as the test fixture.
    fn test_fixture(&self) -> bool {
        self.session().is_some_and(|s| s.server.contains("TEST-FIXTURE"))
            || self.presented.as_ref().is_some_and(|p| p.meta.qualification.starts_with("TEST_FIXTURE"))
    }

    fn set_lab(&mut self, lab: Lab) {
        self.gestures.clear_history();
        self.scene = SceneState::new(lab);
        self.view = lab.default_view();
        self.camera = Camera::default();
        self.sched.invalidate();
    }
}

struct FrameTexture {
    texture: wgpu::Texture,
    id: egui::TextureId,
    size: (u32, u32),
}

struct Gfx {
    // Field order is drop order: surface before window.
    surface: wgpu::Surface<'static>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    config: wgpu::SurfaceConfiguration,
    renderer: egui_wgpu::Renderer,
    native_overlay: NativeOverlayRenderer,
    private_capture_dir: Option<PathBuf>,
    private_capture_kind: Option<&'static str>,
    egui: egui_winit::State,
    frame_tex: Option<FrameTexture>,
    adapter: String,
    window: Arc<Window>,
}

pub struct App {
    opts: Options,
    proxy: Mutex<EventLoopProxy<UserEvent>>,
    gfx: Option<Gfx>,
    client: Option<Client>,
    m: Model,
    trace: Trace,
    repaint_at: Option<Instant>,
    last_physical: Option<(u32, u32)>,
    captured_toggle_states: u16,
    exercise: Option<usize>,
    exercise_due: Option<Instant>,
    pub exit: Result<(), String>,
}

/// Dwell time on each exercised state, so it can be observed and captured.
const EXERCISE_DWELL: Duration = Duration::from_millis(1500);

pub fn run(opts: Options) -> Result<(), String> {
    let event_loop = EventLoop::<UserEvent>::with_user_event().build().map_err(|e| e.to_string())?;
    event_loop.set_control_flow(ControlFlow::Wait);
    let trace = Trace::open(opts.trace.as_deref()).map_err(|e| format!("trace: {e}"))?;
    let exercise = opts.exercise.then_some(0);
    let mut app = App {
        m: Model::new(&opts),
        proxy: Mutex::new(event_loop.create_proxy()),
        opts,
        gfx: None,
        client: None,
        trace,
        repaint_at: None,
        last_physical: None,
        captured_toggle_states: 0,
        exercise,
        exercise_due: None,
        exit: Ok(()),
    };
    event_loop.run_app(&mut app).map_err(|e| e.to_string())?;
    app.exit
}

impl App {
    fn init(&mut self, el: &ActiveEventLoop) -> Result<(), String> {
        let attrs = Window::default_attributes()
            .with_title("blob.in — showcase")
            .with_name(APP_ID, "blobin-showcase")
            .with_inner_size(winit::dpi::LogicalSize::new(self.opts.size.0, self.opts.size.1))
            .with_min_inner_size(winit::dpi::LogicalSize::new(720, 460));
        let window = Arc::new(el.create_window(attrs).map_err(|e| format!("window: {e}"))?);

        let mut desc = wgpu::InstanceDescriptor::new_without_display_handle();
        desc.backends = wgpu::Backends::VULKAN;
        let instance = wgpu::Instance::new(desc);
        let surface = instance.create_surface(window.clone()).map_err(|e| format!("surface: {e}"))?;
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::HighPerformance,
            compatible_surface: Some(&surface),
            ..Default::default()
        }))
        .map_err(|e| format!("no compatible GPU adapter: {e}"))?;
        let info = adapter.get_info();
        let adapter_name = format!("{} ({:?}, {})", info.name, info.backend, info.driver);
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
            label: Some("blobin-showcase"),
            ..Default::default()
        }))
        .map_err(|e| format!("device: {e}"))?;

        let size = window.inner_size();
        let mut config = surface
            .get_default_config(&adapter, size.width.max(1), size.height.max(1))
            .ok_or("surface not supported by adapter")?;
        let caps = surface.get_capabilities(&adapter);
        // egui blends in gamma space and prefers a non-sRGB target.
        if let Some(f) = caps.formats.iter().find(|f| !f.is_srgb()) {
            config.format = *f;
        }
        config.present_mode = wgpu::PresentMode::AutoVsync;
        config.alpha_mode = wgpu::CompositeAlphaMode::Opaque;
        // Test-only GPU pixel witness; permitted ONLY on the dedicated private
        // Weston socket, never the operator's regular Hyprland session.
        let private_capture_dir = std::env::var_os("BLOB_UI_01A_CAPTURE_DIR")
            .map(PathBuf::from)
            .filter(|dir| {
                dir.is_dir() && std::env::var("WAYLAND_DISPLAY")
                    .is_ok_and(|v| v.starts_with("blob-ui-01a-private-"))
            });
        let reset_capture_dir=std::env::var_os("BLOB_UI_01C_CAPTURE_DIR")
            .map(PathBuf::from).filter(|dir|{
                dir.is_dir() && std::env::var("WAYLAND_DISPLAY")
                    .is_ok_and(|v|v.starts_with("blob-ui-01c-private-"))
            });
        if reset_capture_dir.is_some() {
            // An isolated lab-specific initial condition, never a production
            // default. No active Hyprland input or camera state is touched.
            self.m.camera=Camera{cx:0.18,cy:-0.12,zoom:1.45};
            self.trace.emit("ui01c_private_camera_seed",json!({
                "cx":self.m.camera.cx,"cy":self.m.camera.cy,
                "zoom":self.m.camera.zoom,
                "private_weston_only":true
            }));
        }
        let stress_capture_dir=std::env::var_os("BLOB_UI_01D_CAPTURE_DIR")
            .map(PathBuf::from).filter(|dir|{
                dir.is_dir() && std::env::var("BLOB_UI_01D_STRESS").as_deref()==Ok("1")
                && std::env::var("WAYLAND_DISPLAY").is_ok_and(
                    |v|v.starts_with("blob-ui-01d-private-"))
            });
        let vector_capture_dir=std::env::var_os("BLOB_UI_01E_CAPTURE_DIR")
            .map(PathBuf::from).filter(|dir|{
                dir.is_dir() && std::env::var("BLOB_UI_01E_STRESS").as_deref()==Ok("1")
                && std::env::var("WAYLAND_DISPLAY").is_ok_and(
                    |v|v.starts_with("blob-ui-01e-private-"))
            });
        let bezier_capture_dir=std::env::var_os("BLOB_UI_01F_CAPTURE_DIR")
            .map(PathBuf::from).filter(|dir|{
                dir.is_dir() && std::env::var("BLOB_UI_01F_STRESS").as_deref()==Ok("1")
                && std::env::var("WAYLAND_DISPLAY").is_ok_and(
                    |v|v.starts_with("blob-ui-01f-private-"))
            });
        let closed_capture_dir=std::env::var_os("BLOB_UI_01G_CAPTURE_DIR")
            .map(PathBuf::from).filter(|dir|{
                dir.is_dir() && std::env::var("BLOB_UI_01G_STRESS").as_deref()==Ok("1")
                && std::env::var("WAYLAND_DISPLAY").is_ok_and(
                    |v|v.starts_with("blob-ui-01g-private-"))
            });
        let concave_capture_dir=std::env::var_os("BLOB_UI_01H_CAPTURE_DIR")
            .map(PathBuf::from).filter(|dir|{
                dir.is_dir() && std::env::var("BLOB_UI_01H_STRESS").as_deref()==Ok("1")
                && std::env::var("WAYLAND_DISPLAY").is_ok_and(
                    |v|v.starts_with("blob-ui-01h-private-"))
            });
        let aa_capture_dir=std::env::var_os("BLOB_UI_01I_CAPTURE_DIR")
            .map(PathBuf::from).filter(|dir|{
                dir.is_dir() && std::env::var("BLOB_UI_01I_AA").as_deref()==Ok("1")
                && std::env::var("WAYLAND_DISPLAY").is_ok_and(
                    |v|v.starts_with("blob-ui-01i-private-"))
            });
        if stress_capture_dir.is_some() || vector_capture_dir.is_some() ||
           bezier_capture_dir.is_some() || closed_capture_dir.is_some() || concave_capture_dir.is_some() || aa_capture_dir.is_some() {
            self.m.camera=Camera{cx:0.18,cy:-0.12,zoom:1.45};
            self.trace.emit(if stress_capture_dir.is_some()
                {"ui01d_private_camera_seed"} else if vector_capture_dir.is_some()
                {"ui01e_private_camera_seed"} else if bezier_capture_dir.is_some()
                {"ui01f_private_camera_seed"} else if closed_capture_dir.is_some()
                {"ui01g_private_camera_seed"} else if concave_capture_dir.is_some()
                {"ui01h_private_camera_seed"} else {"ui01i_private_camera_seed"},
                json!({"camera_nondefault":true,"private_weston_only":true}));
        }
        let action_capture_dir=std::env::var_os("BLOB_UI_01B_CAPTURE_DIR")
            .map(PathBuf::from).filter(|dir|{
                dir.is_dir() && std::env::var("WAYLAND_DISPLAY")
                    .is_ok_and(|v|v.starts_with("blob-ui-01b-private-"))
            });
        let private_capture_kind=if private_capture_dir.is_some() {Some("01a")}
            else if action_capture_dir.is_some() {Some("01b")}
            else if reset_capture_dir.is_some(){Some("01c")}
            else if stress_capture_dir.is_some(){Some("01d")}
            else if vector_capture_dir.is_some(){Some("01e")}
            else if bezier_capture_dir.is_some(){Some("01f")}
            else if closed_capture_dir.is_some(){Some("01g")}
            else if concave_capture_dir.is_some(){Some("01h")}
            else if aa_capture_dir.is_some(){Some("01i")} else {None};
        let private_capture_dir=private_capture_dir.or(action_capture_dir)
            .or(reset_capture_dir).or(stress_capture_dir).or(vector_capture_dir)
            .or(bezier_capture_dir).or(closed_capture_dir).or(concave_capture_dir).or(aa_capture_dir);
        if private_capture_dir.is_some() {
            if !caps.usages.contains(wgpu::TextureUsages::COPY_SRC) {
                return Err("01A swapchain COPY_SRC unsupported by adapter".into());
            }
            config.usage |= wgpu::TextureUsages::COPY_SRC;
        }
        surface.configure(&device, &config);

        let renderer = egui_wgpu::Renderer::new(&device, config.format, egui_wgpu::RendererOptions::default());
        let native_overlay = NativeOverlayRenderer::new(&device, config.format);
        let ctx = egui::Context::default();
        theme::apply(&ctx);
        let max_side = device.limits().max_texture_dimension_2d as usize;
        let egui = egui_winit::State::new(
            ctx,
            egui::ViewportId::ROOT,
            &window,
            Some(window.scale_factor() as f32),
            None,
            Some(max_side),
        );
        self.trace.emit(
            "window",
            json!({"adapter": adapter_name, "surface_format": format!("{:?}", config.format),
                   "inner_physical": [size.width, size.height], "scale_factor": window.scale_factor()}),
        );
        self.m.log(Level::Info, format!("fenêtre Wayland prête · {adapter_name}"));
        self.gfx = Some(Gfx { surface, device, queue, config, renderer, native_overlay, private_capture_dir, private_capture_kind, egui, frame_tex: None, adapter: adapter_name, window });

        let proxy = self.proxy.lock().unwrap().clone();
        let proxy = Mutex::new(proxy);
        self.client = Some(Client::spawn(ClientConfig::new(self.opts.socket.clone()), move |e| {
            let _ = proxy.lock().unwrap().send_event(UserEvent::Client(e));
        }));
        Ok(())
    }

    fn shutdown(&mut self, el: &ActiveEventLoop) {
        if let Some(mut c) = self.client.take() {
            c.shutdown();
        }
        if let Some(g) = self.gfx.as_mut() {
            if let Some(t) = g.frame_tex.take() {
                g.renderer.free_texture(&t.id);
                t.texture.destroy();
            }
        }
        let c = self.m.sched.counters;
        self.trace.emit(
            "shutdown",
            json!({"clean": true, "client_threads_joined": true, "frame_texture_released": true,
                   "issued": c.issued, "presented": c.presented, "stale": c.stale, "failed": c.failed,
                   "rejected": self.m.rejected, "errors": self.m.errors}),
        );
        el.exit();
    }

    fn redraw(&mut self) {
        let Some(g) = self.gfx.as_mut() else { return };
        let raw = g.egui.take_egui_input(&g.window);
        let ctx = g.egui.egui_ctx().clone();
        let tex = g.frame_tex.as_ref().map(|t| t.id);
        let adapter = g.adapter.clone();
        let socket = self.opts.socket.clone();
        let m = &mut self.m;
        let before_commits = m.gestures.commits();
        let before_cancels = m.gestures.cancellations();
        let before_active = m.gestures.active();
        let mut out = ctx.run_ui(raw, |ui| ui_root(ui, m, tex, &adapter, &socket));
        if m.gestures.active() || before_active || m.gestures.commits() != before_commits
            || m.gestures.cancellations() != before_cancels
        {
            self.trace.emit("ac05_gesture_state", json!({
                "active":m.gestures.active(),
                "commits":m.gestures.commits(),
                "cancels":m.gestures.cancellations(),
                "selected":m.scene.selected,
                "selected_position":m.scene.selected.and_then(|id|m.scene.get(id).map(|c|[c.x,c.y])),
                "preview_position":m.scene.selected.and_then(|id|m.gestures.preview_position(id).map(|p|[p.0,p.1])),
                "scheduler_revision":m.sched.revision()
            }));
        }
        g.egui.handle_platform_output(&g.window, out.platform_output);

        let ppp = out.pixels_per_point;
        let jobs = ctx.tessellate(out.shapes, ppp);
        for (id, deltas) in &out.textures_delta.set {
            for delta in deltas {
                g.renderer.update_texture(&g.device, &g.queue, *id, delta);
            }
        }
        let frame = match g.surface.get_current_texture() {
            wgpu::CurrentSurfaceTexture::Success(f) | wgpu::CurrentSurfaceTexture::Suboptimal(f) => Some(f),
            wgpu::CurrentSurfaceTexture::Outdated | wgpu::CurrentSurfaceTexture::Lost => {
                g.surface.configure(&g.device, &g.config);
                None
            }
            other => {
                log::debug!("surface texture unavailable: {other:?}");
                None
            }
        };
        if let Some(frame) = frame {
            let view = frame.texture.create_view(&wgpu::TextureViewDescriptor::default());
            let screen = egui_wgpu::ScreenDescriptor {
                size_in_pixels: [g.config.width, g.config.height],
                pixels_per_point: ppp,
            };
            let mut enc = g.device.create_command_encoder(&wgpu::CommandEncoderDescriptor { label: Some("frame") });
            let extra = g.renderer.update_buffers(&g.device, &g.queue, &mut enc, &jobs, &screen);
            {
                let c = theme::CANVAS;
                let pass = enc.begin_render_pass(&wgpu::RenderPassDescriptor {
                    label: Some("egui"),
                    color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                        view: &view,
                        depth_slice: None,
                        resolve_target: None,
                        ops: wgpu::Operations {
                            load: wgpu::LoadOp::Clear(wgpu::Color {
                                r: c.r() as f64 / 255.0,
                                g: c.g() as f64 / 255.0,
                                b: c.b() as f64 / 255.0,
                                a: 1.0,
                            }),
                            store: wgpu::StoreOp::Store,
                        },
                    })],
                    ..Default::default()
                });
                g.renderer.render(&mut pass.forget_lifetime(), &jobs, &screen);
            }
            let first=self.m.native_toggle_enabled.then(||self.m.native_toggle.display()).flatten();
            let second=self.m.native_action_enabled.then(||self.m.native_action.display()).flatten();
            let third=self.m.native_reset_enabled.then(||self.m.native_reset.display()).flatten();
            let stress_layer=if first.is_some() && second.is_some() && third.is_some() {
                match g.private_capture_kind {
                    Some("01d")=>Some(crate::ac01d_stress::fixture()),
                    Some("01e")=>Some(crate::ac01e_stroke_stress::fixture()),
                    Some("01f")=>Some(crate::ac01f_bezier_stress::fixture()),
                    Some("01g")=>Some(crate::ac01g_closed_path_stress::fixture()),
                    Some("01h")=>Some(crate::ac01h_complex_paths::fixture()),
                    Some("01i")=>Some(crate::ac01i_even_odd::fixture()),
                    _=>None
                }
            } else {None};
            let viewport_clip=UiRect::new(
                0.,0.,g.config.width as f32/ppp,g.config.height as f32/ppp);
            // Two independent ancestors, explicitly inner→outer.
            // Real G03 widget clips were already computed by the producer;
            // the compositor cannot expand a previously clipped command.
            let ancestors=[
                LayerStep::IDENTITY,
                LayerStep{transform:blobin_ui_scene::UiTransform2D::IDENTITY,
                    parent_clip:Some(viewport_clip)}
            ];
            let mut layers=Vec::with_capacity(4);
            if let Some(list)=first{layers.push(SceneLayer{list,ancestors:&ancestors});}
            if let Some(list)=second{layers.push(SceneLayer{list,ancestors:&ancestors});}
            if let Some(list)=third{layers.push(SceneLayer{list,ancestors:&ancestors});}
            if let Some(list)=stress_layer.as_ref(){
                layers.push(SceneLayer{list,ancestors:&ancestors});
            }
            if !layers.is_empty() {
                let composed=compose(&layers,MAX_NATIVE_UI_COMMANDS);
                if let Ok(ref composed)=composed {
                let refs=composed.as_refs();
                match g.native_overlay.encode_with_triangle_aa(&g.queue,&mut enc,&view,&refs,
                    (g.config.width as f32/ppp,g.config.height as f32/ppp),
                    ppp,(g.config.width,g.config.height),
                    g.private_capture_kind==Some("01i")) {
                    Ok(receipt)=>{
                        if g.private_capture_kind==Some("01i") {
                            self.trace.emit("ui01i_scene_submit",json!({
                                "composed_layers":composed.lists.len(),
                                "triangles":composed.lists.iter().map(|l|l.triangles.len()).sum::<usize>(),
                                "commands":composed.command_count,
                                "gpu_commands":receipt.commands,
                                "antialias_external_edges_only":true,
                                "compositor_present_feedback":false
                            }));
                        }
                        if g.private_capture_kind==Some("01h") {
                            self.trace.emit("ui01h_scene_submit",json!({
                                "input_layers":composed.input_layers,
                                "composed_layers":composed.lists.len(),
                                "rectangles":composed.lists.iter().map(|l|l.commands.len()).sum::<usize>(),
                                "triangles":composed.lists.iter().map(|l|l.triangles.len()).sum::<usize>(),
                                "strokes":composed.lists.iter().map(|l|l.strokes.len()).sum::<usize>(),
                                "total_commands":composed.command_count,
                                "adapter_draw_commands":receipt.commands,
                                "persistent_allocations":g.native_overlay.resident_allocations,
                                "compositor_present_feedback":false
                            }));
                        }
                        if g.private_capture_kind==Some("01g") {
                            self.trace.emit("ui01g_scene_submit",json!({
                                "input_layers":composed.input_layers,
                                "composed_layers":composed.lists.len(),
                                "filled_rectangles":composed.lists.iter()
                                    .map(|l|l.commands.len()).sum::<usize>(),
                                "triangle_fills":composed.lists.iter()
                                    .map(|l|l.triangles.len()).sum::<usize>(),
                                "vector_strokes":composed.lists.iter()
                                    .map(|l|l.strokes.len()).sum::<usize>(),
                                "total_commands":composed.command_count,
                                "adapter_draw_commands":receipt.commands,
                                "persistent_allocations":g.native_overlay.resident_allocations,
                                "compositor_present_feedback":false
                            }));
                        }
                        if g.private_capture_kind==Some("01f") {
                            self.trace.emit("ui01f_scene_submit",json!({
                                "input_layers":composed.input_layers,
                                "composed_layers":composed.lists.len(),
                                "filled_rectangles":composed.lists.iter()
                                    .map(|l|l.commands.len()).sum::<usize>(),
                                "bezier_flattened_segments":composed.lists.iter()
                                    .map(|l|l.strokes.len()).sum::<usize>(),
                                "total_commands":composed.command_count,
                                "adapter_draw_commands":receipt.commands,
                                "tolerance_logical_px":crate::ac01f_bezier_stress::TOLERANCE_LOGICAL_PX,
                                "uniform_uploads_total":g.native_overlay.uploads,
                                "persistent_allocations":g.native_overlay.resident_allocations,
                                "compositor_present_feedback":false
                            }));
                        }
                        if g.private_capture_kind==Some("01e") {
                            self.trace.emit("ui01e_scene_submit",json!({
                                "input_layers":composed.input_layers,
                                "composed_layers":composed.lists.len(),
                                "filled_rectangles":composed.lists.iter()
                                    .map(|l|l.commands.len()).sum::<usize>(),
                                "vector_segments":composed.lists.iter()
                                    .map(|l|l.strokes.len()).sum::<usize>(),
                                "total_commands":composed.command_count,
                                "adapter_draw_commands":receipt.commands,
                                "uniform_uploads_total":g.native_overlay.uploads,
                                "persistent_allocations":g.native_overlay.resident_allocations,
                                "compositor_present_feedback":false
                            }));
                        }
                        self.trace.emit("ui01d_scene_submit",json!({
                            "composed_layers":composed.lists.len(),
                            "input_layers":composed.input_layers,
                            "clipped_layers":composed.clipped_layers,
                            "commands":composed.command_count,
                            "adapter_draw_commands":receipt.commands,
                            "persistent_allocations":g.native_overlay.resident_allocations,
                            "stress_fixture":g.private_capture_kind==Some("01d"),
                            "compositor_present_feedback":false
                        }));
                        if let Some(list)=first {
                            self.trace.emit("ui01a_native_submit",json!({
                                "commands":list.commands.len(),"node":list.source_node.slot,
                                "surface":list.surface.0,
                                "ui_revision":list.source_ui_revision,"layout_epoch":list.layout_epoch,
                                "overlay_state":self.m.overlay,
                                "bounds":list.commands.first().map(|c|[
                                    c.rect.x,c.rect.y,c.rect.width,c.rect.height]),
                                "clip":list.commands.first().map(|c|[
                                    c.clip.x,c.clip.y,c.clip.width,c.clip.height]),
                                "renderer":"blobin-ui-scene/wgpu native overlay",
                                "sdf_frame_unchanged":true,
                                "compositor_present_feedback":false
                            }));
                        }
                        if let Some(list)=second {
                            self.trace.emit("ui01b_native_submit",json!({
                                "commands":list.commands.len(),"node":list.source_node.slot,
                                "surface":list.surface.0,
                                "ui_revision":list.source_ui_revision,"layout_epoch":list.layout_epoch,
                                "selected":self.m.view==ViewMode::Distance,
                                "bounds":list.commands.first().map(|c|[
                                    c.rect.x,c.rect.y,c.rect.width,c.rect.height]),
                                "clip":list.commands.first().map(|c|[
                                    c.clip.x,c.clip.y,c.clip.width,c.clip.height]),
                                "uniform_write":receipt.uniform_write,
                                "uniform_uploads_total":g.native_overlay.uploads,
                                "resident_resource_allocations":g.native_overlay.resident_allocations,
                                "batched_nodes":receipt.nodes,
                                "batched_commands":receipt.commands,
                                "compositor_present_feedback":false
                            }));
                        }
                        if let Some(list)=third {
                            self.trace.emit("ui01c_native_submit",json!({
                                "commands":list.commands.len(),"surface":list.surface.0,
                                "ui_revision":list.source_ui_revision,"layout_epoch":list.layout_epoch,
                                "camera_default":self.m.camera==Camera::default(),
                                "bounds":list.commands.first().map(|c|[
                                    c.rect.x,c.rect.y,c.rect.width,c.rect.height]),
                                "nodes":receipt.nodes,"commands_batch":receipt.commands,
                                "uniform_uploads_total":g.native_overlay.uploads,
                                "present_feedback":false
                            }));
                        }
                    }
                    Err(reason)=>{
                        self.m.native_toggle_enabled=false;
                        self.m.native_action_enabled=false;
                        self.m.native_reset_enabled=false;
                        self.m.log(Level::Error,format!("01B native GPU: {reason}; retour egui activé"));
                        g.window.request_redraw();
                    }
                }
                } else {
                    self.m.native_toggle_enabled=false;
                    self.m.native_action_enabled=false;
                    self.m.native_reset_enabled=false;
                    self.m.log(Level::Error,format!("01D composed scene rejected: {:?}",
                        composed.err()));
                    g.window.request_redraw();
                }
            }
            let stable_frame=self.m.presented.as_ref().is_some_and(
                |p| p.meta.scene_revision==self.m.sched.revision()
            ) && self.m.pending.is_none() && g.frame_tex.is_some();
            let capture_state=if g.private_capture_dir.is_some() && stable_frame {
                match g.private_capture_kind {
                    Some("01a") if self.m.native_toggle_enabled
                        && self.m.native_toggle.display().is_some()=>{
                        if self.m.overlay && self.captured_toggle_states&1==0 {
                            Some((1,"toggle-on"))
                        } else if !self.m.overlay && self.captured_toggle_states&2==0 {
                            Some((2,"toggle-off"))
                        } else {None}
                    },
                    Some("01b") if self.m.native_action_enabled
                        && self.m.native_action.display().is_some()=>{
                        if self.m.view!=ViewMode::Distance && self.captured_toggle_states&4==0 {
                            Some((4,"action-idle"))
                        } else if self.m.view==ViewMode::Distance
                            && self.captured_toggle_states&8==0 {
                            Some((8,"action-selected"))
                        } else if !self.m.overlay && self.captured_toggle_states&2==0
                            && self.captured_toggle_states&8!=0 {
                            Some((2,"toggle-off"))
                        } else {None}
                    },
                    Some("01i") if self.m.native_reset_enabled &&
                        self.m.native_reset.display().is_some() &&
                        self.captured_toggle_states&2048==0=>{
                        Some((2048,"two-holes-aa"))
                    },
                    Some("01h") if self.m.native_reset_enabled &&
                        self.m.native_reset.display().is_some() &&
                        self.captured_toggle_states&1024==0=>{
                        Some((1024,"concave-hole"))
                    },
                    Some("01g") if self.m.native_reset_enabled &&
                        self.m.native_reset.display().is_some() &&
                        self.captured_toggle_states&512==0=>{
                        Some((512,"convex-closed-paths"))
                    },
                    Some("01f") if self.m.native_reset_enabled &&
                        self.m.native_reset.display().is_some() &&
                        self.captured_toggle_states&256==0=>{
                        Some((256,"bezier-curves"))
                    },
                    Some("01e") if self.m.native_reset_enabled &&
                        self.m.native_reset.display().is_some() &&
                        self.captured_toggle_states&128==0=>{
                        Some((128,"vector-strokes"))
                    },
                    Some("01d") if self.m.native_reset_enabled &&
                        self.m.native_reset.display().is_some() &&
                        self.captured_toggle_states&64==0=>{
                        Some((64,"composition-stress"))
                    },
                    Some("01c") if self.m.native_reset_enabled &&
                        self.m.native_reset.display().is_some()=>{
                        if self.m.camera!=Camera::default() &&
                            self.captured_toggle_states&16==0 {
                            Some((16,"reset-before"))
                        } else if self.m.camera==Camera::default() &&
                            self.captured_toggle_states&32==0 {
                            Some((32,"reset-after"))
                        } else {None}
                    },
                    _=>None
                }
            } else {None};
            let copy = capture_state.and_then(|(bit,name)| {
                let w=g.config.width;
                let h=g.config.height;
                if w>2048 || h>2048 || w==0 || h==0 {return None}
                let pitch=(w*4).div_ceil(256)*256;
                let buffer=g.device.create_buffer(&wgpu::BufferDescriptor{
                    label:Some("01A private GPU source-pixel readback"),
                    size:u64::from(pitch)*u64::from(h),
                    usage:wgpu::BufferUsages::COPY_DST|wgpu::BufferUsages::MAP_READ,
                    mapped_at_creation:false,
                });
                enc.copy_texture_to_buffer(
                    wgpu::TexelCopyTextureInfo {
                        texture:&frame.texture,mip_level:0,origin:wgpu::Origin3d::ZERO,
                        aspect:wgpu::TextureAspect::All
                    },
                    wgpu::TexelCopyBufferInfo {
                        buffer:&buffer,
                        layout:wgpu::TexelCopyBufferLayout {
                            offset:0,bytes_per_row:Some(pitch),rows_per_image:Some(h)
                        }
                    },
                    wgpu::Extent3d{width:w,height:h,depth_or_array_layers:1});
                Some((bit,name,buffer,pitch,w,h))
            });
            g.queue.submit(extra.into_iter().chain([enc.finish()]));
            g.window.pre_present_notify();
            g.queue.present(frame);
            if let Some((bit,name,buffer,pitch,w,h))=copy {
                let mut error:Option<String>=None;
                let (sender,receiver)=std::sync::mpsc::channel();
                buffer.slice(..).map_async(wgpu::MapMode::Read,move |result|{
                    let _=sender.send(result);
                });
                if g.device.poll(wgpu::PollType::Wait{
                    submission_index:None,timeout:Some(Duration::from_secs(5))
                }).is_err() {
                    error=Some("device poll timeout".into());
                } else if !matches!(receiver.recv_timeout(Duration::from_secs(2)),Ok(Ok(()))) {
                    error=Some("GPU pixel mapping failed".into());
                } else {
                    match buffer.slice(..).get_mapped_range() {
                        Ok(range)=>{
                            let mut contiguous=Vec::with_capacity(w as usize*h as usize*4);
                            for row in range.chunks_exact(pitch as usize) {
                                contiguous.extend_from_slice(&row[..w as usize*4]);
                            }
                            drop(range);
                            buffer.unmap();
                            if let Some(dir)=&g.private_capture_dir {
                                match std::fs::write(dir.join(format!("{name}.raw")),&contiguous){
                                    Ok(())=>{
                                        self.captured_toggle_states|=bit;
                                        if name.starts_with("toggle-") {
                                            self.trace.emit("ui01a_gpu_pixels",json!({
                                                "toggle":name.trim_start_matches("toggle-"),
                                                "width":w,"height":h,
                                                "format":format!("{:?}",g.config.format),
                                                "bytes":contiguous.len(),
                                                "sdf_scene_revision":self.m.sched.revision(),
                                                "compositor_present_feedback":false
                                            }));
                                        } else if name.starts_with("two-holes-") {
                                            self.trace.emit("ui01i_gpu_pixels",json!({
                                                "state":name,"width":w,"height":h,
                                                "format":format!("{:?}",g.config.format),
                                                "bytes":contiguous.len(),
                                                "compositor_present_feedback":false
                                            }));
                                        } else if name.starts_with("concave-") {
                                            self.trace.emit("ui01h_gpu_pixels",json!({
                                                "state":name,"width":w,"height":h,
                                                "format":format!("{:?}",g.config.format),
                                                "bytes":contiguous.len(),
                                                "compositor_present_feedback":false
                                            }));
                                        } else if name.starts_with("convex-") {
                                            self.trace.emit("ui01g_gpu_pixels",json!({
                                                "state":name,"width":w,"height":h,
                                                "format":format!("{:?}",g.config.format),
                                                "bytes":contiguous.len(),
                                                "compositor_present_feedback":false
                                            }));
                                        } else if name.starts_with("bezier-") {
                                            self.trace.emit("ui01f_gpu_pixels",json!({
                                                "state":name,"width":w,"height":h,
                                                "format":format!("{:?}",g.config.format),
                                                "bytes":contiguous.len(),
                                                "compositor_present_feedback":false
                                            }));
                                        } else if name.starts_with("vector-") {
                                            self.trace.emit("ui01e_gpu_pixels",json!({
                                                "state":name,"width":w,"height":h,
                                                "format":format!("{:?}",g.config.format),
                                                "bytes":contiguous.len(),
                                                "compositor_present_feedback":false
                                            }));
                                        } else if name.starts_with("composition-") {
                                            self.trace.emit("ui01d_gpu_pixels",json!({
                                                "state":name,"width":w,"height":h,
                                                "format":format!("{:?}",g.config.format),
                                                "bytes":contiguous.len(),
                                                "compositor_present_feedback":false
                                            }));
                                        } else if name.starts_with("reset-") {
                                            self.trace.emit("ui01c_gpu_pixels",json!({
                                                "state":name,"width":w,"height":h,
                                                "format":format!("{:?}",g.config.format),
                                                "bytes":contiguous.len(),
                                                "scene_revision":self.m.sched.revision(),
                                                "camera_default":self.m.camera==Camera::default(),
                                                "compositor_present_feedback":false
                                            }));
                                        } else {
                                            self.trace.emit("ui01b_gpu_pixels",json!({
                                                "selection":name.trim_start_matches("action-"),
                                                "width":w,"height":h,
                                                "format":format!("{:?}",g.config.format),
                                                "bytes":contiguous.len(),
                                                "sdf_scene_revision":self.m.sched.revision(),
                                                "compositor_present_feedback":false
                                            }));
                                        }
                                    },
                                    Err(e)=>error=Some(e.to_string()),
                                }
                            }
                        },
                        Err(e)=>error=Some(format!("01A map read: {e:?}"))
                    }
                }
                if let Some(error)=error {
                    self.trace.emit("ui01a_capture_error",json!({"reason":error}));
                }
            }
        }
        for id in &out.textures_delta.free {
            g.renderer.free_texture(id);
        }
        // egui 0.36's TexturesDelta drop asserts all deltas were explicitly
        // consumed. These were uploaded/freed by egui_wgpu above.
        out.textures_delta.clear();

        let delay = out.viewport_output.get(&egui::ViewportId::ROOT).map(|v| v.repaint_delay).unwrap_or(Duration::MAX);
        self.repaint_at = if delay.is_zero() {
            g.window.request_redraw();
            None
        } else {
            Instant::now().checked_add(delay)
        };
        if self.m.quit {
            return;
        }
        self.after_ui();
    }

    /// Reacts to what the UI pass changed (viewport size) and issues a request if due.
    fn after_ui(&mut self) {
        if let Some(vp) = self.m.viewport {
            if self.last_physical != Some(vp.physical) {
                self.trace.emit("viewport", json!({"physical": [vp.physical.0, vp.physical.1]}));
                self.last_physical = Some(vp.physical);
                self.m.sched.invalidate();
            }
        }
        self.pump();
    }

    fn pump(&mut self) {
        let (Some(client), Some(vp)) = (self.client.as_ref(), self.m.viewport) else { return };
        let Conn::Connected(session) = &self.m.conn else { return };
        let f = fit(vp.physical, &session.capabilities);
        self.m.fit = Some(f);
        let Fit::Render { w, h, scale } = f else { return };
        if !self.m.sched.dirty() || self.m.sched.in_flight().is_some() {
            return;
        }
        if !session.capabilities.backend_offered(self.m.backend) {
            return;
        }
        let prims = match self.m.scene.to_wire(&self.m.camera) {
            Ok(p) => {
                self.m.bounds_error = None;
                p
            }
            Err(e) => {
                self.m.bounds_error = Some(e);
                return;
            }
        };
        let Some(slot) = self.m.sched.issue(Instant::now()) else { return };
        let req = RenderRequest::new(slot.request_id, slot.revision, (w, h), self.m.backend, self.m.view, prims);
        self.trace.emit(
            "request",
            json!({"request_id": slot.request_id, "revision": slot.revision, "size": [w, h],
                   "viewport_physical": [vp.physical.0, vp.physical.1], "scale": scale,
                   "backend": self.m.backend.as_str(), "view_mode": self.m.view.as_str(),
                   "primitives": req.primitives.len()}),
        );
        self.m.pending = Some(Pending { request_id: slot.request_id, camera: self.m.camera, scale, backend: self.m.backend, size: (w, h) });
        client.render(req);
    }

    fn on_client(&mut self, e: ClientEvent) {
        match e {
            ClientEvent::Connecting { attempt } => {
                if !matches!(self.m.conn, Conn::Failed { .. }) {
                    self.m.conn = Conn::Connecting { attempt };
                }
            }
            ClientEvent::ConnectFailed { reason, retry_in } => {
                let repeated = matches!(&self.m.conn, Conn::Failed { reason: r, .. } if *r == reason);
                if !repeated {
                    self.m.log(Level::Warn, format!("runtime injoignable : {reason}"));
                    self.trace.emit("connect_failed", json!({"reason": reason}));
                }
                self.m.conn = Conn::Failed { reason, retry_in };
            }
            ClientEvent::Connected(s) => {
                self.m.log(Level::Info, format!("connecté à « {} » (BLOB-FRAME-v1)", s.server));
                self.trace.emit(
                    "connected",
                    json!({"session": s.id, "server": s.server,
                           "capabilities": serde_json::to_value(&s.capabilities).unwrap_or_default()}),
                );
                if !s.capabilities.backend_offered(self.m.backend) {
                    self.m.log(Level::Warn, format!("backend {} non proposé par ce runtime", self.m.backend.as_str()));
                }
                self.m.conn = Conn::Connected(s);
                self.m.sched.reset_session();
                self.m.pending = None;
                if let Some(c) = &self.client {
                    c.ping();
                }
            }
            ClientEvent::Disconnected { session_id, reason } => {
                self.m.log(Level::Warn, format!("session {session_id} terminée : {reason}"));
                self.trace.emit("disconnected", json!({"session": session_id, "reason": reason}));
                self.m.conn = Conn::Connecting { attempt: 0 };
                self.m.sched.reset_session();
                self.m.pending = None;
            }
            ClientEvent::Frame(f) => self.on_frame(f),
            ClientEvent::FrameRejected { request_id, reason } => {
                self.m.rejected += 1;
                self.settle_failed(request_id);
                self.m.log(Level::Error, format!("frame {request_id} rejetée : {reason}"));
                self.trace.emit("frame_rejected", json!({"request_id": request_id, "reason": reason}));
            }
            ClientEvent::RequestFailed { request_id, reason } => {
                self.settle_failed(request_id);
                self.m.log(Level::Warn, format!("requête {request_id} non aboutie : {reason}"));
                self.trace.emit("request_failed", json!({"request_id": request_id, "reason": reason}));
            }
            ClientEvent::RenderError { request_id, error } => {
                self.m.errors += 1;
                let backend = self.m.pending.as_ref().map(|p| p.backend.as_str()).unwrap_or("?");
                if let Some(id) = request_id {
                    self.settle_failed(id);
                }
                self.m.log(Level::Error, format!("RENDER_ERROR {} (backend {backend}) — aucune substitution", error.reason));
                self.trace.emit("render_error", json!({"request_id": request_id, "reason": error.reason, "backend": backend}));
            }
            ClientEvent::Pong { rtt } => self.m.ping_rtt = Some(rtt),
        }
    }

    fn settle_failed(&mut self, request_id: u64) {
        if self.m.sched.on_failed(request_id) {
            self.m.pending = None;
        }
    }

    fn on_frame(&mut self, f: Box<ReceivedFrame>) {
        let id = f.meta.request_id;
        let pending = self.m.pending.take_if(|p| p.request_id == id);
        let verdict = self.m.sched.on_frame(id, f.meta.scene_revision);
        let (Verdict::Present, Some(p), Some(g)) = (verdict, pending, self.gfx.as_mut()) else {
            self.trace.emit("frame_dropped", json!({"request_id": id, "revision": f.meta.scene_revision, "verdict": format!("{verdict:?}")}));
            return;
        };
        debug_assert_eq!(p.size, (f.meta.width_px, f.meta.height_px));
        // Optional bounded original BLOB-FRAME pixel witness. Only the local
        // AC05 private test sets this env var; output is a raw runtime frame,
        // NOT egui overlay/swapchain pixels or compositor presentation proof.
        if let Some(dir) = std::env::var_os("BLOB_AC05_FRAME_EVIDENCE_DIR") {
            let path = std::path::PathBuf::from(dir);
            if path.is_dir() && self.m.sched.counters.presented <= 2 {
                let name = format!("runtime-revision-{}.rgba", f.meta.scene_revision);
                if let Err(e) = std::fs::write(path.join(name), f.pixels.bytes()) {
                    self.trace.emit("ac05_capture_error",json!({"reason":e.to_string()}));
                }
            }
        }
        upload(g, &f);
        g.window.request_redraw();
        self.trace.emit(
            "presented",
            json!({"request_id": id, "revision": f.meta.scene_revision,
                   "size": [f.meta.width_px, f.meta.height_px],
                   "viewport_physical": self.m.viewport.map(|v| [v.physical.0, v.physical.1]),
                   "backend_actual": f.meta.backend_actual.as_str(), "view_mode": f.meta.view_mode.as_str(),
                   "qualification": f.meta.qualification, "generation": f.meta.generation,
                   "frame_sequence": f.meta.frame_sequence, "geometry_sha256": f.meta.geometry_sha256,
                   "round_trip_ms": f.round_trip.as_secs_f64() * 1e3}),
        );
        self.m.presented =
            Some(Presented { meta: f.meta.clone(), camera: p.camera, scale: p.scale, round_trip: f.round_trip, at: Instant::now() });
        // `f` (and with it the read-only mapping) is dropped here.
        if self.exercise.is_some() {
            self.exercise_due = Some(Instant::now() + EXERCISE_DWELL);
        }
    }

    fn next_exercise_step(&mut self) {
        let Some(i) = self.exercise else { return };
        let Some(&step) = EXERCISE.get(i) else {
            self.trace.emit("exercise_done", json!({"steps": EXERCISE.len()}));
            self.exercise = None;
            self.m.quit = true;
            return;
        };
        self.exercise = Some(i + 1);
        let m = &mut self.m;
        let applied = match step {
            Step::MoveCircle { index, dx, dy } => m.scene.circles.get_mut(index).map(|c| {
                c.x += dx;
                c.y += dy;
            }).is_some(),
            Step::ScaleRadius { index, factor } => {
                let c = m.scene.circles.get(index).copied();
                c.is_some_and(|c| m.scene.set_radius(c.id, c.radius * factor))
            }
            Step::CycleOp { index } => {
                let id = m.scene.circles.get(index).map(|c| c.id);
                id.is_some_and(|id| m.scene.cycle_op(id))
            }
            Step::View(v) => {
                m.view = v;
                true
            }
            Step::Backend(b) => {
                let ok = m.session().is_some_and(|s| s.capabilities.backend_offered(b));
                if ok {
                    m.backend = b;
                }
                ok
            }
            Step::Lab(l) => {
                m.set_lab(l);
                true
            }
            Step::Zoom(z) => {
                m.camera.zoom = (m.camera.zoom * z).clamp(MIN_ZOOM, MAX_ZOOM);
                true
            }
            Step::ResetCamera => {
                m.camera = Camera::default();
                true
            }
        };
        let m = &mut self.m;
        m.sched.invalidate();
        let wire = m.scene.to_wire(&m.camera).ok();
        self.trace.emit(
            "exercise_step",
            json!({"index": i, "step": format!("{step:?}"), "applied": applied,
                   "revision": self.m.sched.revision(), "backend": self.m.backend.as_str(),
                   "view_mode": self.m.view.as_str(),
                   "primitives": wire.map(|w| serde_json::to_value(w).unwrap_or_default())}),
        );
    }
}

/// Copies a received frame into the presentation texture (one GPU copy; the
/// contract hands over a memfd, not a DMA-BUF).
fn upload(g: &mut Gfx, f: &ReceivedFrame) {
    let (w, h) = (f.meta.width_px, f.meta.height_px);
    if g.frame_tex.as_ref().map(|t| t.size) != Some((w, h)) {
        let texture = g.device.create_texture(&wgpu::TextureDescriptor {
            label: Some("blob-frame"),
            size: wgpu::Extent3d { width: w, height: h, depth_or_array_layers: 1 },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            // Bytes are display-encoded values (as in the runtime's PNG output).
            format: wgpu::TextureFormat::Rgba8UnormSrgb,
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
            view_formats: &[],
        });
        let view = texture.create_view(&wgpu::TextureViewDescriptor::default());
        match g.frame_tex.as_mut() {
            Some(t) => {
                g.renderer.update_egui_texture_from_wgpu_texture(&g.device, &view, wgpu::FilterMode::Linear, t.id);
                t.texture = texture;
                t.size = (w, h);
            }
            None => {
                let id = g.renderer.register_native_texture(&g.device, &view, wgpu::FilterMode::Linear);
                g.frame_tex = Some(FrameTexture { texture, id, size: (w, h) });
            }
        }
    }
    let t = g.frame_tex.as_ref().expect("texture exists");
    g.queue.write_texture(
        wgpu::TexelCopyTextureInfo {
            texture: &t.texture,
            mip_level: 0,
            origin: wgpu::Origin3d::ZERO,
            aspect: wgpu::TextureAspect::All,
        },
        f.pixels.bytes(),
        wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(f.meta.stride_bytes), rows_per_image: Some(h) },
        wgpu::Extent3d { width: w, height: h, depth_or_array_layers: 1 },
    );
}

impl ApplicationHandler<UserEvent> for App {
    fn resumed(&mut self, el: &ActiveEventLoop) {
        if self.gfx.is_some() {
            return;
        }
        if let Err(e) = self.init(el) {
            log::error!("{e}");
            self.exit = Err(e);
            el.exit();
        }
    }

    fn new_events(&mut self, _el: &ActiveEventLoop, cause: StartCause) {
        if let StartCause::ResumeTimeReached { .. } = cause {
            if self.exercise_due.is_some_and(|t| t <= Instant::now()) {
                self.exercise_due = None;
                self.next_exercise_step();
                self.pump();
            }
            if let Some(g) = &self.gfx {
                g.window.request_redraw();
            }
        }
    }

    fn window_event(&mut self, el: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        let Some(g) = self.gfx.as_mut() else { return };
        let resp = g.egui.on_window_event(&g.window, &event);
        match &event {
            WindowEvent::CursorMoved { position, .. } =>
                self.trace.emit("ac05_winit_pointer",json!({"kind":"move","x":position.x,"y":position.y})),
            WindowEvent::MouseInput { state, button, .. } =>
                self.trace.emit("ac05_winit_pointer",json!({"kind":"button","state":format!("{state:?}"),"button":format!("{button:?}")})),
            _ => {}
        }
        match event {
            WindowEvent::CloseRequested => {
                self.shutdown(el);
                return;
            }
            WindowEvent::Resized(size) => {
                self.m.gestures.cancel();
                if size.width > 0 && size.height > 0 {
                    g.config.width = size.width;
                    g.config.height = size.height;
                    g.surface.configure(&g.device, &g.config);
                }
                self.trace.emit("resized", json!({"inner_physical": [size.width, size.height]}));
                g.window.request_redraw();
            }
            WindowEvent::Focused(false) => {
                self.m.gestures.cancel();
            }
            WindowEvent::RedrawRequested => {
                self.redraw();
                if self.m.quit {
                    self.shutdown(el);
                }
                return;
            }
            _ => {}
        }
        if resp.repaint {
            g.window.request_redraw();
        }
    }

    fn user_event(&mut self, _el: &ActiveEventLoop, e: UserEvent) {
        match e {
            UserEvent::Client(e) => self.on_client(e),
        }
        self.pump();
        if let Some(g) = &self.gfx {
            g.window.request_redraw();
        }
    }

    fn about_to_wait(&mut self, el: &ActiveEventLoop) {
        let wake = match (self.repaint_at, self.exercise_due) {
            (Some(a), Some(b)) => Some(a.min(b)),
            (a, b) => a.or(b),
        };
        el.set_control_flow(match wake {
            Some(t) => ControlFlow::WaitUntil(t),
            None => ControlFlow::Wait,
        });
    }
}

// ---------------------------------------------------------------- UI ----

fn op_glyph(op: CsgOp) -> &'static str {
    let math = theme::MATH_GLYPHS.load(std::sync::atomic::Ordering::Relaxed);
    match (op, math) {
        (CsgOp::Union, true) => "∪",
        (CsgOp::Subtract, true) => "−",
        (CsgOp::Intersect, true) => "∩",
        (CsgOp::SmoothUnion, true) => "∪~",
        (CsgOp::Union, false) => "U",
        (CsgOp::Subtract, false) => "-",
        (CsgOp::Intersect, false) => "n",
        (CsgOp::SmoothUnion, false) => "U~",
    }
}

fn op_label(op: CsgOp) -> &'static str {
    match op {
        CsgOp::Union => "union",
        CsgOp::Subtract => "soustraction",
        CsgOp::Intersect => "intersection",
        CsgOp::SmoothUnion => "union lisse",
    }
}

fn view_label(v: ViewMode) -> &'static str {
    match v {
        ViewMode::Distance => "Distance",
        ViewMode::Normals => "Normales",
        ViewMode::Coverage => "Couverture",
        ViewMode::Lit => "Éclairé",
    }
}

fn section(ui: &mut egui::Ui, title: &str) {
    ui.add_space(6.0);
    ui.label(egui::RichText::new(title).small().strong().color(theme::TEXT_MUTED));
}

const PANEL_WIDTH: f32 = 348.0;

fn ui_root(ui: &mut egui::Ui, m: &mut Model, tex: Option<egui::TextureId>, adapter: &str, socket: &std::path::Path) {
    shortcuts(ui.ctx(), m);
    // Explicit split: viewport on the left, fixed control column on the right.
    let full = ui.max_rect();
    let split = full.max.x - PANEL_WIDTH.min(full.width() * 0.6);
    let vp_rect = egui::Rect::from_min_max(full.min, Pos2::new(split, full.max.y));
    let panel_rect = egui::Rect::from_min_max(Pos2::new(split, full.min.y), full.max);
    let mut vp = ui.new_child(egui::UiBuilder::new().max_rect(vp_rect));
    vp.set_clip_rect(vp_rect);
    viewport(&mut vp, m, tex);
    let mut panel = ui.new_child(egui::UiBuilder::new().max_rect(panel_rect));
    panel.set_clip_rect(panel_rect);
    panel.painter().rect_filled(panel_rect, 0.0, theme::PANEL);
    panel.painter().vline(split, full.y_range(), Stroke::new(1.0, theme::BORDER));
    egui::Frame::new().inner_margin(egui::Margin::same(14)).show(&mut panel, |ui| {
        egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| controls(ui, m, adapter, socket));
    });
    if m.help {
        help_window(ui.ctx(), m);
    }
}

fn shortcuts(ctx: &egui::Context, m: &mut Model) {
    if ctx.egui_wants_keyboard_input() {
        return;
    }
    use egui::Key;
    ctx.input(|i| {
        let keys = [Key::Num1, Key::Num2, Key::Num3, Key::Num4, Key::Num5, Key::Num6];
        for (k, lab) in keys.into_iter().zip(Lab::ALL) {
            if i.key_pressed(k) {
                m.set_lab(lab);
            }
        }
        if i.modifiers.ctrl && i.key_pressed(Key::Q) {
            m.quit = true;
        }
        if i.modifiers.command && i.key_pressed(Key::Z) && !i.modifiers.shift && m.gestures.undo_move(&mut m.scene) {
            m.sched.invalidate();
        }
        if i.key_pressed(Key::B) {
            let offered: Vec<Backend> = Backend::ALL
                .into_iter()
                .filter(|b| m.session().is_none_or(|s| s.capabilities.backend_offered(*b)))
                .collect();
            if let Some(k) = offered.iter().position(|b| *b == m.backend) {
                m.backend = offered[(k + 1) % offered.len()];
                m.sched.invalidate();
            }
        }
        if i.key_pressed(Key::V) {
            let k = ViewMode::ALL.iter().position(|v| *v == m.view).unwrap_or(0);
            m.view = ViewMode::ALL[(k + 1) % ViewMode::ALL.len()];
            m.sched.invalidate();
        }
        if i.key_pressed(Key::O) {
            if let Some(id) = m.scene.selected {
                if m.scene.cycle_op(id) {
                    m.sched.invalidate();
                }
            }
        }
        if i.key_pressed(Key::Tab) && !m.scene.circles.is_empty() {
            let k = m.scene.selected.and_then(|id| m.scene.index_of(id)).map(|k| k + 1).unwrap_or(0);
            m.scene.selected = Some(m.scene.circles[k % m.scene.circles.len()].id);
        }
        if i.key_pressed(Key::Delete) {
            if let Some(id) = m.scene.selected {
                if m.scene.remove(id) {
                    m.sched.invalidate();
                }
            }
        }
        if i.key_pressed(Key::Escape) {
            m.gestures.cancel();
            m.scene.selected = None;
            m.help = false;
        }
        if i.key_pressed(Key::R) {
            m.camera = Camera::default();
            m.sched.invalidate();
        }
        if i.key_pressed(Key::G) {
            m.overlay = !m.overlay;
        }
        if i.key_pressed(Key::F1) || i.key_pressed(Key::H) {
            m.help = !m.help;
        }
        if let Some(id) = m.scene.selected {
            let step = if i.modifiers.shift { 0.05 } else { 0.01 };
            let d = [(Key::ArrowLeft, (-step, 0.0)), (Key::ArrowRight, (step, 0.0)), (Key::ArrowUp, (0.0, -step)), (Key::ArrowDown, (0.0, step))];
            for (k, (dx, dy)) in d {
                if i.key_pressed(k) {
                    if let Some(c) = m.scene.get_mut(id) {
                        c.x += dx;
                        c.y += dy;
                        m.sched.invalidate();
                    }
                }
            }
            for (k, f) in [(Key::Plus, 1.1), (Key::Equals, 1.1), (Key::Minus, 1.0 / 1.1)] {
                if i.key_pressed(k) {
                    let r = m.scene.get(id).map(|c| c.radius * f).unwrap_or(0.1);
                    if m.scene.set_radius(id, r) {
                        m.sched.invalidate();
                    }
                }
            }
        }
    });
}

fn controls(ui: &mut egui::Ui, m: &mut Model, adapter: &str, socket: &std::path::Path) {
    ui.horizontal(|ui| {
        ui.heading(egui::RichText::new("blob.in").strong().color(theme::TEXT_STRONG));
        ui.label(egui::RichText::new("surface native").color(theme::TEXT_MUTED));
    });
    source_badge(ui, m);

    section(ui, "SCÈNE");
    let cell = ((ui.available_width() - 6.0) / 2.0).floor();
    egui::Grid::new("labs").num_columns(2).spacing([6.0, 6.0]).show(ui, |ui| {
        for (i, lab) in Lab::ALL.into_iter().enumerate() {
            let r = ui.add_sized([cell, 26.0], egui::Button::selectable(m.scene.lab == lab, lab.name()));
            if r.on_hover_text(format!("{} (touche {})", lab.blurb(), i + 1)).clicked() {
                m.set_lab(lab);
            }
            if i % 2 == 1 {
                ui.end_row();
            }
        }
    });
    ui.label(egui::RichText::new(m.scene.lab.blurb()).small().color(theme::TEXT_MUTED));

    section(ui, "BACKEND");
    ui.horizontal(|ui| {
        for b in Backend::ALL {
            let offered = m.session().is_none_or(|s| s.capabilities.backend_offered(b));
            let r = ui.add_enabled(offered, egui::Button::selectable(m.backend == b, b.as_str().to_uppercase()));
            let r = r.on_disabled_hover_text("non proposé par ce runtime (CAPABILITIES)");
            if r.clicked() && m.backend != b {
                m.backend = b;
                m.sched.invalidate();
            }
        }
    });
    ui.label(
        egui::RichText::new("Aucun repli : un échec du backend demandé est affiché, jamais remplacé.")
            .small()
            .color(theme::TEXT_MUTED),
    );

    section(ui, "VISUALISATION");
    ui.horizontal_wrapped(|ui| {
        for v in ViewMode::ALL {
            let offered = m.session().is_none_or(|s| s.capabilities.view_modes.contains(&v));
            if v==ViewMode::Distance && m.native_action_enabled {
                let response=ui.add_enabled(
                    offered,egui::Button::new(view_label(v)).frame(false)
                        .min_size(egui::vec2(NATIVE_ACTION_SIZE.0,NATIVE_ACTION_SIZE.1))
                );
                if response.clicked() && m.view!=v {
                    m.view=v;
                    m.sched.invalidate(); // a real SDF view mode change, only once
                }
                let r=response.rect;
                let clip=ui.clip_rect();
                let content=ui.ctx().content_rect();
                let col=|c:Color32|Rgba8::new(c.r(),c.g(),c.b(),c.a());
                let palette=ActionPalette{
                    idle:col(theme::CONTROL),selected:col(theme::CONTROL_SELECTED),
                    hover:col(theme::CONTROL_HOVER),pressed:col(theme::CONTROL_PRESSED),
                    border:col(theme::BORDER),focus:col(theme::ACCENT),
                    disabled:col(theme::PANEL),selected_marker:col(theme::ACCENT)
                };
                let state=ActionVisualState{
                    selected:m.view==v,hovered:response.hovered(),focused:response.has_focus(),
                    pressed:response.is_pointer_button_down_on(),enabled:offered
                };
                let bounds=UiRect::new(r.min.x,r.min.y,r.width(),r.height());
                let clipping=UiRect::new(clip.min.x,clip.min.y,clip.width(),clip.height());
                if let Err(e)=m.native_action.update(
                    UiSize::new(content.width(),content.height()),
                    ui.ctx().pixels_per_point(),bounds,clipping,state,palette
                ){
                    m.native_action.failure();
                    m.native_action_enabled=false;
                    m.log(Level::Error,format!("01B G03: {e}; retour egui activé"));
                    ui.ctx().request_repaint();
                }
            } else {
                if v==ViewMode::Distance {m.native_action.clear();}
                if ui.add_enabled(offered, egui::Button::selectable(m.view == v, view_label(v))).clicked() && m.view != v {
                    m.view = v;
                    m.sched.invalidate();
                }
            }
        }
    });
    if m.view == ViewMode::Lit {
        ui.label(
            egui::RichText::new("Éclairé = ombrage dérivé des normales calculées (post-traitement 2D).")
                .small()
                .color(theme::WARNING),
        );
    }

    section(ui, "PRIMITIVES");
    primitives(ui, m);

    section(ui, "VUE");
    ui.horizontal(|ui| {
        ui.label(format!("zoom {:0.2}×  centre ({:0.2}, {:0.2})", m.camera.zoom, m.camera.cx, m.camera.cy));
        if m.native_reset_enabled {
            let response=ui.add_sized([NATIVE_RESET_SIZE.0,NATIVE_RESET_SIZE.1],
                egui::Button::new("Réinitialiser").frame(false));
            if response.clicked() && m.camera!=Camera::default(){
                m.camera=Camera::default();
                m.sched.invalidate(); // only once, and only if changed
            }
            let rect=response.rect;
            let clip=ui.clip_rect();
            let content=ui.ctx().content_rect();
            let col=|c:Color32|Rgba8::new(c.r(),c.g(),c.b(),c.a());
            let palette=ActionPalette{
                idle:col(theme::CONTROL),selected:col(theme::CONTROL_SELECTED),
                hover:col(theme::CONTROL_HOVER),pressed:col(theme::CONTROL_PRESSED),
                border:col(theme::BORDER),focus:col(theme::ACCENT),
                disabled:col(theme::PANEL),selected_marker:col(theme::ACCENT)
            };
            let state=ActionVisualState{
                selected:m.camera==Camera::default(),hovered:response.hovered(),
                focused:response.has_focus(),pressed:response.is_pointer_button_down_on(),
                enabled:true
            };
            let bounds=UiRect::new(rect.min.x,rect.min.y,rect.width(),rect.height());
            let clipping=UiRect::new(clip.min.x,clip.min.y,clip.width(),clip.height());
            if let Err(e)=m.native_reset.update(
                UiSize::new(content.width(),content.height()),ui.ctx().pixels_per_point(),
                bounds,clipping,state,palette
            ){
                m.native_reset.failure();
                m.native_reset_enabled=false;
                m.log(Level::Error,format!("01C native layout: {e}; retour egui activé"));
                ui.ctx().request_repaint();
            }
        } else {
            m.native_reset.clear();
            if ui.small_button("Réinitialiser").clicked() && m.camera!=Camera::default(){
                m.camera=Camera::default();
                m.sched.invalidate();
            }
        }
    });
    if m.native_toggle_enabled {
        ui.horizontal(|ui| {
            // One egui Button owns the WHOLE row (thumb + text):
            // label, pointer, focus and keyboard activation remain accessible
            // through the existing egui action owner until P3.
            let response=ui.add_sized(
                [ui.available_width(),NATIVE_TOGGLE_SIZE.1],
                egui::Button::new("Contours de contrôle (G)").frame(false)
            );
            let rect=egui::Rect::from_min_size(
                response.rect.min,egui::vec2(NATIVE_TOGGLE_SIZE.0,NATIVE_TOGGLE_SIZE.1));
            if response.clicked() {
                m.overlay = !m.overlay; // One semantic action; SDF unchanged.
            }
            // egui paints the text, blob.in paints only the native toggle.
            let clip=ui.clip_rect();
            let content=ui.ctx().content_rect();
            let col=|c:Color32|Rgba8::new(c.r(),c.g(),c.b(),c.a());
            let colors=TogglePalette {
                track_off:col(theme::CONTROL),track_on:col(theme::CONTROL_SELECTED),
                border:col(theme::BORDER),thumb:col(theme::TEXT_STRONG),
                thumb_disabled:col(theme::TEXT_MUTED),focus:col(theme::ACCENT),
            };
            let state=ToggleVisualState {
                checked:m.overlay,hovered:response.hovered(),
                focused:response.has_focus(),enabled:true,
            };
            let bound=UiRect::new(rect.min.x,rect.min.y,rect.width(),rect.height());
            let clipping=UiRect::new(clip.min.x,clip.min.y,clip.width(),clip.height());
            match m.native_toggle.update(
                UiSize::new(content.width(),content.height()),
                ui.ctx().pixels_per_point(),bound,clipping,state,colors
            ) {
                Ok(_) => {},
                Err(e) => {
                    m.native_toggle.failures+=1;
                    m.native_toggle_enabled=false;
                    m.log(Level::Error,format!("01A G03: {e}; retour egui activé"));
                    ui.ctx().request_repaint();
                }
            }
        });
    } else {
        m.native_toggle.clear();
        ui.checkbox(&mut m.overlay, "Contours de contrôle (G)"); // Explicit legacy fallback.
    }

    section(ui, "DIAGNOSTICS");
    diagnostics(ui, m, adapter, socket);

    section(ui, "JOURNAL");
    let now = Instant::now();
    for l in m.log.iter().rev().take(8) {
        let color = match l.level {
            Level::Info => theme::TEXT_MUTED,
            Level::Warn => theme::WARNING,
            Level::Error => theme::DANGER,
        };
        let age = now.duration_since(l.at).as_secs();
        ui.label(egui::RichText::new(format!("{age:>4}s  {}", l.text)).small().color(color));
    }
    ui.add_space(4.0);
    if ui.small_button("Raccourcis (F1)").clicked() {
        m.help = true;
    }
}

fn source_badge(ui: &mut egui::Ui, m: &Model) {
    let (text, color) = match &m.conn {
        Conn::Connected(_) if m.test_fixture() => ("SERVEUR DE TEST — pas une sortie blob.in", theme::WARNING),
        Conn::Connected(_) => ("RUNTIME blob.in (Render Bridge)", theme::ACCENT),
        Conn::Connecting { .. } => ("connexion…", theme::TEXT_MUTED),
        Conn::Failed { .. } => ("runtime injoignable", theme::DANGER),
    };
    egui::Frame::new()
        .stroke(Stroke::new(1.0, color))
        .corner_radius(egui::CornerRadius::same(theme::RADIUS_CONTROL))
        .inner_margin(egui::Margin::symmetric(8, 4))
        .show(ui, |ui| ui.label(egui::RichText::new(text).small().strong().color(color)));
}

fn primitives(ui: &mut egui::Ui, m: &mut Model) {
    let mut changed = false;
    let mut remove = None;
    let n = m.scene.circles.len();
    for i in 0..n {
        let c = m.scene.circles[i];
        let selected = m.scene.selected == Some(c.id);
        ui.horizontal(|ui| {
            if ui.add(egui::Button::selectable(selected, format!("#{}", c.id))).clicked() {
                m.scene.selected = if selected { None } else { Some(c.id) };
            }
            let mut op = c.op;
            ui.add_enabled_ui(i > 0, |ui| {
                egui::ComboBox::from_id_salt(("op", c.id))
                    .width(108.0)
                    .selected_text(format!("{} {}", op_glyph(op), op_label(op)))
                    .show_ui(ui, |ui| {
                        for o in CsgOp::ALL {
                            ui.selectable_value(&mut op, o, format!("{} {}", op_glyph(o), op_label(o)));
                        }
                    })
            })
            .response
            .on_disabled_hover_text("le premier cercle est toujours une union (contrat)");
            if op != c.op {
                m.scene.circles[i].op = op;
                changed = true;
            }
            let mut r = c.radius;
            if ui.add(egui::DragValue::new(&mut r).speed(0.002).range(0.01..=1.0).prefix("r ").max_decimals(3)).changed() {
                m.scene.circles[i].radius = r;
                changed = true;
            }
            if ui.add_enabled(n > 1, egui::Button::new(if theme::MATH_GLYPHS.load(std::sync::atomic::Ordering::Relaxed) { "✕" } else { "x" }).small()).on_hover_text("supprimer").clicked() {
                remove = Some(c.id);
            }
        });
    }
    if let Some(id) = remove {
        changed |= m.scene.remove(id);
    }
    ui.horizontal(|ui| {
        let can_add = m.scene.circles.len() < MAX_UI_PRIMITIVES;
        if ui.add_enabled(can_add, egui::Button::new("+ union lisse")).clicked() {
            let at = (m.camera.cx + 0.1, m.camera.cy + 0.1);
            m.scene.selected = m.scene.add(at, CsgOp::SmoothUnion);
            changed = true;
        }
        if ui.add_enabled(can_add, egui::Button::new("+ soustraction")).clicked() {
            let at = (m.camera.cx, m.camera.cy);
            m.scene.selected = m.scene.add(at, CsgOp::Subtract);
            changed = true;
        }
    });
    ui.label(
        egui::RichText::new(format!("k (union lisse) = {} — fixé par le moteur, non transmis.", blob_frame::ENGINE_SMOOTH_K))
            .small()
            .color(theme::TEXT_MUTED),
    );
    if changed {
        m.sched.invalidate();
    }
}

fn kv(ui: &mut egui::Ui, k: &str, v: impl Into<egui::WidgetText>) {
    ui.label(egui::RichText::new(k).small().color(theme::TEXT_MUTED));
    ui.label(v);
    ui.end_row();
}

fn diagnostics(ui: &mut egui::Ui, m: &mut Model, adapter: &str, socket: &std::path::Path) {
    egui::Grid::new("diag").num_columns(2).spacing([10.0, 3.0]).striped(false).show(ui, |ui| {
        kv(ui, "socket", egui::RichText::new(socket.display().to_string()).small());
        match &m.conn {
            Conn::Connected(s) => {
                kv(ui, "serveur", egui::RichText::new(&s.server).small());
                kv(ui, "protocole", "BLOB-FRAME-v1");
                let backends: Vec<String> = Backend::ALL
                    .iter()
                    .map(|b| {
                        let tag = if s.capabilities.backend_offered(*b) {
                            "implémenté"
                        } else if s.capabilities.backends_implemented.contains(b) {
                            "non configuré"
                        } else {
                            "absent"
                        };
                        format!("{} {tag}", b.as_str())
                    })
                    .collect();
                kv(ui, "backends", egui::RichText::new(backends.join(" · ")).small());
                kv(ui, "santé device", egui::RichText::new(&s.capabilities.device_healthy_now).small().monospace());
                let l = &s.capabilities;
                kv(ui, "limites", format!("≤ {}×{} · ≤ {} px", l.max_width_px, l.max_height_px, l.max_pixels));
                if let Some(rtt) = m.ping_rtt {
                    kv(ui, "ping IPC", format!("{:0.2} ms", rtt.as_secs_f64() * 1e3));
                }
            }
            Conn::Connecting { attempt } => kv(ui, "état", format!("connexion (tentative {attempt})")),
            Conn::Failed { reason, retry_in } => {
                kv(ui, "état", egui::RichText::new(reason).small().color(theme::DANGER));
                kv(ui, "nouvel essai", format!("dans {:0.1} s", retry_in.as_secs_f32()));
            }
        }
        if let Some(vp) = m.viewport {
            kv(ui, "viewport", format!("{}×{} px physiques", vp.physical.0, vp.physical.1));
        }
        match m.fit {
            Some(Fit::Render { w, h, scale }) => kv(ui, "résolution demandée", format!("{w}×{h} (échelle {scale:0.2})")),
            Some(Fit::TooSmall) => kv(ui, "résolution demandée", "viewport trop petit"),
            None => {}
        }
        kv(ui, "révision", format!("courante {} · affichée {}", m.sched.revision(), m.sched.presented_revision()));
        let c = m.sched.counters;
        kv(ui, "requêtes", format!("{} émises · {} en vol (max 1)", c.issued, m.sched.in_flight().map_or(0, |_| 1)));
        kv(ui, "issues", format!("{} affichées · {} obsolètes · {} échecs · {} rejetées", c.presented, c.stale, c.failed, m.rejected));
        if let Some(p) = &m.presented {
            ui.end_row();
            kv(ui, "FRAME AFFICHÉE", egui::RichText::new(format!("#{} rév. {}", p.meta.request_id, p.meta.scene_revision)).strong());
            kv(ui, "backend effectif", egui::RichText::new(p.meta.backend_actual.as_str()).strong().color(theme::ACCENT));
            let q = &p.meta.qualification;
            let qc = if q == "CUDA05F_GATE_PASS" { theme::ACCENT } else { theme::WARNING };
            kv(ui, "qualification", egui::RichText::new(q).small().monospace().color(qc));
            kv(ui, "vue", p.meta.view_mode.as_str());
            kv(ui, "génération", p.meta.generation.to_string());
            kv(ui, "dimensions", format!("{}×{} · stride {} · {} o", p.meta.width_px, p.meta.height_px, p.meta.stride_bytes, p.meta.buffer_bytes));
            kv(ui, "format", egui::RichText::new(&p.meta.format).small().monospace());
            kv(ui, "échelle de rendu", format!("{:0.2}", p.scale));
            kv(ui, "aller-retour client", format!("{:0.0} ms (mesuré par la surface)", p.round_trip.as_secs_f64() * 1e3));
            kv(ui, "cache", if p.meta.cache_hit { "hit" } else { "miss" });
            if let Some(seq) = p.meta.frame_sequence {
                kv(ui, "séquence runtime", seq.to_string());
            }
            kv(ui, "géométrie", egui::RichText::new(format!("sha256 {}…", &p.meta.geometry_sha256[..16])).small().monospace());
            kv(ui, "âge", format!("{:0.1} s", p.at.elapsed().as_secs_f32()));
        }
        kv(ui, "gestes", format!("{} commits · {} annulations · {} déplacements annulables",
            m.gestures.commits(), m.gestures.cancellations(), m.gestures.undo_count()));
        kv(ui, "présentation", egui::RichText::new(adapter).small());
    });
    if m.sched.in_flight().is_none() && m.sched.counters.failed > 0 && ui.small_button("Relancer le rendu").clicked() {
        m.sched.retry();
    }
}

fn viewport(ui: &mut egui::Ui, m: &mut Model, tex: Option<egui::TextureId>) {
    let (resp, painter) = ui.allocate_painter(ui.available_size(), Sense::click_and_drag());
    let r = resp.rect;
    let ppp = ui.ctx().pixels_per_point();
    let rect = Rect { x0: r.min.x, y0: r.min.y, x1: r.max.x, y1: r.max.y };
    let physical = ((r.width() * ppp).round().max(0.0) as u32, (r.height() * ppp).round().max(0.0) as u32);
    if m.viewport.is_some_and(|old| old.physical != physical || old.rect != rect) {
        m.gestures.cancel();
    }
    m.viewport = Some(Viewport { rect, physical });
    let baseline_view = View { rect, camera: m.camera };
    // The existing egui canvas owns input capture; AC04 consumes its accepted
    // response without installing a second competing G04 router.
    interact(ui, &resp, m, &baseline_view);
    let view = View { rect, camera: m.gestures.preview_camera(m.camera) };
    painter.rect_filled(r, 0.0, theme::CANVAS);

    // The last valid frame, placed by its own camera and resolution.
    if let (Some(p), Some(tex)) = (&m.presented, tex) {
        let fr = view.frame_rect(&p.camera, p.meta.width_px, p.meta.height_px);
        let dst = egui::Rect::from_min_max(Pos2::new(fr.x0, fr.y0), Pos2::new(fr.x1, fr.y1));
        let dim = !matches!(m.conn, Conn::Connected(_));
        let tint = if dim { Color32::from_gray(110) } else { Color32::WHITE };
        painter.image(tex, dst, egui::Rect::from_min_max(Pos2::ZERO, Pos2::new(1.0, 1.0)), tint);
    }

    if m.overlay || m.gestures.active() {
        overlay(&painter, m, &view);
    }
    status_overlay(&painter, m, r);
}

fn interact(ui: &egui::Ui, resp: &egui::Response, m: &mut Model, view: &View) {
    let pointer = resp.interact_pointer_pos().or(resp.hover_pos());
    let to_world = |p: Pos2| view.screen_to_world((p.x, p.y));
    let tol = view.world_len(6.0);
    if resp.drag_started() {
        if let Some(p) = pointer {
            // egui declares drag_start only after movement threshold.
            // Recover the actual press position so a small handle cannot be
            // missed merely because the cursor crossed that threshold.
            let down = p - resp.drag_delta();
            let w = to_world(down);
            let primary = ui.input(|i| i.pointer.primary_down());
            let hit = if primary { m.scene.hit(w, tol) } else { None };
            if m.gestures.begin(&m.scene, m.camera, hit) {
                if let Some(id) = hit {
                    m.scene.selected = Some(id);
                }
            }
        }
    }
    // egui 0.36 resets drag_delta() on the release frame.
    // Only accept movement while dragging; commit the LAST accepted preview.
    if resp.dragged() && ui.input(|i| i.pointer.delta() != Vec2::ZERO) {
        let displacement = resp.drag_delta();
        m.gestures.preview(&m.scene, *view, Translation {
            x: displacement.x, y: displacement.y
        });
    }
    if resp.drag_stopped() {
        match m.gestures.commit(&mut m.scene, &mut m.camera) {
            Commit::Moved(_) | Commit::Panned => m.sched.invalidate(),
            Commit::NoChange | Commit::Cancelled => {}
        }
    }
    if resp.clicked() {
        if let Some(p) = pointer {
            m.scene.selected = m.scene.hit(to_world(p), tol);
        }
    }
    if resp.hovered() && !m.gestures.active() {
        let (scroll, ctrl) = ui.input(|i| (i.smooth_scroll_delta.y, i.modifiers.ctrl || i.modifiers.command));
        if scroll != 0.0 {
            if let Some(p) = pointer {
                let target = m.scene.hit(to_world(p), tol).filter(|_| !ctrl);
                match target {
                    Some(id) => {
                        let r = m.scene.get(id).map(|c| c.radius * (scroll * 0.002).exp()).unwrap_or(0.1);
                        m.scene.selected = Some(id);
                        m.scene.set_radius(id, r);
                    }
                    None => m.camera = view.zoom_about((p.x, p.y), (scroll * 0.002).exp(), MIN_ZOOM, MAX_ZOOM),
                }
                m.sched.invalidate();
            }
        }
    }
}

/// Control outlines drawn by the surface from its own scene values, not from frames.
fn overlay(painter: &egui::Painter, m: &Model, view: &View) {
    for c in &m.scene.circles {
        let preview = m.gestures.preview_position(c.id);
        let (sx, sy) = view.world_to_screen(preview.unwrap_or((c.x, c.y)));
        let rad = c.radius / view.world_len(1.0);
        let selected = m.scene.selected == Some(c.id);
        let color = match c.op {
            CsgOp::Union | CsgOp::SmoothUnion => theme::ACCENT,
            CsgOp::Subtract => theme::DANGER,
            CsgOp::Intersect => theme::WARNING,
        };
        let alpha = if selected { 255 } else { 120 };
        let stroke = Stroke::new(if selected { 2.0 } else { 1.0 }, color.gamma_multiply_u8(alpha));
        let center = Pos2::new(sx, sy);
        if preview.is_some() {
            let (old_x, old_y) = view.world_to_screen((c.x,c.y));
            painter.circle_stroke(Pos2::new(old_x, old_y), rad,
                Stroke::new(1.0, theme::TEXT_MUTED.gamma_multiply_u8(110)));
            painter.line_segment([Pos2::new(old_x,old_y),center],
                Stroke::new(1.5, theme::WARNING.gamma_multiply_u8(180)));
        }
        if matches!(c.op, CsgOp::Union | CsgOp::SmoothUnion) {
            painter.circle_stroke(center, rad, stroke);
        } else {
            let pts: Vec<Pos2> = (0..=96).map(|k| {
                let a = k as f32 / 96.0 * std::f32::consts::TAU;
                center + Vec2::new(a.cos(), a.sin()) * rad
            }).collect();
            painter.extend(egui::Shape::dashed_line(&pts, stroke, 6.0, 4.0));
        }
        if selected {
            painter.circle_filled(center, 3.5, color);
        }
        painter.text(
            center + Vec2::new(rad * 0.72 + 4.0, -rad * 0.72 - 4.0),
            egui::Align2::LEFT_BOTTOM,
            format!("#{} {}", c.id, op_glyph(c.op)),
            egui::FontId::proportional(11.0),
            color.gamma_multiply_u8(alpha),
        );
    }
}

fn chip(painter: &egui::Painter, at: Pos2, text: &str, color: Color32) -> f32 {
    let galley = painter.layout_no_wrap(text.to_owned(), egui::FontId::proportional(12.0), color);
    let size = galley.size() + Vec2::new(16.0, 8.0);
    let rect = egui::Rect::from_min_size(at, size);
    painter.rect(rect, egui::CornerRadius::same(theme::RADIUS_CONTROL), theme::PANEL.gamma_multiply_u8(230), Stroke::new(1.0, color), egui::StrokeKind::Inside);
    painter.galley(at + Vec2::new(8.0, 4.0), galley, color);
    size.y
}

fn status_overlay(painter: &egui::Painter, m: &Model, r: egui::Rect) {
    let mut y = r.min.y + 12.0;
    let x = r.min.x + 12.0;
    if m.gestures.active() {
        y += chip(painter, Pos2::new(x, y),
            "GESTE AC04 — aperçu local · rendu runtime mis à jour au relâchement",
            theme::WARNING) + 6.0;
    }
    if m.test_fixture() {
        y += chip(painter, Pos2::new(x, y), "SERVEUR DE TEST — mires de référence, aucune géométrie évaluée · pas une sortie blob.in", theme::WARNING) + 6.0;
    }
    if let Some(p) = &m.presented {
        let text = format!(
            "{} · {} · {} · {}×{}",
            p.meta.backend_actual.as_str().to_uppercase(),
            view_label(p.meta.view_mode),
            p.meta.qualification,
            p.meta.width_px,
            p.meta.height_px
        );
        y += chip(painter, Pos2::new(x, y), &text, theme::TEXT) + 6.0;
    }
    if let Some(f) = m.sched.in_flight() {
        let secs = f.issued_at.elapsed().as_secs_f32();
        let text = format!("rendu {} en cours · {:0.1} s · la frame précédente reste affichée", m.backend.as_str(), secs);
        y += chip(painter, Pos2::new(x, y), &text, theme::ACCENT) + 6.0;
    }
    match &m.conn {
        Conn::Connected(s) if !s.capabilities.backend_offered(m.backend) => {
            y += chip(painter, Pos2::new(x, y), &format!("backend {} non proposé par ce runtime", m.backend.as_str()), theme::DANGER) + 6.0;
        }
        Conn::Connected(_) => {}
        Conn::Failed { reason, .. } => {
            y += chip(painter, Pos2::new(x, y), &format!("runtime injoignable — {reason}"), theme::DANGER) + 6.0;
        }
        Conn::Connecting { .. } => {
            y += chip(painter, Pos2::new(x, y), "connexion au runtime…", theme::TEXT_MUTED) + 6.0;
        }
    }
    if let Some(e) = &m.bounds_error {
        y += chip(painter, Pos2::new(x, y), e, theme::WARNING) + 6.0;
    }
    if m.fit == Some(Fit::TooSmall) {
        chip(painter, Pos2::new(x, y), "viewport trop petit pour le runtime (min 16×16 px)", theme::WARNING);
    }
    if let Some(l) = m.log.back().filter(|l| l.level == Level::Error && l.at.elapsed() < Duration::from_secs(6)) {
        chip(painter, Pos2::new(x, r.max.y - 36.0), &l.text, theme::DANGER);
    }
    if m.presented.is_none() && matches!(m.conn, Conn::Connected(_)) {
        let g = painter.layout_no_wrap("en attente de la première frame…".into(), egui::FontId::proportional(14.0), theme::TEXT_MUTED);
        painter.galley(r.center() - g.size() / 2.0, g, theme::TEXT_MUTED);
    }
}

fn help_window(ctx: &egui::Context, m: &mut Model) {
    let mut open = true;
    egui::Window::new("Raccourcis").open(&mut open).collapsible(false).resizable(false).show(ctx, |ui| {
        egui::Grid::new("help").num_columns(2).spacing([16.0, 4.0]).show(ui, |ui| {
            for (k, v) in [
                ("1 … 6", "changer de lab"),
                ("glisser un cercle", "aperçu local · appliquer au relâchement"),
                ("Ctrl+Z", "annuler le dernier déplacement"),
                ("molette sur un cercle", "changer son rayon"),
                ("glisser le fond", "déplacer la vue"),
                ("molette / Ctrl+molette", "zoom (transformation côté surface)"),
                ("Tab · ←↑→↓ · + −", "sélection · déplacer · rayon"),
                ("O", "changer l'opération du cercle sélectionné"),
                ("Suppr", "supprimer le cercle sélectionné"),
                ("B · V", "backend suivant · visualisation suivante"),
                ("R · G", "réinitialiser la vue · contours de contrôle"),
                ("Ctrl+Q", "quitter"),
            ] {
                ui.label(egui::RichText::new(k).strong());
                ui.label(v);
                ui.end_row();
            }
        });
    });
    if !open {
        m.help = false;
    }
}

#[cfg(test)]
mod ac04_production_input_tests {
    use super::*;
    use egui::{Event, Modifiers, PointerButton};

    fn make() -> Model {
        Model::new(&Options {
            socket: PathBuf::from("/tmp/blob-ac04-test-nonexistent.sock"),
            trace: None, lab: Lab::Primitive, backend: Backend::Cpu,
            size: (1100, 700), exercise: false,
        })
    }
    fn frame(ctx: &egui::Context, m: &mut Model, time: f64, events: Vec<Event>) {
        let raw = egui::RawInput {
            screen_rect: Some(egui::Rect::from_min_size(
                Pos2::ZERO, Vec2::new(1100.0, 700.0))),
            time: Some(time),
            events,
            ..egui::RawInput::default()
        };
        let mut result = ctx.run_ui(raw, |ui| {
            ui_root(ui, m, None, "AC04 mock GPU", std::path::Path::new("/tmp/none"));
        });
        result.textures_delta.clear();
    }
    fn pointer(pos: Pos2, down: bool) -> Event {
        Event::PointerButton {
            pos, button: PointerButton::Primary, pressed: down,
            modifiers: Modifiers::default(),
        }
    }
    #[test]
    fn ui01c_reset_real_camera_one_commit_then_idempotent_and_others_survive(){
        let ctx=egui::Context::default();
        let mut m=make();
        m.native_reset_enabled=true;
        m.native_action_enabled=true;
        m.native_toggle_enabled=true;
        m.camera.cx=0.43;
        m.camera.zoom=1.6;
        frame(&ctx,&mut m,0.,vec![]);
        let witness=m.native_reset.display().expect("01C native display in production UI").clone();
        assert_eq!(witness.surface.0,0x010C);
        assert_eq!(witness.commands.len(),3);
        let r=witness.commands[0].rect;
        let pos=Pos2::new(r.x+25.,r.y+13.);
        let rev=m.sched.revision();
        frame(&ctx,&mut m,0.016,vec![Event::PointerMoved(pos),pointer(pos,true)]);
        frame(&ctx,&mut m,0.032,vec![pointer(pos,false)]);
        assert_eq!(m.camera,Camera::default());
        assert_eq!(m.sched.revision(),rev+1);
        assert!(m.native_reset.display().unwrap().source_ui_revision>=2);
        assert!(m.native_toggle.display().is_some());
        assert!(m.native_action.display().is_some());
        frame(&ctx,&mut m,0.048,vec![pointer(pos,true)]);
        frame(&ctx,&mut m,0.064,vec![pointer(pos,false)]);
        assert_eq!(m.sched.revision(),rev+1,"reset already default is idempotent");
    }

    #[test]
    fn ui01b_egui_real_distance_action_then_toggle_separate_authorities() {
        let ctx=egui::Context::default();
        let mut m=make();
        m.native_action_enabled=true;
        m.native_toggle_enabled=true;
        frame(&ctx,&mut m,0.0,vec![]);
        assert_eq!(m.view,ViewMode::Coverage);
        let r=m.native_action.display().expect("G02/G03 action list in real UI").commands[0].rect;
        let pos=Pos2::new(r.x+30.0,r.y+13.0);
        let baseline_revision=m.sched.revision();
        let original_geometry=m.scene.clone();
        frame(&ctx,&mut m,0.016,vec![Event::PointerMoved(pos),pointer(pos,true)]);
        frame(&ctx,&mut m,0.032,vec![pointer(pos,false)]);
        assert_eq!(m.view,ViewMode::Distance,"Distance must change real view");
        assert_eq!(m.sched.revision(),baseline_revision+1,"one runtime invalidation");
        assert_eq!(m.scene,original_geometry,"visualization must not change geometry");
        assert_eq!(m.native_action.display().unwrap().source_ui_revision,2);
        assert!(m.overlay,"second widget must be independent");
        frame(&ctx,&mut m,0.048,vec![pointer(pos,true)]);
        frame(&ctx,&mut m,0.064,vec![pointer(pos,false)]);
        assert_eq!(m.sched.revision(),baseline_revision+1,"reselecting same view is a no-op");
        let t=m.native_toggle.display().expect("01A survives").commands[0].rect;
        let toggle_pos=Pos2::new(t.x+26.0,t.y+13.0);
        frame(&ctx,&mut m,0.08,vec![Event::PointerMoved(toggle_pos),pointer(toggle_pos,true)]);
        frame(&ctx,&mut m,0.096,vec![pointer(toggle_pos,false)]);
        assert!(!m.overlay,"01A toggle must still function");
        assert_eq!(m.sched.revision(),baseline_revision+1,"UI-only action cannot rerender");
        assert_eq!(m.view,ViewMode::Distance,"01B selection must persist");
        assert_eq!(m.native_toggle.display().unwrap().source_ui_revision,2);
    }

    #[test]
    fn ui01a_egui_entire_label_and_thumb_both_activate_once() {
        let ctx=egui::Context::default();
        let mut m=make();
        m.native_toggle_enabled=true;
        frame(&ctx,&mut m,0.0,vec![]);
        let first=m.native_toggle.display().expect("01A native scene in actual ui_root").clone();
        let r=first.commands[0].rect;
        let start=m.sched.revision();
        let label=Pos2::new(r.x+110.0,r.y+13.0);
        frame(&ctx,&mut m,0.016,vec![Event::PointerMoved(label),pointer(label,true)]);
        frame(&ctx,&mut m,0.032,vec![pointer(label,false)]);
        assert!(!m.overlay,"the egui label must still toggle the semantic state");
        assert_eq!(m.sched.revision(),start,"UI-only toggle cannot schedule SDF");
        let changed=m.native_toggle.display().expect("off visual retained");
        assert_eq!(changed.source_node,first.source_node);
        let thumb=Pos2::new(r.x+26.0,r.y+13.0);
        frame(&ctx,&mut m,0.048,vec![Event::PointerMoved(thumb),pointer(thumb,true)]);
        frame(&ctx,&mut m,0.064,vec![pointer(thumb,false)]);
        assert!(m.overlay,"the graphic area must also toggle exactly once");
        assert_eq!(m.sched.revision(),start);
    }

    #[test]
    fn real_egui_canvas_drag_previews_then_one_commit_then_undo() {
        let ctx = egui::Context::default();
        let mut m = make();
        frame(&ctx,&mut m,0.0,vec![]);
        let vp=m.viewport.expect("canvas available");
        let view=View{rect:vp.rect,camera:m.camera};
        let id=m.scene.circles[0].id;
        let c=m.scene.get(id).unwrap();
        let (x,y)=view.world_to_screen((c.x,c.y));
        let down=Pos2::new(x,y);
        let target=Pos2::new(x+90.0,y+15.0);
        let previous=m.scene.clone();
        let previous_revision=m.sched.revision();
        frame(&ctx,&mut m,0.016,vec![Event::PointerMoved(down),pointer(down,true)]);
        frame(&ctx,&mut m,0.032,vec![Event::PointerMoved(target)]);
        assert!(m.gestures.active(),"egui must deliver a drag to AC04");
        assert_eq!(m.scene.circles,previous.circles, "not one geometry write on preview");
        assert_eq!(m.sched.revision(),previous_revision, "no render request on preview");
        let accepted = m.gestures.preview_position(id).expect("native preview");
        // Regression from AC05: egui redraws with NO new pointer motion must
        // not overwrite the last accepted preview with drag_delta()==0.
        frame(&ctx, &mut m, 0.037, vec![]);
        frame(&ctx, &mut m, 0.042, vec![]);
        assert_eq!(m.gestures.preview_position(id), Some(accepted));
        assert_eq!(m.sched.revision(), previous_revision);
        frame(&ctx,&mut m,0.048,vec![pointer(target,false)]);
        assert_eq!(m.gestures.commits(),1, "one commit, not one per motion");
        assert_eq!(m.gestures.undo_count(),1);
        assert_eq!(m.sched.revision(),previous_revision+1);
        assert_ne!(m.scene,previous);
        let mut modifiers=Modifiers::default();
        modifiers.ctrl=true;
        modifiers.command=true;
        frame(&ctx,&mut m,0.064,vec![Event::ModifiersChanged(modifiers),Event::Key {
            key:egui::Key::Z, physical_key:None, pressed:true, repeat:false,
            modifiers,
        }]);
        assert_eq!(m.scene.circles,previous.circles,"Ctrl+Z restores one committed move");
        assert_eq!(m.sched.revision(),previous_revision+2);
    }

    #[test]
    fn real_egui_pan_is_preview_only_until_release() {
        let ctx=egui::Context::default();
        let mut m=make();
        frame(&ctx,&mut m,0.0,vec![]);
        let vp=m.viewport.expect("real egui viewport");
        let down=Pos2::new(vp.rect.x0+18.0,vp.rect.y0+160.0);
        let target=down+Vec2::new(90.0,60.0);
        let original_cam=m.camera;
        let original_scene=m.scene.clone();
        let revision=m.sched.revision();
        frame(&ctx,&mut m,0.016,vec![Event::PointerMoved(down),pointer(down,true)]);
        frame(&ctx,&mut m,0.032,vec![Event::PointerMoved(target)]);
        assert!(m.gestures.active());
        assert_ne!(m.gestures.preview_camera(m.camera),original_cam);
        assert_eq!(m.camera,original_cam);
        assert_eq!(m.scene,original_scene);
        assert_eq!(m.sched.revision(),revision);
        frame(&ctx,&mut m,0.048,vec![pointer(target,false)]);
        assert_ne!(m.camera,original_cam);
        assert_eq!(m.scene,original_scene);
        assert_eq!(m.gestures.commits(),1);
        assert_eq!(m.sched.revision(),revision+1);
    }

    #[test]
    fn egui_geometry_epoch_change_cancels_active_drag() {
        let ctx=egui::Context::default();
        let mut m=make();
        frame(&ctx,&mut m,0.0,vec![]);
        let vp=m.viewport.unwrap();
        let v=View{rect:vp.rect,camera:m.camera};
        let circle=m.scene.circles[0];
        let (x,y)=v.world_to_screen((circle.x,circle.y));
        let from=Pos2::new(x,y);
        let to=Pos2::new(x+90.0,y);
        let original=m.scene.clone();
        let revision=m.sched.revision();
        frame(&ctx,&mut m,0.016,vec![Event::PointerMoved(from),pointer(from,true)]);
        frame(&ctx,&mut m,0.032,vec![Event::PointerMoved(to)]);
        assert!(m.gestures.active());
        m.viewport.as_mut().unwrap().physical.0+=1;
        frame(&ctx,&mut m,0.048,vec![Event::PointerMoved(to+Vec2::new(3.0,0.0))]);
        assert!(!m.gestures.active());
        frame(&ctx,&mut m,0.064,vec![pointer(to,false)]);
        assert_eq!(m.scene.circles,original.circles);
        assert_eq!(m.gestures.commits(),0);
        assert_eq!(m.sched.revision(),revision);
    }

    #[test]
    fn real_egui_canvas_escape_during_drag_keeps_scene_and_scheduler() {
        let ctx = egui::Context::default();
        let mut m = make();
        frame(&ctx,&mut m,0.0,vec![]);
        let vp=m.viewport.unwrap();
        let view=View{rect:vp.rect,camera:m.camera};
        let c=m.scene.circles[0];
        let (x,y)=view.world_to_screen((c.x,c.y));
        let down=Pos2::new(x,y);
        let changed=Pos2::new(x+100.0,y);
        let before=m.scene.clone();
        let revision=m.sched.revision();
        frame(&ctx,&mut m,0.016,vec![Event::PointerMoved(down),pointer(down,true)]);
        frame(&ctx,&mut m,0.032,vec![Event::PointerMoved(changed)]);
        assert!(m.gestures.active());
        frame(&ctx,&mut m,0.048,vec![Event::Key{
            key:egui::Key::Escape,physical_key:None,pressed:true,repeat:false,
            modifiers:Modifiers::default()
        }]);
        assert!(!m.gestures.active());
        frame(&ctx,&mut m,0.064,vec![pointer(changed,false)]);
        assert_eq!(m.scene,before);
        assert_eq!(m.sched.revision(),revision);
    }
}
