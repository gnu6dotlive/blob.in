//! Native blob.in interface primitives: GPU-tessellated egui geometry.
//! Stable IDs, typed actions and responsive canvas (no pre-rendered static images).
use egui::{Align2, Color32, FontId, Pos2, Rect, Sense, Stroke, Ui, Vec2};
use crate::ui_motion::{UiAction, UiRuntime};

const BG: Color32 = Color32::from_rgb(8, 13, 23);
const PANEL: Color32 = Color32::from_rgb(15, 24, 36);
const PANEL_HI: Color32 = Color32::from_rgb(22, 35, 49);
const TEXT: Color32 = Color32::from_rgb(234, 242, 245);
const MUTED: Color32 = Color32::from_rgb(135, 155, 173);
const CYAN: Color32 = Color32::from_rgb(102, 229, 217);
const ORANGE: Color32 = Color32::from_rgb(245, 162, 108);
const OUTLINE: Color32 = Color32::from_rgb(46, 67, 78);

fn rect(ui: &Ui, r: Rect, fill: Color32, radius: u8) {
    ui.painter().rect_filled(r, egui::CornerRadius::same(radius), fill);
}
fn text(ui: &Ui, at: Pos2, label: &str, size: f32, color: Color32, align: Align2) {
    ui.painter().text(at, align, label, FontId::proportional(size), color);
}
fn line(ui: &Ui, x: f32, y: f32, w: f32, color: Color32) {
    ui.painter().line_segment([Pos2::new(x, y), Pos2::new(x + w, y)], Stroke::new(1.0, color));
}
fn button(ui: &mut Ui, id: &'static str, r: Rect, label: &str, active: bool) -> bool {
    let response = ui.interact(r, egui::Id::new(id), Sense::click());
    let fill = if response.hovered() { PANEL_HI }
        else if active { Color32::from_rgb(22, 56, 63) } else { PANEL };
    rect(ui, r, fill, 11);
    ui.painter().rect_stroke(r, egui::CornerRadius::same(11),
        Stroke::new(1.0, if active { CYAN } else { OUTLINE }), egui::StrokeKind::Inside);
    text(ui, r.center(), label, 13.0,
        if active { CYAN } else { TEXT }, Align2::CENTER_CENTER);
    response.clicked()
}

/// Animate a real organic contour, rather than a static texture sprite.
pub fn organic_vertices(center: Pos2, radius: f32, phase: f32, points: usize) -> Vec<Pos2> {
    (0..points).map(|i| {
        let a = std::f32::consts::TAU * (i as f32 / points as f32);
        let wobble = (a * 3.0 + phase * std::f32::consts::TAU).sin() * 0.075
            + (a * 5.0 - phase * std::f32::consts::TAU * 0.7).cos() * 0.035;
        let r = radius * (1.0 + wobble);
        Pos2::new(center.x + r * a.cos(), center.y + r * a.sin())
    }).collect()
}

fn blob(ui: &Ui, center: Pos2, radius: f32, phase: f32, hover: f32, selected: usize) {
    for i in (0..9).rev() {
        let r = radius * (1.10 + i as f32 * 0.105);
        let alpha = 4 + (9-i)*2;
        let hue = if selected == 1 { ORANGE } else { CYAN };
        let fill = Color32::from_rgba_unmultiplied(hue.r(), hue.g(), hue.b(), alpha);
        ui.painter().add(egui::Shape::convex_polygon(
            organic_vertices(center, r, phase + i as f32 * 0.03, 96),
            fill, Stroke::NONE,
        ));
    }
    let main = if selected == 1 { ORANGE } else { CYAN };
    ui.painter().add(egui::Shape::convex_polygon(
        organic_vertices(center, radius * (1.0 + hover * 0.06), phase, 128),
        Color32::from_rgb(28, 94, 104), Stroke::new(1.2, main),
    ));
    ui.painter().circle_filled(Pos2::new(center.x - radius*0.22, center.y-radius*0.25),
        radius*0.32, Color32::from_rgba_unmultiplied(130,244,230,38));
    ui.painter().circle_stroke(center, radius*0.65, Stroke::new(1.0,
        Color32::from_rgba_unmultiplied(210,255,245,70)));
    text(ui, center, "blob.in", 32.0, TEXT, Align2::CENTER_CENTER);
}
