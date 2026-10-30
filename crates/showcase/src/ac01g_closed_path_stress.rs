//! 01G private-WestON-only two closed *convex* paths.
//! Exactly 55 lab commands + 9 original real UI commands = 64.
//! The production renderer uses its existing one wgpu pass and its
//! persistent uniform arena, with no additional GPU device or surface.
use blobin_ui_core::layout::Rect;
use blobin_ui_core::SurfaceId;
use blobin_ui_scene::fills::{fill_convex_path, stroke_closed_convex_path};
use blobin_ui_scene::strokes::Point2;
use blobin_ui_scene::{DisplayList, Rgba8};

pub fn fixture() -> DisplayList {
    let mut display = crate::ac01f_bezier_stress::fixture();
    display.surface = SurfaceId(0x01A7);
    display.commands.truncate(17); // red rectangles, independently verified
    let clip = Rect::new(0., 0., 1280., 800.);
    let square = [
        Point2::new(700., 110.),
        Point2::new(770., 110.),
        Point2::new(770., 180.),
        Point2::new(700., 180.),
    ];
    let triangle = [
        Point2::new(830., 115.),
        Point2::new(900., 175.),
        Point2::new(830., 185.),
    ];
    let square_fill = Rgba8::new(30, 110, 230, 255);
    let triangle_fill = Rgba8::new(200, 60, 180, 255);
    let outline = Rgba8::new(250, 180, 40, 255);
    display.triangles.extend(
        fill_convex_path(display.source_node, &square, clip, square_fill).expect("01G square fill"),
    );
    display.triangles.extend(
        fill_convex_path(display.source_node, &triangle, clip, triangle_fill)
            .expect("01G triangle fill"),
    );
    display.strokes.extend(
        stroke_closed_convex_path(display.source_node, &square, 8., clip, outline)
            .expect("01G closed square"),
    );
    display.strokes.extend(
        stroke_closed_convex_path(display.source_node, &triangle, 8., clip, outline)
            .expect("01G closed triangle"),
    );
    assert_eq!(display.commands.len(), 17);
    assert_eq!(display.triangles.len(), 3);
    assert_eq!(display.strokes.len(), 35); // 28 Bézier + 7 closed
    assert_eq!(
        display.commands.len() + display.triangles.len() + display.strokes.len(),
        55
    );
    display
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn two_real_convex_fills_and_closed_round_outlines_fit_gpu_budget() {
        let list = fixture();
        assert_eq!(list.surface, SurfaceId(0x01A7));
        assert_eq!(list.commands.len(), 17);
        assert_eq!(list.triangles.len(), 3);
        assert_eq!(list.strokes.len(), 35);
        assert_eq!(list.triangles[0].vertices[0], Point2::new(700., 110.));
        assert_eq!(list.strokes[28].start, Point2::new(700., 110.));
        assert_eq!(list.strokes[31].end, Point2::new(700., 110.));
        assert_eq!(list.strokes[34].end, Point2::new(830., 115.));
        assert_eq!(
            list.commands.len() + list.triangles.len() + list.strokes.len() + 9,
            64
        );
        assert!(list.triangles.iter().all(|v| v.source == list.source_node));
    }
}
