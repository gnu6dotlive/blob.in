//! 01F private-WestON-only quadratic/cubic Bézier witness.
//! The CPU produces deterministic line segments; the EXISTING 01E GPU
//! capsule shader paints those segments, without a new renderer or device.
use blobin_ui_core::layout::Rect;
use blobin_ui_core::SurfaceId;
use blobin_ui_scene::bezier::{stroke_bezier, BezierCurve};
use blobin_ui_scene::strokes::Point2;
use blobin_ui_scene::{DisplayList, Rgba8};

pub const TOLERANCE_LOGICAL_PX: f32 = 0.75;
pub fn fixture() -> DisplayList {
    let mut current = crate::ac01d_stress::fixture();
    current.surface = SurfaceId(0x01F0);
    let quad = BezierCurve::Quadratic([
        Point2::new(480., 140.),
        Point2::new(515., 220.),
        Point2::new(550., 140.),
    ]);
    let cubic = BezierCurve::Cubic([
        Point2::new(575., 145.),
        Point2::new(590., 225.),
        Point2::new(640., 225.),
        Point2::new(655., 145.),
    ]);
    let clip = Rect::new(0., 0., 1280., 800.);
    let green = Rgba8::new(20, 230, 150, 255);
    let mut strokes = stroke_bezier(
        current.source_node,
        quad,
        7.,
        clip,
        green,
        TOLERANCE_LOGICAL_PX,
        55,
    )
    .expect("quadratic bounded");
    let cubic_segments = stroke_bezier(
        current.source_node,
        cubic,
        7.,
        clip,
        green,
        TOLERANCE_LOGICAL_PX,
        55 - strokes.len(),
    )
    .expect("cubic bounded");
    strokes.extend(cubic_segments);
    assert!(strokes.len() > 4 && strokes.len() <= 55, "bounded fixture");
    current.commands.truncate(55 - strokes.len());
    current.strokes = strokes;
    assert_eq!(current.commands.len() + current.strokes.len(), 55);
    current
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn two_true_curves_generate_strokes_and_preserve_64_total_commands() {
        let witness = fixture();
        assert!(witness.strokes.len() > 8);
        assert!(witness.commands.len() > 0);
        assert_eq!(witness.commands.len() + witness.strokes.len() + 9, 64);
        assert_eq!(witness.source_ui_revision, 1);
        assert_eq!(witness.surface, SurfaceId(0x01F0));
        assert_eq!(witness.strokes[0].start, Point2::new(480., 140.));
        assert_eq!(witness.strokes.last().unwrap().end, Point2::new(655., 145.));
        assert!(witness
            .strokes
            .iter()
            .all(|s| s.source == witness.source_node && s.width == 7.));
    }
}
