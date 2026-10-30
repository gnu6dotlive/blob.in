//! 01H: private-only L-shaped concave fill and axis-aligned rectangular hole.
use blobin_ui_core::layout::Rect;
use blobin_ui_core::SurfaceId;
use blobin_ui_scene::concave::{fill_rectangular_frame, fill_simple_polygon};
use blobin_ui_scene::strokes::Point2;
use blobin_ui_scene::{DisplayList, Rgba8};
pub fn fixture() -> DisplayList {
    let mut list = crate::ac01f_bezier_stress::fixture();
    list.surface = SurfaceId(0x01A8);
    list.commands.truncate(5);
    let id = list.source_node;
    let clip = Rect::new(0., 0., 1280., 800.);
    let concave = [
        Point2::new(680., 110.),
        Point2::new(800., 110.),
        Point2::new(800., 145.),
        Point2::new(735., 145.),
        Point2::new(735., 220.),
        Point2::new(680., 220.),
    ];
    list.triangles.extend(
        fill_simple_polygon(id, &concave, clip, Rgba8::new(40, 130, 230, 255))
            .expect("01H ear clipping"),
    );
    let frame = fill_rectangular_frame(
        id,
        Rect::new(845., 105., 150., 140.),
        Rect::new(885., 145., 70., 60.),
        clip,
        Rgba8::new(200, 65, 165, 255),
    )
    .expect("01H rectangular hole");
    list.triangles.extend(frame);
    assert_eq!(list.triangles.len(), 12);
    assert_eq!(list.strokes.len(), 28);
    assert_eq!(list.commands.len(), 5);
    assert_eq!(
        list.commands.len() + list.strokes.len() + list.triangles.len(),
        45
    );
    list
}
#[cfg(test)]
mod tests {
    #[test]
    fn shapes_are_nonempty_with_a_real_hole_and_bounded_gpu_budget() {
        let list = super::fixture();
        assert_eq!(list.triangles.len(), 12);
        assert_eq!(
            list.triangles.len() + list.commands.len() + list.strokes.len() + 9,
            54
        );
    }
}
