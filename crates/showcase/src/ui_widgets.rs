//! Native blob.in interface primitives: GPU-tessellated egui geometry.
//! Stable IDs, typed actions and responsive canvas (no pre-rendered static images).
use crate::ui_motion::{UiAction, UiRuntime};
use egui::{Align2, Color32, FontId, Pos2, Rect, Sense, Stroke, Ui, Vec2};

const BG: Color32 = Color32::from_rgb(8, 13, 23);
const PANEL: Color32 = Color32::from_rgb(15, 24, 36);
const PANEL_HI: Color32 = Color32::from_rgb(22, 35, 49);
const TEXT: Color32 = Color32::from_rgb(234, 242, 245);
const MUTED: Color32 = Color32::from_rgb(135, 155, 173);
const CYAN: Color32 = Color32::from_rgb(102, 229, 217);
const ORANGE: Color32 = Color32::from_rgb(245, 162, 108);
const OUTLINE: Color32 = Color32::from_rgb(46, 67, 78);

fn rect(ui: &Ui, r: Rect, fill: Color32, radius: u8) {
    ui.painter()
        .rect_filled(r, egui::CornerRadius::same(radius), fill);
}
fn text(ui: &Ui, at: Pos2, label: &str, size: f32, color: Color32, align: Align2) {
    ui.painter()
        .text(at, align, label, FontId::proportional(size), color);
}
fn line(ui: &Ui, x: f32, y: f32, w: f32, color: Color32) {
    ui.painter().line_segment(
        [Pos2::new(x, y), Pos2::new(x + w, y)],
        Stroke::new(1.0, color),
    );
}
fn button(ui: &mut Ui, id: &'static str, r: Rect, label: &str, active: bool) -> bool {
    let response = ui.interact(r, egui::Id::new(id), Sense::click());
    let fill = if response.hovered() {
        PANEL_HI
    } else if active {
        Color32::from_rgb(22, 56, 63)
    } else {
        PANEL
    };
    rect(ui, r, fill, 11);
    ui.painter().rect_stroke(
        r,
        egui::CornerRadius::same(11),
        Stroke::new(1.0, if active { CYAN } else { OUTLINE }),
        egui::StrokeKind::Inside,
    );
    text(
        ui,
        r.center(),
        label,
        13.0,
        if active { CYAN } else { TEXT },
        Align2::CENTER_CENTER,
    );
    response.clicked()
}

/// Animate a real organic contour, rather than a static texture sprite.
pub fn organic_vertices(center: Pos2, radius: f32, phase: f32, points: usize) -> Vec<Pos2> {
    (0..points)
        .map(|i| {
            let a = std::f32::consts::TAU * (i as f32 / points as f32);
            let wobble = (a * 3.0 + phase * std::f32::consts::TAU).sin() * 0.075
                + (a * 5.0 - phase * std::f32::consts::TAU * 0.7).cos() * 0.035;
            let r = radius * (1.0 + wobble);
            Pos2::new(center.x + r * a.cos(), center.y + r * a.sin())
        })
        .collect()
}

