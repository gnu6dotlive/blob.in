//! GNU6/Gnosix visual tokens (from gnosix `gnos-ux-gpui/src/product_design.rs`)
//! applied to egui.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use egui::{Color32, CornerRadius, FontData, FontDefinitions, FontFamily, Stroke, Style, Visuals};

/// Whether a loaded font covers ∪ ∩ − ✕; otherwise the UI uses ASCII labels.
pub static MATH_GLYPHS: AtomicBool = AtomicBool::new(false);

const UI_FONTS: [&str; 2] = ["/usr/share/fonts/noto/NotoSans-Regular.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf"];
const MATH_FONT: &str = "/usr/share/fonts/TTF/DejaVuSans.ttf";

/// System fonts read from disk (local files only); egui's bundled fonts remain the last fallback.
fn fonts() -> FontDefinitions {
    let mut defs = FontDefinitions::default();
    let mut chain = Vec::new();
    for path in UI_FONTS {
        if chain.iter().any(|(p, _)| *p == path) {
            continue;
        }
        match std::fs::read(path) {
            Ok(bytes) => {
                defs.font_data.insert(path.into(), Arc::new(FontData::from_owned(bytes)));
                chain.push((path, ()));
                if path == MATH_FONT {
                    MATH_GLYPHS.store(true, Ordering::Relaxed);
                }
            }
            Err(e) => log::info!("font {path} unavailable ({e}); using bundled fallback"),
        }
    }
    let prop = defs.families.entry(FontFamily::Proportional).or_default();
    for (i, (path, _)) in chain.iter().enumerate() {
        prop.insert(i, (*path).into());
    }
    defs
}

pub const CANVAS: Color32 = Color32::from_rgb(0x0d, 0x12, 0x18);
pub const PANEL: Color32 = Color32::from_rgb(0x17, 0x20, 0x29);
pub const PANEL_ELEVATED: Color32 = Color32::from_rgb(0x16, 0x27, 0x33);
pub const CONTROL: Color32 = Color32::from_rgb(0x16, 0x27, 0x33);
pub const CONTROL_HOVER: Color32 = Color32::from_rgb(0x1c, 0x34, 0x45);
pub const CONTROL_PRESSED: Color32 = Color32::from_rgb(0x24, 0x46, 0x5a);
pub const CONTROL_SELECTED: Color32 = Color32::from_rgb(0x31, 0x5f, 0x79);
pub const BORDER: Color32 = Color32::from_rgba_premultiplied(0x33, 0x33, 0x33, 0x33);
pub const TEXT: Color32 = Color32::from_rgb(0xd8, 0xe9, 0xef);
pub const TEXT_STRONG: Color32 = Color32::WHITE;
pub const TEXT_MUTED: Color32 = Color32::from_rgb(0xa4, 0xb7, 0xc0);
pub const ACCENT: Color32 = Color32::from_rgb(0x8b, 0xdd, 0xe7);
pub const DANGER: Color32 = Color32::from_rgb(0xe4, 0x7d, 0x7d);
pub const WARNING: Color32 = Color32::from_rgb(0xe7, 0xbf, 0x72);

pub const RADIUS_CONTROL: u8 = 10;
pub const RADIUS_PANEL: u8 = 14;

pub fn apply(ctx: &egui::Context) {
    ctx.set_fonts(fonts());
    let mut style = Style::default();
    let mut v = Visuals::dark();
    v.override_text_color = Some(TEXT);
    v.panel_fill = PANEL;
    v.window_fill = PANEL_ELEVATED;
    v.window_stroke = Stroke::new(1.0, BORDER);
    v.window_corner_radius = CornerRadius::same(RADIUS_PANEL);
    v.menu_corner_radius = CornerRadius::same(RADIUS_CONTROL);
    v.extreme_bg_color = CANVAS;
    v.faint_bg_color = PANEL_ELEVATED;
    v.hyperlink_color = ACCENT;
    v.warn_fg_color = WARNING;
    v.error_fg_color = DANGER;
    v.selection.bg_fill = CONTROL_SELECTED;
    v.selection.stroke = Stroke::new(1.0, ACCENT);
    let r = CornerRadius::same(RADIUS_CONTROL);
    let w = &mut v.widgets;
    w.noninteractive.bg_fill = PANEL;
    w.noninteractive.weak_bg_fill = PANEL;
    w.noninteractive.bg_stroke = Stroke::new(1.0, BORDER);
    w.noninteractive.fg_stroke = Stroke::new(1.0, TEXT);
    for (s, fill) in [(&mut w.inactive, CONTROL), (&mut w.hovered, CONTROL_HOVER), (&mut w.active, CONTROL_PRESSED), (&mut w.open, CONTROL_HOVER)] {
        s.bg_fill = fill;
        s.weak_bg_fill = fill;
        s.corner_radius = r;
        s.fg_stroke = Stroke::new(1.0, TEXT_STRONG);
    }
    w.inactive.bg_stroke = Stroke::new(1.0, BORDER);
    w.hovered.bg_stroke = Stroke::new(1.0, ACCENT);
    w.active.bg_stroke = Stroke::new(1.0, ACCENT);
    style.visuals = v;
    style.spacing.item_spacing = egui::vec2(8.0, 8.0);
    style.spacing.button_padding = egui::vec2(10.0, 5.0);
    style.spacing.slider_width = 120.0;
    ctx.set_global_style(style);
}
