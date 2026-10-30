//! Shared G02/G03 layout ownership for independent native UI controls.
//! The caller owns the palette, action, input, and eventual GPU draw pass.
use blobin_ui_core::layout::{
    self, Insets, LayoutSnapshot, LayoutStyles, Length, Rect, Size, Style, Viewport,
};
use blobin_ui_core::{NodeId, NodeProperties, Role, SurfaceId, UiSnapshot, UiTree};
use blobin_ui_scene::{DisplayList, SceneError};

pub struct ControlLayoutHost {
    tree: UiTree,
    styles: LayoutStyles,
    root: NodeId,
    id: NodeId,
    size: (f32, f32),
    geometry_epoch: u64,
    last_viewport: Option<(Size, f32)>,
    semantic: Option<(&'static str, bool)>,
    display: Option<DisplayList>,
    pub failures: u64,
}
impl ControlLayoutHost {
    pub fn new(surface: SurfaceId, label: &'static str, size: (f32, f32)) -> Result<Self, String> {
        let mut tree = UiTree::new();
        let mut nodes = None;
        tree.transact(|tx| {
            tx.open_surface(surface)?;
            let root = tx.append_root(
                surface,
                NodeProperties::new(Role::Container, "UI control host"),
            )?;
            let id = tx.append_child(root, NodeProperties::new(Role::Button, label))?;
            nodes = Some((root, id));
            Ok(())
        })
        .map_err(|e| e.to_string())?;
        let (root, id) = nodes.ok_or("missing control nodes")?;
        let mut styles = LayoutStyles::new();
        styles
            .set(
                &tree.snapshot(),
                id,
                Style {
                    width: Length::Px(size.0),
                    height: Length::Px(size.1),
                    stretch_cross: false,
                    flex_shrink: 0.0,
                    ..Style::default()
                },
            )
            .map_err(|e| e.to_string())?;
        Ok(Self {
            tree,
            styles,
            root,
            id,
            size,
            geometry_epoch: 1,
            last_viewport: None,
            semantic: None,
            display: None,
            failures: 0,
        })
    }
    pub fn id(&self) -> NodeId {
        self.id
    }
    pub fn revision(&self) -> u64 {
        self.tree.snapshot().revision()
    }
    pub fn display(&self) -> Option<&DisplayList> {
        self.display.as_ref()
    }
    pub fn clear(&mut self) {
        self.display = None
    }
    /// The callback may use only the validated G02 snapshot and G03 layout.
    /// It cannot mutate scene, input authority or the renderer.
    #[allow(clippy::too_many_arguments)]
    pub fn update<F>(
        &mut self,
        viewport_size: Size,
        scale: f32,
        bounds: Rect,
        clip: Rect,
        label: &'static str,
        enabled: bool,
        draw: F,
    ) -> Result<Option<&DisplayList>, String>
    where
        F: FnOnce(
            &UiSnapshot,
            &LayoutStyles,
            &LayoutSnapshot,
            Viewport,
            NodeId,
            Rect,
        ) -> Result<DisplayList, SceneError>,
    {
        self.clear(); // fail closed, never reuse stale graphics
        if self.last_viewport != Some((viewport_size, scale)) {
            self.geometry_epoch = self
                .geometry_epoch
                .checked_add(1)
                .ok_or("geometry epoch exhausted")?;
            self.last_viewport = Some((viewport_size, scale));
        }
        if self.semantic != Some((label, enabled)) {
            let mut props = NodeProperties::new(Role::Button, label);
            props.enabled = enabled;
            self.tree
                .transact(|tx| tx.set_properties(self.id, props))
                .map_err(|e| e.to_string())?;
            self.semantic = Some((label, enabled));
        }
        if !viewport_size.width.is_finite()
            || !viewport_size.height.is_finite()
            || viewport_size.width < 0.0
            || viewport_size.height < 0.0
            || !bounds.x.is_finite()
            || !bounds.y.is_finite()
            || bounds.x < 0.0
            || bounds.y < 0.0
            || bounds.width != self.size.0
            || bounds.height != self.size.1
            || bounds.x + bounds.width > viewport_size.width + 0.1
            || bounds.y + bounds.height > viewport_size.height + 0.1
        {
            return Err("UI host bounds invalid".into());
        }
        let mut root_style = Style::fill();
        root_style.padding = Insets {
            left: bounds.x,
            top: bounds.y,
            right: (viewport_size.width - (bounds.x + bounds.width)).max(0.0),
            bottom: (viewport_size.height - (bounds.y + bounds.height)).max(0.0),
        };
        root_style.clip_children = true;
        self.styles
            .set(&self.tree.snapshot(), self.root, root_style)
            .map_err(|e| e.to_string())?;
        let vp = Viewport::new(viewport_size, scale, self.geometry_epoch);
        let snapshot = self.tree.snapshot();
        let layout = layout::compute(
            &snapshot,
            &self.styles,
            snapshot.get(self.id).ok_or("control missing")?.surface(),
            vp,
        )
        .map_err(|e| e.to_string())?;
        let actual = layout.get(self.id).ok_or("control layout missing")?.rect;
        let delta = [
            actual.x - bounds.x,
            actual.y - bounds.y,
            actual.width - bounds.width,
            actual.height - bounds.height,
        ];
        if delta.iter().any(|d| d.abs() > 0.2) {
            return Err(format!("G03 bounds mismatch with input capture {delta:?}"));
        }
        match draw(&snapshot, &self.styles, &layout, vp, self.id, clip) {
            Ok(value) => self.display = Some(value),
            Err(SceneError::Invisible) => {}
            Err(error) => return Err(error.to_string()),
        }
        Ok(self.display())
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn independent_nodes_stable_and_stale_geometry_never_publishes() {
        let mut h = ControlLayoutHost::new(SurfaceId(18), "action", (88., 26.)).unwrap();
        let id = h.id();
        let compile = |h: &mut ControlLayoutHost, x: f32| {
            h.update(
                Size::new(1100., 800.),
                1.0,
                Rect::new(x, 140., 88., 26.),
                Rect::new(0., 0., 1100., 800.),
                "action",
                true,
                |tree, styles, layout, vp, node, clip| {
                    blobin_ui_scene::action_button(
                        tree,
                        styles,
                        layout,
                        vp,
                        node,
                        blobin_ui_scene::ActionVisualState {
                            selected: false,
                            hovered: false,
                            focused: false,
                            pressed: false,
                            enabled: true,
                        },
                        blobin_ui_scene::ActionPalette {
                            idle: blobin_ui_scene::Rgba8::new(1, 2, 3, 255),
                            selected: blobin_ui_scene::Rgba8::new(5, 6, 7, 255),
                            hover: blobin_ui_scene::Rgba8::new(6, 7, 8, 255),
                            pressed: blobin_ui_scene::Rgba8::new(3, 4, 5, 255),
                            border: blobin_ui_scene::Rgba8::new(0, 0, 0, 255),
                            focus: blobin_ui_scene::Rgba8::new(2, 3, 4, 255),
                            disabled: blobin_ui_scene::Rgba8::new(8, 9, 10, 255),
                            selected_marker: blobin_ui_scene::Rgba8::new(255, 200, 50, 255),
                        },
                        clip,
                    )
                },
            )
            .map(|value| value.is_some())
        };
        assert!(compile(&mut h, 900.).unwrap());
        let rev = h.revision();
        assert!(compile(&mut h, 900.).unwrap());
        assert_eq!(h.revision(), rev);
        assert_eq!(h.id(), id);
        assert!(compile(&mut h, 1090.).is_err());
        assert!(h.display().is_none());
    }
}