fn blob(ui: &Ui, center: Pos2, radius: f32, phase: f32, hover: f32, selected: usize) {
    for i in (0..9).rev() {
        let r = radius * (1.10 + i as f32 * 0.105);
        let alpha = 4 + (9 - i) * 2;
        let hue = if selected == 1 { ORANGE } else { CYAN };
        let fill = Color32::from_rgba_unmultiplied(hue.r(), hue.g(), hue.b(), alpha);
        ui.painter().add(egui::Shape::convex_polygon(
            organic_vertices(center, r, phase + i as f32 * 0.03, 96),
            fill,
            Stroke::NONE,
        ));
    }
    let main = if selected == 1 { ORANGE } else { CYAN };
    ui.painter().add(egui::Shape::convex_polygon(
        organic_vertices(center, radius * (1.0 + hover * 0.06), phase, 128),
        Color32::from_rgb(28, 94, 104),
        Stroke::new(1.2, main),
    ));
    ui.painter().circle_filled(
        Pos2::new(center.x - radius * 0.22, center.y - radius * 0.25),
        radius * 0.32,
        Color32::from_rgba_unmultiplied(130, 244, 230, 38),
    );
    ui.painter().circle_stroke(
        center,
        radius * 0.65,
        Stroke::new(1.0, Color32::from_rgba_unmultiplied(210, 255, 245, 70)),
    );
    text(ui, center, "blob.in", 32.0, TEXT, Align2::CENTER_CENTER);
}
/// Render the native UI with stable widgets and animation; true pointer/keyboard input.
pub fn draw(ui: &mut Ui, state: &mut UiRuntime, dt_seconds: f32, frames: u64) {
    let outer = ui.max_rect();
    let w = outer.width();
    let h = outer.height();
    let origin = outer.min;
    let hovered_canvas = ui
        .ctx()
        .input(|i| i.pointer.hover_pos())
        .is_some_and(|p| p.x > origin.x + 90.0 && p.x < origin.x + w - 290.0);
    state.advance(dt_seconds, hovered_canvas);
    let layout = state.layout(w, h);
    let rail = origin.x + layout.rail;
    let inspector_x = origin.x + w - layout.inspector;
    rect(ui, outer, BG, 0);
    rect(
        ui,
        Rect::from_min_max(origin, Pos2::new(rail, origin.y + h)),
        PANEL,
        0,
    );
    line(ui, rail, origin.y, 0.0, OUTLINE);
    text(
        ui,
        Pos2::new(origin.x + layout.rail * 0.5, origin.y + 37.0),
        "b",
        34.0,
        CYAN,
        Align2::CENTER_CENTER,
    );
    text(
        ui,
        Pos2::new(rail + 28.0, origin.y + 32.0),
        "BLOB / STUDIO",
        14.0,
        TEXT,
        Align2::LEFT_CENTER,
    );
    text(
        ui,
        Pos2::new(rail + 28.0, origin.y + 55.0),
        "NATIVE 2D RENDER ENGINE",
        10.0,
        MUTED,
        Align2::LEFT_CENTER,
    );
    text(
        ui,
        Pos2::new(inspector_x - 120.0, origin.y + 32.0),
        "VULKAN   ·   WAYLAND",
        11.0,
        CYAN,
        Align2::RIGHT_CENTER,
    );
    line(ui, rail, origin.y + 78.0, w - layout.rail, OUTLINE);
    for (i, glyph) in ["◇", "◎", "▣"].iter().enumerate() {
        let top = origin.y + 112.0 + (i as f32) * 64.0;
        let r = Rect::from_min_size(
            Pos2::new(origin.x + 12.0, top),
            Vec2::new(layout.rail - 24.0, 48.0),
        );
        let id = match i {
            0 => "rail-scene",
            1 => "rail-material",
            _ => "rail-motion",
        };
        if button(ui, id, r, glyph, state.selected == i) {
            state.dispatch(UiAction::SelectSurface(i));
        }
    }
    text(
        ui,
        Pos2::new(origin.x + layout.rail / 2.0, origin.y + h - 35.0),
        "v0.1",
        11.0,
        MUTED,
        Align2::CENTER_CENTER,
    );

    let canvas_top = origin.y + 78.0;
    let canvas_bottom = origin.y + h - 115.0;
    let canvas = Rect::from_min_max(
        Pos2::new(rail, canvas_top),
        Pos2::new(inspector_x, canvas_bottom),
    );
    ui.painter().rect_stroke(
        canvas,
        egui::CornerRadius::ZERO,
        Stroke::new(1.0, OUTLINE),
        egui::StrokeKind::Inside,
    );
    for step in 1..8 {
        let y = canvas.top() + step as f32 * canvas.height() / 8.0;
        line(
            ui,
            canvas.left() + 20.0,
            y,
            canvas.width() - 40.0,
            Color32::from_rgba_unmultiplied(86, 120, 132, 12),
        );
    }
    let center = Pos2::new(canvas.center().x, canvas.center().y - 12.0);
    let radius = canvas.width().min(canvas.height()).max(120.0) * 0.20;
    blob(
        ui,
        center,
        radius,
        state.phase,
        state.hover.value,
        state.selected,
    );
    text(
        ui,
        Pos2::new(canvas.left() + 26.0, canvas.top() + 28.0),
        "SCENE 01  /  LIVE",
        11.0,
        CYAN,
        Align2::LEFT_CENTER,
    );
    text(
        ui,
        Pos2::new(canvas.left() + 26.0, canvas.top() + 49.0),
        "Organic surface • interactive",
        12.0,
        MUTED,
        Align2::LEFT_CENTER,
    );
    text(
        ui,
        Pos2::new(canvas.left() + 26.0, canvas.bottom() - 27.0),
        "MOVE POINTER   /   CLICK RAIL   /   SPACE PAUSES",
        10.0,
        MUTED,
        Align2::LEFT_CENTER,
    );

    if layout.inspector >= 290.0 {
        let panel = Rect::from_min_max(
            Pos2::new(inspector_x, canvas_top),
            Pos2::new(origin.x + w, origin.y + h),
        );
        rect(ui, panel, PANEL, 0);
        let left = inspector_x + 25.0;
        text(
            ui,
            Pos2::new(left, canvas_top + 33.0),
            "INSPECTOR",
            13.0,
            TEXT,
            Align2::LEFT_CENTER,
        );
        text(
            ui,
            Pos2::new(left, canvas_top + 61.0),
            "SURFACE / PROPERTIES",
            10.0,
            MUTED,
            Align2::LEFT_CENTER,
        );
        line(
            ui,
            inspector_x + 1.0,
            canvas_top + 82.0,
            layout.inspector - 2.0,
            OUTLINE,
        );
        text(
            ui,
            Pos2::new(left, canvas_top + 114.0),
            "Motion system",
            14.0,
            TEXT,
            Align2::LEFT_CENTER,
        );
        let a = Rect::from_min_size(
            Pos2::new(left, canvas_top + 137.0),
            Vec2::new(layout.inspector - 50.0, 39.0),
        );
        if button(
            ui,
            "motion-toggle",
            a,
            if state.motion_on {
                "ANIMATION  ·  ON"
            } else {
                "ANIMATION  ·  OFF"
            },
            state.motion_on,
        ) {
            state.dispatch(UiAction::ToggleMotion);
        }
        let b = Rect::from_min_size(
            Pos2::new(left, canvas_top + 198.0),
            Vec2::new(layout.inspector - 50.0, 39.0),
        );
        if button(
            ui,
            "reduced-motion-toggle",
            b,
            if state.reduced_motion {
                "REDUCED MOTION  ·  ON"
            } else {
                "REDUCED MOTION  ·  OFF"
            },
            state.reduced_motion,
        ) {
            state.dispatch(UiAction::ToggleReducedMotion);
        }
        text(
            ui,
            Pos2::new(left, canvas_top + 279.0),
            "TIMELINE",
            11.0,
            MUTED,
            Align2::LEFT_CENTER,
        );
        let bar = Rect::from_min_size(
            Pos2::new(left, canvas_top + 297.0),
            Vec2::new(layout.inspector - 50.0, 5.0),
        );
        rect(ui, bar, OUTLINE, 3);
        let marker = Pos2::new(bar.left() + bar.width() * state.phase, bar.center().y);
        ui.painter().circle_filled(marker, 7.0, CYAN);
        text(
            ui,
            Pos2::new(left, canvas_top + 342.0),
            &format!("SCENE REV  {:03}", state.ui_revision),
            11.0,
            CYAN,
            Align2::LEFT_CENTER,
        );
        text(
            ui,
            Pos2::new(left, canvas_top + 366.0),
            &format!("SUBMITTED  {:05}", frames),
            11.0,
            MUTED,
            Align2::LEFT_CENTER,
        );
    }
    let bottom = Rect::from_min_max(
        Pos2::new(rail, canvas_bottom),
        Pos2::new(inspector_x, origin.y + h),
    );
    rect(ui, bottom, PANEL, 0);
    text(
        ui,
        Pos2::new(rail + 27.0, canvas_bottom + 30.0),
        "COMPOSITION",
        11.0,
        CYAN,
        Align2::LEFT_CENTER,
    );
    text(
        ui,
        Pos2::new(rail + 27.0, canvas_bottom + 56.0),
        "Responsive  /  GPU geometry  /  spring transitions",
        13.0,
        TEXT,
        Align2::LEFT_CENTER,
    );
    let controls_top = canvas_bottom + 70.0;
    for (i, label) in ["CANVAS", "MATERIAL", "MOTION"].iter().enumerate() {
        let r = Rect::from_min_size(
            Pos2::new(rail + 26.0 + i as f32 * 127.0, controls_top),
            Vec2::new(116.0, 30.0),
        );
        let id = match i {
            0 => "tab-canvas",
            1 => "tab-material",
            _ => "tab-motion",
        };
        if button(ui, id, r, label, state.selected == i) {
            state.dispatch(UiAction::SelectSurface(i));
        }
    }
    if layout.inspector < 1.0 && !layout.compact {
        text(
            ui,
            Pos2::new(origin.x + w - 15.0, origin.y + 98.0),
            "INSPECTOR HIDDEN",
            10.0,
            MUTED,
            Align2::RIGHT_CENTER,
        );
    }
    if !layout.compact {
        let toggle_rect = Rect::from_min_size(
            Pos2::new(inspector_x - 95.0, origin.y + 19.0),
            Vec2::new(82.0, 36.0),
        );
        if button(
            ui,
            "inspector-toggle",
            toggle_rect,
            if state.inspector_open {
                "HIDE  ›"
            } else {
                "SHOW  ‹"
            },
            state.inspector_open,
        ) {
            state.dispatch(UiAction::ToggleInspector);
        }
    }
    let focus_rect = Rect::from_center_size(
        Pos2::new(center.x, center.y + radius * 1.4),
        Vec2::new(155.0, 35.0),
    );
    if button(
        ui,
        "canvas-focus",
        focus_rect,
        if state.focused {
            "FOCUS ACTIVE"
        } else {
            "INTERACT  ↗"
        },
        state.focused,
    ) {
        state.dispatch(UiAction::ToggleFocus);
    }
    if state.focused {
        ui.painter()
            .circle_stroke(center, radius * 1.2, Stroke::new(2.0, ORANGE));
    }
    if state.active_motion() {
        ui.ctx()
            .request_repaint_after(std::time::Duration::from_millis(16));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn contour_is_finite_and_animated() {
        let center = Pos2::new(400.0, 300.0);
        let a = organic_vertices(center, 100.0, 0.0, 64);
        let b = organic_vertices(center, 100.0, 0.25, 64);
        assert_eq!(a.len(), 64);
        assert_eq!(b.len(), 64);
        assert_ne!(a, b);
        assert!(a.iter().all(|p| p.x.is_finite() && p.y.is_finite()));
    }
}
