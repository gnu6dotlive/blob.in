//! blob.in native GPU UI lab. No F4 broker required.
//! Interactivity is real Wayland/winit input; --probe-frames scripts separate test states.
use std::fs::File;
use std::io::Write;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};

use blobin_showcase::ui_motion::{UiAction, UiRuntime};
use blobin_showcase::ui_widgets;
use serde_json::json;
use winit::application::ApplicationHandler;
use winit::event::{ElementState, StartCause, WindowEvent};
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop};
use winit::keyboard::{Key, NamedKey};
use winit::platform::wayland::WindowAttributesExtWayland;
use winit::window::{Window, WindowId};

struct Graphics {
    window: Arc<Window>,
    surface: wgpu::Surface<'static>,
    config: wgpu::SurfaceConfiguration,
    device: wgpu::Device,
    queue: wgpu::Queue,
    renderer: egui_wgpu::Renderer,
    egui: egui_winit::State,
}
struct Lab {
    gpu: Option<Graphics>,
    runtime: UiRuntime,
    last_tick: Instant,
    frames: u64,
    max_frames: u64,
    trace: Option<File>,
    failure: Option<String>,
}
impl Lab {
    fn init(&mut self, el: &ActiveEventLoop) -> Result<(), String> {
        let window = Arc::new(
            el.create_window(
                Window::default_attributes()
                    .with_title("blob.in / native UI engine — motion lab")
                    .with_name("live.gnu6.blobin-ui-lab", "blobin-ui-lab")
                    .with_inner_size(winit::dpi::LogicalSize::new(1280, 720))
                    .with_min_inner_size(winit::dpi::LogicalSize::new(640, 440)),
            )
            .map_err(|e| e.to_string())?,
        );
        let mut desc = wgpu::InstanceDescriptor::new_without_display_handle();
        desc.backends = wgpu::Backends::VULKAN;
        let instance = wgpu::Instance::new(desc);
        let surface = instance
            .create_surface(window.clone())
            .map_err(|e| e.to_string())?;
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::HighPerformance,
            compatible_surface: Some(&surface),
            ..Default::default()
        }))
        .map_err(|e| format!("adapter: {e}"))?;
        let adapter_info = adapter.get_info();
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
            label: Some("blob.in-native-ui-runtime"),
            ..Default::default()
        }))
        .map_err(|e| format!("device: {e}"))?;
        let size = window.inner_size();
        let mut config = surface
            .get_default_config(&adapter, size.width.max(1), size.height.max(1))
            .ok_or("incompatible Vulkan surface")?;
        let caps = surface.get_capabilities(&adapter);
        if let Some(format) = caps.formats.iter().find(|f| !f.is_srgb()) {
            config.format = *format;
        }
        config.present_mode = wgpu::PresentMode::AutoVsync;
        surface.configure(&device, &config);
        let renderer = egui_wgpu::Renderer::new(
            &device,
            config.format,
            egui_wgpu::RendererOptions::default(),
        );
        let ctx = egui::Context::default();
        let mut style = egui::Style {
            visuals: egui::Visuals::dark(),
            ..Default::default()
        };
        style.visuals.override_text_color = Some(egui::Color32::WHITE);
        ctx.set_global_style(style);
        let egui = egui_winit::State::new(
            ctx,
            egui::ViewportId::ROOT,
            &window,
            Some(window.scale_factor() as f32),
            None,
            Some(device.limits().max_texture_dimension_2d as usize),
        );
        println!(
            "BLOBIN_UI_GPU_READY adapter={} backend={:?} format={:?}",
            adapter_info.name, adapter_info.backend, config.format
        );
        window.request_redraw();
        self.gpu = Some(Graphics {
            window,
            surface,
            config,
            device,
            queue,
            renderer,
            egui,
        });
        Ok(())
    }

    fn record(&mut self, kind: &str, value: serde_json::Value) {
        if let Some(file) = self.trace.as_mut() {
            let _ = writeln!(
                file,
                "{}",
                json!({
                    "kind":kind,"frame":self.frames,"revision":self.runtime.ui_revision,
                    "data":value
                })
            );
        }
    }
    fn scripted_probe_step(&mut self) {
        if self.max_frames == 0 {
            return;
        }
        let action = match self.frames {
            25 => Some(UiAction::SelectSurface(1)),
            50 => Some(UiAction::ToggleInspector),
            75 => Some(UiAction::SelectSurface(2)),
            100 => Some(UiAction::ToggleReducedMotion),
            125 => Some(UiAction::ToggleReducedMotion),
            150 => Some(UiAction::ToggleInspector),
            _ => None,
        };
        if let Some(action) = action {
            self.runtime.dispatch(action);
            self.record("scripted_action", json!({"action":format!("{action:?}")}));
        }
    }

    fn render(&mut self) {
        let start = Instant::now();
        let dt = start.duration_since(self.last_tick).as_secs_f32().min(0.1);
        self.last_tick = start;
        self.scripted_probe_step();
        let Some(g) = self.gpu.as_mut() else { return };
        let input = g.egui.take_egui_input(&g.window);
        let context = g.egui.egui_ctx().clone();
        let before = self.runtime.ui_revision;
        let mut response = context.run_ui(input, |ui| {
            ui_widgets::draw(ui, &mut self.runtime, dt, self.frames);
        });
        let revision = self.runtime.ui_revision;
        if revision != before {
            self.record("input_action", json!({"old":before,"new":revision}));
        }
        let mut frame_report = None;
        let Some(g) = self.gpu.as_mut() else { return };
        g.egui
            .handle_platform_output(&g.window, response.platform_output);
        let ppp = response.pixels_per_point;
        let jobs = context.tessellate(response.shapes, ppp);
        for (id, deltas) in response.textures_delta.set.drain() {
            for delta in deltas {
                g.renderer.update_texture(&g.device, &g.queue, id, &delta);
            }
        }
        let frame = match g.surface.get_current_texture() {
            wgpu::CurrentSurfaceTexture::Success(f)
            | wgpu::CurrentSurfaceTexture::Suboptimal(f) => Some(f),
            wgpu::CurrentSurfaceTexture::Outdated | wgpu::CurrentSurfaceTexture::Lost => {
                g.surface.configure(&g.device, &g.config);
                None
            }
            other => {
                self.failure = Some(format!("surface: {other:?}"));
                None
            }
        };
        if let Some(frame) = frame {
            let target = frame
                .texture
                .create_view(&wgpu::TextureViewDescriptor::default());
            let screen = egui_wgpu::ScreenDescriptor {
                size_in_pixels: [g.config.width, g.config.height],
                pixels_per_point: ppp,
            };
            let mut encoder = g
                .device
                .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                    label: Some("blobin-ui-frame"),
                });
            let extra =
                g.renderer
                    .update_buffers(&g.device, &g.queue, &mut encoder, &jobs, &screen);
            {
                let pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                    label: Some("blobin-native-ui-vulkan"),
                    color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                        view: &target,
                        depth_slice: None,
                        resolve_target: None,
                        ops: wgpu::Operations {
                            load: wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                            store: wgpu::StoreOp::Store,
                        },
                    })],
                    ..Default::default()
                });
                g.renderer
                    .render(&mut pass.forget_lifetime(), &jobs, &screen);
            }
            g.queue.submit(extra.into_iter().chain([encoder.finish()]));
            g.window.pre_present_notify();
            g.queue.present(frame);
            self.frames += 1;
            if self.frames % 30 == 0 {
                frame_report = Some(json!({
                    "width":g.config.width,"height":g.config.height,
                    "phase":self.runtime.phase,
                    "scene":self.runtime.selected,
                    "motion":self.runtime.motion_on,
                    "inspector":self.runtime.inspector.value,
                    "cpu_frame_ms":start.elapsed().as_secs_f64()*1000.0
                }));
                println!(
                    "BLOBIN_UI_SUBMITTED frame={} revision={} selected={}",
                    self.frames, self.runtime.ui_revision, self.runtime.selected
                );
            }
        }
        for id in response.textures_delta.free.drain() {
            g.renderer.free_texture(&id);
        }
        if let Some(report) = frame_report {
            self.record("gpu_frame_submitted", report);
        }
    }
}
impl ApplicationHandler for Lab {
    fn resumed(&mut self, el: &ActiveEventLoop) {
        if self.gpu.is_none() {
            if let Err(error) = self.init(el) {
                eprintln!("BLOBIN_UI_INIT_FAILED {error}");
                self.failure = Some(error);
                el.exit();
            }
        }
    }
    fn new_events(&mut self, _el: &ActiveEventLoop, cause: StartCause) {
        if matches!(cause, StartCause::ResumeTimeReached { .. }) {
            if let Some(g) = &self.gpu {
                g.window.request_redraw();
            }
        }
    }
    fn window_event(&mut self, el: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        if matches!(&event, WindowEvent::RedrawRequested) {
            self.render();
            if self.max_frames != 0 && self.frames >= self.max_frames {
                println!(
                    "BLOBIN_UI_PROBE_COMPLETE frames={} revisions={}",
                    self.frames, self.runtime.ui_revision
                );
                el.exit();
                return;
            }
            if self.runtime.active_motion() || self.max_frames != 0 {
                el.set_control_flow(ControlFlow::WaitUntil(
                    Instant::now() + Duration::from_millis(16),
                ));
            } else {
                el.set_control_flow(ControlFlow::Wait);
            }
            return;
        }
        if let Some(g) = &mut self.gpu {
            let input = g.egui.on_window_event(&g.window, &event);
            match event {
                WindowEvent::CloseRequested => {
                    el.exit();
                    return;
                }
                WindowEvent::Resized(size) => {
                    if size.width > 0 && size.height > 0 {
                        g.config.width = size.width;
                        g.config.height = size.height;
                        g.surface.configure(&g.device, &g.config);
                        g.window.request_redraw();
                    }
                }
                WindowEvent::KeyboardInput { event, .. }
                    if event.state == ElementState::Pressed =>
                {
                    match event.logical_key {
                        Key::Named(NamedKey::Space) => {
                            self.runtime.dispatch(UiAction::ToggleMotion);
                            g.window.request_redraw();
                        }
                        Key::Named(NamedKey::Escape) => {
                            el.exit();
                            return;
                        }
                        Key::Character(ref s) if s.eq_ignore_ascii_case("r") => {
                            self.runtime.dispatch(UiAction::ToggleReducedMotion);
                            g.window.request_redraw();
                        }
                        Key::Character(ref s) if s.eq_ignore_ascii_case("i") => {
                            self.runtime.dispatch(UiAction::ToggleInspector);
                            g.window.request_redraw();
                        }
                        _ => {}
                    }
                }
                WindowEvent::RedrawRequested => unreachable!("redraw handled before input borrow"),
                _ => {}
            }
            if input.repaint {
                g.window.request_redraw();
            }
        }
        if self.runtime.active_motion() || self.max_frames != 0 {
            el.set_control_flow(ControlFlow::WaitUntil(
                Instant::now() + Duration::from_millis(16),
            ));
        } else {
            el.set_control_flow(ControlFlow::Wait);
        }
    }
}
fn main() -> Result<(), String> {
    let mut trace = None;
    let mut max_frames = 0;
    for arg in std::env::args().skip(1) {
        if let Some(value) = arg.strip_prefix("--trace=") {
            trace = Some(File::create(PathBuf::from(value)).map_err(|e| e.to_string())?);
        } else if let Some(value) = arg.strip_prefix("--probe-frames=") {
            max_frames = value.parse::<u64>().map_err(|e| e.to_string())?;
            if max_frames == 0 || max_frames > 1200 {
                return Err("probe frames must be in 1..=1200".into());
            }
        } else if arg == "--help" {
            println!("blobin-ui-lab [--trace=/path/trace.jsonl] [--probe-frames=180]");
            println!("Mouse: click elements | Space: motion | R: reduced motion | I: inspector | Esc: quit");
            return Ok(());
        } else {
            return Err(format!("unknown argument: {arg}"));
        }
    }
    let loop_ = EventLoop::new().map_err(|e| e.to_string())?;
    loop_.set_control_flow(ControlFlow::Wait);
    let mut app = Lab {
        gpu: None,
        runtime: UiRuntime::default(),
        last_tick: Instant::now(),
        frames: 0,
        max_frames,
        trace,
        failure: None,
    };
    loop_.run_app(&mut app).map_err(|e| e.to_string())?;
    if let Some(error) = app.failure {
        return Err(error);
    }
    if max_frames != 0 && app.frames != max_frames {
        return Err("incomplete native GPU probe".into());
    }
    Ok(())
}
