//! UI01A/01B: legacy action adapter for native toggle drawing.
//! Shared G02/G03 control layout lives in ac01b_control_layout, rather than
//! duplicating a second independent tree/layout implementation per widget.
use crate::ac01b_control_layout::ControlLayoutHost;
use blobin_ui_core::layout::{Rect, Size};
use blobin_ui_core::{NodeId, SurfaceId};
use blobin_ui_scene::{DisplayList, Rgba8, TogglePalette, ToggleVisualState};

pub const SIZE: (f32, f32) = (52.0, 26.0);
const SURFACE: SurfaceId = SurfaceId(0x010A);
pub struct NativeToggleHost {
    core: ControlLayoutHost,
    pub failures: u64,
}
impl NativeToggleHost {
    pub fn new() -> Result<Self, String> {
        Ok(Self {
            core: ControlLayoutHost::new(SURFACE, "Contours de contrôle: activés", SIZE)?,
            failures: 0,
        })
    }
    pub fn display(&self) -> Option<&DisplayList> {
        self.core.display()
    }
    pub fn clear(&mut self) {
        self.core.clear()
    }
    pub fn current_revision(&self) -> u64 {
        self.core.revision()
    }
    pub fn control_id(&self) -> NodeId {
        self.core.id()
    }
    #[allow(clippy::too_many_arguments)]
    pub fn update(
        &mut self,
        size: Size,
        scale: f32,
        bounds: Rect,
        clip: Rect,
        state: ToggleVisualState,
        colors: TogglePalette,
    ) -> Result<Option<&DisplayList>, String> {
        self.core.update(
            size,
            scale,
            bounds,
            clip,
            if state.checked {
                "Contours de contrôle: activés"
            } else {
                "Contours de contrôle: désactivés"
            },
            state.enabled,
            move |tree, styles, layout, viewport, id, clip| {
                blobin_ui_scene::toggle(tree, styles, layout, viewport, id, state, colors, clip)
            },
        )
    }
}
pub fn color(r: u8, g: u8, b: u8, a: u8) -> Rgba8 {
    Rgba8::new(r, g, b, a)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn palette() -> TogglePalette {
        TogglePalette {
            track_off: color(20, 30, 40, 255),
            track_on: color(20, 190, 200, 255),
            border: color(120, 120, 120, 255),
            thumb: color(240, 240, 240, 255),
            thumb_disabled: color(100, 100, 100, 255),
            focus: color(255, 180, 50, 255),
        }
    }
    fn update(h: &mut NativeToggleHost, on: bool, x: f32) -> Result<Option<&DisplayList>, String> {
        h.update(
            Size::new(640., 480.),
            1.5,
            Rect::new(x, 120., SIZE.0, SIZE.1),
            Rect::new(x, 120., SIZE.0, SIZE.1),
            ToggleVisualState {
                checked: on,
                hovered: false,
                focused: false,
                enabled: true,
            },
            palette(),
        )
    }
    #[test]
    fn stable_node_and_layout_state_after_toggle() {
        let mut h = NativeToggleHost::new().unwrap();
        let id = h.control_id();
        let first = update(&mut h, true, 300.).unwrap().unwrap().clone();
        let revision = h.current_revision();
        let second = update(&mut h, true, 300.).unwrap().unwrap().clone();
        assert_eq!(h.control_id(), id);
        assert_eq!(h.current_revision(), revision);
        assert_eq!(first, second);
        let off = update(&mut h, false, 300.).unwrap().unwrap().clone();
        assert_ne!(off.commands[2].rect, first.commands[2].rect);
        assert_eq!(h.control_id(), id);
        assert!(h.current_revision() > revision);
    }
    #[test]
    fn physical_clip_tracks_real_ui_rect() {
        let mut h = NativeToggleHost::new().unwrap();
        let list = update(&mut h, false, 330.).unwrap().unwrap();
        assert_eq!(list.commands[0].rect, Rect::new(330., 120., 52., 26.));
        assert_eq!(list.commands[0].clip, Rect::new(330., 120., 52., 26.));
    }
    #[test]
    fn bad_geometry_fails_closed_not_reusing_old_list() {
        let mut h = NativeToggleHost::new().unwrap();
        update(&mut h, true, 320.).unwrap();
        assert!(h.display().is_some());
        assert!(update(&mut h, true, 650.).is_err());
        assert!(h.display().is_none());
    }
    #[test]
    fn geometry_epoch_updates_without_recycling_id() {
        let mut h = NativeToggleHost::new().unwrap();
        let id = h.control_id();
        let initial = update(&mut h, true, 300.).unwrap().unwrap().layout_epoch;
        let list = h
            .update(
                Size::new(720., 480.),
                1.5,
                Rect::new(370., 120., 52., 26.),
                Rect::new(370., 120., 52., 26.),
                ToggleVisualState {
                    checked: true,
                    hovered: false,
                    focused: false,
                    enabled: true,
                },
                palette(),
            )
            .unwrap()
            .unwrap();
        assert!(list.layout_epoch > initial);
        assert_eq!(h.control_id(), id);
    }
}
