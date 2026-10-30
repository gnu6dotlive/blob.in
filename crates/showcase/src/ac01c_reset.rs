//! BLOB-UI-RUNTIME-01C. Third real control with same G02/G03 graphical host.
use crate::ac01b_action::NativeActionHost;
use blobin_ui_core::layout::{Rect, Size};
use blobin_ui_core::SurfaceId;
use blobin_ui_scene::{
    transform_and_clip, ActionPalette, ActionVisualState, DisplayList, UiTransform2D,
};
pub const SIZE: (f32, f32) = (94., 26.);
pub struct NativeResetHost {
    core: NativeActionHost,
    transformed: Option<DisplayList>,
}
impl NativeResetHost {
    pub fn new() -> Result<Self, String> {
        Ok(Self {
            core: NativeActionHost::with_identity(SurfaceId(0x010C), "Réinitialiser", SIZE)?,
            transformed: None,
        })
    }
    pub fn display(&self) -> Option<&DisplayList> {
        self.transformed.as_ref()
    }
    pub fn clear(&mut self) {
        self.core.clear();
        self.transformed = None;
    }
    pub fn current_revision(&self) -> u64 {
        self.core.current_revision()
    }
    pub fn failure(&mut self) {
        self.core.failure()
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
        // 01C's nested clip/transform pipeline is bounded and called on every
        // frame; it does not take over semantic camera ownership.
        self.transformed = None;
        let base = self
            .core
            .update(size, scale, bounds, clip, state, palette)?;
        match base {
            Some(list) => {
                let list = transform_and_clip(list, UiTransform2D::IDENTITY, &[clip])
                    .map_err(|e| e.to_string())?;
                self.transformed = Some(list);
                Ok(self.transformed.as_ref())
            }
            None => {
                self.transformed = None;
                Ok(None)
            }
        }
    }
}
