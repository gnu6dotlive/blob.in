//! 01D laboratory-only 55-corner stress overlay for the REAL production wgpu
//! adapter. This is not a new product component or an alternate renderer.
use blobin_ui_core::layout::Rect;
use blobin_ui_core::{NodeId, SurfaceId};
use blobin_ui_scene::{DisplayList, FillRoundedRect, Rgba8};

pub fn fixture() -> DisplayList {
    let source = NodeId {
        slot: 1,
        generation: 1,
    };
    let clip = Rect::new(0., 0., 1280., 800.);
    let mut commands = Vec::with_capacity(55);
    for i in 0..55 {
        let col = (i % 11) as f32;
        let row = (i / 11) as f32;
        commands.push(FillRoundedRect {
            source,
            rect: Rect::new(120. + 24. * col, 105. + 24. * row, 18., 18.),
            clip,
            color: Rgba8::new(224, 70, 130, 255),
            radius: 3.,
        });
    }
    DisplayList {
        source_ui_revision: 1,
        surface: SurfaceId(0x01D0),
        layout_epoch: 1,
        source_node: source,
        commands,
        strokes: vec![],
        triangles: vec![],
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn first_party_stress_fixture_uses_55_visible_commands_with_one_identity() {
        let s = fixture();
        assert_eq!(s.commands.len(), 55);
        assert!(s
            .commands
            .iter()
            .all(|c| c.source == s.source_node && c.rect.width == 18.));
        assert_ne!(s.commands[0].rect, s.commands[54].rect);
    }
}
