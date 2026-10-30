//! 01B native-selection button in the real Visualization inspector.
//! The existing egui Response owns action/focus/text; this owns G02/G03
//! paint identity only; no runtime rendering policy moves here.
use crate::ac01b_control_layout::ControlLayoutHost;
use blobin_ui_core::layout::{Rect, Size};
use blobin_ui_core::{NodeId, SurfaceId};
use blobin_ui_scene::{ActionPalette, ActionVisualState, DisplayList};
pub const SIZE: (f32, f32) = (76.0, 26.0);
const SURFACE: SurfaceId = SurfaceId(0x010B);
pub struct NativeActionHost {
    core: ControlLayoutHost,
}
impl NativeActionHost {
    pub fn new() -> Result<Self, String> {
        Self::with_identity(SURFACE, "Distance: inactive", SIZE)
    }
    pub fn with_identity(
        surface: SurfaceId,
        label: &'static str,
        size: (f32, f32),
    ) -> Result<Self, String> {
        Ok(Self {
            core: ControlLayoutHost::new(surface, label, size)?,
        })
    }
    pub fn display(&self) -> Option<&DisplayList> {
        self.core.display()
    }
    pub fn clear(&mut self) {
        self.core.clear()
    }
    pub fn control_id(&self) -> NodeId {
        self.core.id()
    }
    pub fn current_revision(&self) -> u64 {
        self.core.revision()
    }
    pub fn failures(&self) -> u64 {
        self.core.failures
    }
    pub fn failure(&mut self) {
        self.core.failures += 1
    }
    #[allow(clippy::too_many_arguments)]
    pub fn update(
        &mut self,
        size: Size,
        scale: f32,
        bounds: Rect,
        clip: Rect,
        state: ActionVisualState,
        palette: ActionPalette,
    ) -> Result<Option<&DisplayList>, String> {
        self.core.update(
            size,
            scale,
            bounds,
            clip,
            if state.selected {
                "Distance: active"
            } else {
                "Distance: inactive"
            },
            state.enabled,
            move |tree, styles, layout, vp, id, clip| {
                blobin_ui_scene::action_button(tree, styles, layout, vp, id, state, palette, clip)
            },
        )
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use blobin_ui_scene::Rgba8;
    fn colors() -> ActionPalette {
        ActionPalette {
            idle: Rgba8::new(10, 11, 12, 255),
            selected: Rgba8::new(30, 31, 32, 255),
            hover: Rgba8::new(40, 41, 42, 255),
            pressed: Rgba8::new(50, 51, 52, 255),
            border: Rgba8::new(60, 61, 62, 255),
            focus: Rgba8::new(70, 71, 72, 255),
            disabled: Rgba8::new(80, 81, 82, 255),
            selected_marker: Rgba8::new(255, 100, 0, 255),
        }
    }
    fn render(h: &mut NativeActionHost, selected: bool) -> DisplayList {
        h.update(
            Size::new(1280., 800.),
            1.0,
            Rect::new(946., 320., SIZE.0, SIZE.1),
            Rect::new(932., 0., 348., 800.),
            ActionVisualState {
                selected,
                hovered: false,
                focused: false,
                pressed: false,
                enabled: true,
            },
            colors(),
        )
        .unwrap()
        .unwrap()
        .clone()
    }
    #[test]
    fn selection_changes_only_visual_identity_and_keeps_node() {
        let mut h = NativeActionHost::new().unwrap();
        let id = h.control_id();
        let before = render(&mut h, false);
        let rev = h.current_revision();
        assert_eq!(render(&mut h, false), before);
        assert_eq!(h.current_revision(), rev);
        let after = render(&mut h, true);
        assert_eq!(after.source_node, id);
        assert_ne!(before.commands[1].color, after.commands[1].color);
        assert_ne!(before.commands[2].color, after.commands[2].color);
        assert!(h.current_revision() > rev);
    }
}
