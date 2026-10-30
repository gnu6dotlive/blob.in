//! 01I bounded two-hole rectangular EvenOdd witness, private Weston only.
use blobin_ui_core::{layout::Rect, SurfaceId};
use blobin_ui_scene::concave::fill_rectangular_even_odd;
use blobin_ui_scene::{DisplayList, Rgba8};
pub fn fixture() -> DisplayList {
    let mut list = crate::ac01d_stress::fixture();
    list.surface = SurfaceId(0x01A9);
    list.commands.clear();
    list.triangles = fill_rectangular_even_odd(
        list.source_node,
        Rect::new(700.25, 110.25, 260., 150.),
        &[
            Rect::new(745.25, 145.25, 40., 50.),
            Rect::new(840.25, 165.25, 50., 55.),
        ],
        Rect::new(0., 0., 1280., 800.),
        Rgba8::new(180, 80, 210, 255),
    )
    .expect("01I bounded two-hole tessellation");
    assert_eq!(list.triangles.len(), 42);
    list
}
#[cfg(test)]
mod tests {
    #[test]
    fn limits_and_identity() {
        let s = super::fixture();
        assert_eq!(s.triangles.len(), 42);
        assert_eq!(s.surface.0, 0x01A9);
        assert!(s.triangles.iter().all(|t| t.source == s.source_node));
        assert_eq!(s.triangles.len() + 9, 51);
    }
}
