//! 01E private-Weston-only fixture: 51 existing fill rectangles plus four
//! genuine vector stroke segments, exactly 55 + 9 = 64 GPU commands.
//! This is test instrumentation, not an editor feature or a new SDF renderer.
use blobin_ui_core::SurfaceId;
use blobin_ui_scene::strokes::{stroke_polyline, Point2};
use blobin_ui_scene::{DisplayList, Rgba8};

pub fn fixture() -> DisplayList {
    let mut current = crate::ac01d_stress::fixture();
    current.commands.truncate(51);
    current.surface = SurfaceId(0x01E0);
    let path = [
        Point2::new(480., 140.),
        Point2::new(550., 140.),
        Point2::new(550., 200.),
        Point2::new(620., 200.),
        Point2::new(620., 140.),
    ];
    current.strokes = stroke_polyline(
        current.source_node,
        &path,
        8.,
        blobin_ui_core::layout::Rect::new(0., 0., 1280., 800.),
        Rgba8::new(20, 230, 150, 255),
    )
    .expect("01E bounded first-party strokes");
    current
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn witness_is_51_rects_and_4_true_strokes_not_rect_fakes() {
        let a = fixture();
        assert_eq!(a.commands.len(), 51);
        assert_eq!(a.strokes.len(), 4);
        assert_eq!(a.commands.len() + a.strokes.len(), 55);
        assert!(a
            .strokes
            .iter()
            .all(|s| s.width == 8. && s.source == a.source_node));
        assert_eq!(a.strokes[0].start, Point2::new(480., 140.));
        assert_eq!(a.strokes[3].end, Point2::new(620., 140.));
    }
}
