//! UI-RUNTIME-01A: first-party G02/G03-to-display-list boundary.
//! No egui, winit, wgpu, F4, brand/theme authority or GPU resource ownership.
use blobin_ui_core::layout::{LayoutSnapshot, LayoutStyles, Rect, Viewport};
use blobin_ui_core::{NodeId, Role, SurfaceId, UiSnapshot};
use std::fmt;

pub mod bezier;
pub mod composition;
pub mod concave;
pub mod fills;
pub mod strokes;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Rgba8 {
    pub r: u8,
    pub g: u8,
    pub b: u8,
    pub a: u8,
}
impl Rgba8 {
    pub const fn new(r: u8, g: u8, b: u8, a: u8) -> Self {
        Self { r, g, b, a }
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct TogglePalette {
    pub track_off: Rgba8,
    pub track_on: Rgba8,
    pub border: Rgba8,
    pub thumb: Rgba8,
    pub thumb_disabled: Rgba8,
    pub focus: Rgba8,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ToggleVisualState {
    pub checked: bool,
    pub hovered: bool,
    pub focused: bool,
    pub enabled: bool,
}
/// Only graphics; no action interpreter, focus controller or theme policy.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct FillRoundedRect {
    pub source: NodeId,
    pub rect: Rect,
    pub clip: Rect,
    pub color: Rgba8,
    pub radius: f32,
}
#[derive(Clone, Debug, PartialEq)]
pub struct DisplayList {
    pub source_ui_revision: u64,
    pub surface: SurfaceId,
    pub layout_epoch: u64,
    pub source_node: NodeId,
    pub commands: Vec<FillRoundedRect>,
    /// Lines are painted after the filled rects of the same layer.
    pub strokes: Vec<strokes::StrokeSegment>,
    /// Convex path fill fan triangles, painted after rectangles and before strokes.
    pub triangles: Vec<fills::FillTriangle>,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SceneError {
    StaleLayout,
    InvalidTarget,
    InvalidBounds,
    Invisible,
}
impl fmt::Display for SceneError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}
impl std::error::Error for SceneError {}
fn finite(r: Rect) -> bool {
    [r.x, r.y, r.width, r.height, r.x + r.width, r.y + r.height]
        .iter()
        .all(|v| v.is_finite())
        && r.width >= 0.0
        && r.height >= 0.0
}
/// Build a real toggle's background, border and thumb. Text is not owned by this
/// v0.1 drawing API; consumers must explicitly supply a separate label renderer.
/// Input/hit authority stays with the current application's input owner.
#[allow(clippy::too_many_arguments)]
pub fn toggle(
    tree: &UiSnapshot,
    styles: &LayoutStyles,
    layout: &LayoutSnapshot,
    viewport: Viewport,
    node: NodeId,
    state: ToggleVisualState,
    palette: TogglePalette,
    external_clip: Rect,
) -> Result<DisplayList, SceneError> {
    if !layout.is_current(tree, styles, viewport) {
        return Err(SceneError::StaleLayout);
    }
    let target = tree.get(node).ok_or(SceneError::InvalidTarget)?;
    if target.surface() != layout.stamp.surface
        || !matches!(target.properties().role, Role::Button)
        || state.enabled != target.properties().enabled
    {
        return Err(SceneError::InvalidTarget);
    }
    let box_ = layout.get(node).ok_or(SceneError::InvalidTarget)?;
    let rect = box_.rect;
    if !finite(rect) || !finite(external_clip) || rect.width < 28.0 || rect.height < 16.0 {
        return Err(SceneError::InvalidBounds);
    }
    let clip = box_.visible.intersect(external_clip);
    if clip.width <= 0.0 || clip.height <= 0.0 {
        return Err(SceneError::Invisible);
    }
    let inset = 2.0;
    let inner = Rect::new(
        rect.x + inset,
        rect.y + inset,
        rect.width - 2.0 * inset,
        rect.height - 2.0 * inset,
    );
    let diameter = (rect.height - 8.0).min(rect.width * 0.42);
    let thumb_x = if state.checked {
        rect.x + rect.width - 4.0 - diameter
    } else {
        rect.x + 4.0
    };
    let thumb = Rect::new(
        thumb_x,
        rect.y + (rect.height - diameter) * 0.5,
        diameter,
        diameter,
    );
    let track_color = if !state.enabled {
        palette.thumb_disabled
    } else if state.checked {
        palette.track_on
    } else {
        palette.track_off
    };
    let outer_color = if state.focused {
        palette.focus
    } else {
        palette.border
    };
    Ok(DisplayList {
        source_ui_revision: tree.revision(),
        surface: layout.stamp.surface,
        layout_epoch: layout.stamp.geometry_epoch,
        source_node: node,
        strokes: vec![],
        triangles: vec![],
        commands: vec![
            FillRoundedRect {
                source: node,
                rect,
                clip,
                color: outer_color,
                radius: rect.height * 0.5,
            },
            FillRoundedRect {
                source: node,
                rect: inner,
                clip,
                color: track_color,
                radius: inner.height * 0.5,
            },
            FillRoundedRect {
                source: node,
                rect: thumb,
                clip,
                color: if state.enabled {
                    palette.thumb
                } else {
                    palette.thumb_disabled
                },
                radius: diameter * 0.5,
            },
        ],
    })
}
/// Generic axis-aligned fill primitive with zero corner radius. The caller
/// retains styling, layout, clipping and G02 provenance authority.
pub fn solid_rectangle(
    source: NodeId,
    rect: Rect,
    clip: Rect,
    color: Rgba8,
) -> Result<FillRoundedRect, SceneError> {
    if !finite(rect) || !finite(clip) {
        return Err(SceneError::InvalidBounds);
    }
    if rect.width == 0.
        || rect.height == 0.
        || rect.intersect(clip).width == 0.
        || rect.intersect(clip).height == 0.
    {
        return Err(SceneError::Invisible);
    }
    Ok(FillRoundedRect {
        source,
        rect,
        clip,
        color,
        radius: 0.,
    })
}

/// First-party bounded 2D scale+translation. Not a general affine or rotation API.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct UiTransform2D {
    pub sx: f32,
    pub sy: f32,
    pub tx: f32,
    pub ty: f32,
}
impl UiTransform2D {
    pub const IDENTITY: Self = Self {
        sx: 1.,
        sy: 1.,
        tx: 0.,
        ty: 0.,
    };
    pub fn checked(self) -> Result<Self, SceneError> {
        if [self.sx, self.sy, self.tx, self.ty]
            .iter()
            .all(|v| v.is_finite())
            && self.sx > 0.
            && self.sy > 0.
        {
            Ok(self)
        } else {
            Err(SceneError::InvalidBounds)
        }
    }
    pub fn rect(self, r: Rect) -> Result<Rect, SceneError> {
        self.checked()?;
        if !finite(r) {
            return Err(SceneError::InvalidBounds);
        }
        let result = Rect::new(
            r.x * self.sx + self.tx,
            r.y * self.sy + self.ty,
            r.width * self.sx,
            r.height * self.sy,
        );
        if finite(result) {
            Ok(result)
        } else {
            Err(SceneError::InvalidBounds)
        }
    }
}
/// Applies a bounded transform and the intersection of all ancestor clips.
/// Output is a new immutable DisplayList. Semantic G02 identity is unchanged.
pub fn transform_and_clip(
    source: &DisplayList,
    transform: UiTransform2D,
    ancestors: &[Rect],
) -> Result<DisplayList, SceneError> {
    transform.checked()?;
    if ancestors.iter().any(|r| !finite(*r)) {
        return Err(SceneError::InvalidBounds);
    }
    let mut commands = Vec::with_capacity(source.commands.len());
    for command in &source.commands {
        if command.source != source.source_node
            || !finite(command.rect)
            || !finite(command.clip)
            || !command.radius.is_finite()
            || command.radius < 0.
        {
            return Err(SceneError::InvalidBounds);
        }
        let rect = transform.rect(command.rect)?;
        let mut clip = transform.rect(command.clip)?;
        for ancestor in ancestors {
            clip = clip.intersect(*ancestor);
        }
        if clip.width > 0. && clip.height > 0. {
            commands.push(FillRoundedRect {
                source: command.source,
                rect,
                clip,
                color: command.color,
                radius: command.radius * transform.sx.min(transform.sy),
            });
        }
    }
    let strokes = source
        .strokes
        .iter()
        .filter_map(|line| match line.transformed(transform, ancestors) {
            Ok(segment) => Some(Ok(segment)),
            Err(SceneError::Invisible) => None,
            Err(e) => Some(Err(e)),
        })
        .collect::<Result<Vec<_>, _>>()?;
    let triangles = source
        .triangles
        .iter()
        .filter_map(|shape| match shape.transformed(transform, ancestors) {
            Ok(triangle) => Some(Ok(triangle)),
            Err(SceneError::Invisible) => None,
            Err(e) => Some(Err(e)),
        })
        .collect::<Result<Vec<_>, _>>()?;
    if commands.is_empty() && strokes.is_empty() && triangles.is_empty() {
        return Err(SceneError::Invisible);
    }
    Ok(DisplayList {
        commands,
        strokes,
        triangles,
        ..source.clone()
    })
}
/// An egui-independent paint recipe for a selectable UI action button.
/// The host retains sole input authority; text remains an explicit consumer slot.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ActionVisualState {
    pub selected: bool,
    pub hovered: bool,
    pub focused: bool,
    pub pressed: bool,
    pub enabled: bool,
}
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ActionPalette {
    pub idle: Rgba8,
    pub selected: Rgba8,
    pub hover: Rgba8,
    pub pressed: Rgba8,
    pub border: Rgba8,
    pub focus: Rgba8,
    pub disabled: Rgba8,
    pub selected_marker: Rgba8,
}
#[allow(clippy::too_many_arguments)]
pub fn action_button(
    tree: &UiSnapshot,
    styles: &LayoutStyles,
    layout: &LayoutSnapshot,
    viewport: Viewport,
    node: NodeId,
    state: ActionVisualState,
    palette: ActionPalette,
    external_clip: Rect,
) -> Result<DisplayList, SceneError> {
    if !layout.is_current(tree, styles, viewport) {
        return Err(SceneError::StaleLayout);
    }
    let target = tree.get(node).ok_or(SceneError::InvalidTarget)?;
    if target.surface() != layout.stamp.surface
        || !matches!(target.properties().role, Role::Button)
        || target.properties().enabled != state.enabled
    {
        return Err(SceneError::InvalidTarget);
    }
    let box_ = layout.get(node).ok_or(SceneError::InvalidTarget)?;
    let rect = box_.rect;
    if !finite(rect) || !finite(external_clip) || rect.width < 48.0 || rect.height < 18.0 {
        return Err(SceneError::InvalidBounds);
    }
    let clip = box_.visible.intersect(external_clip);
    if clip.width <= 0.0 || clip.height <= 0.0 {
        return Err(SceneError::Invisible);
    }
    let fill = if !state.enabled {
        palette.disabled
    } else if state.pressed {
        palette.pressed
    } else if state.selected {
        palette.selected
    } else if state.hovered {
        palette.hover
    } else {
        palette.idle
    };
    let stroke = if state.focused {
        palette.focus
    } else {
        palette.border
    };
    let inner = Rect::new(
        rect.x + 1.0,
        rect.y + 1.0,
        rect.width - 2.0,
        rect.height - 2.0,
    );
    let underline = Rect::new(
        rect.x + 8.0,
        rect.y + rect.height - 3.5,
        rect.width - 16.0,
        2.0,
    );
    Ok(DisplayList {
        source_ui_revision: tree.revision(),
        surface: layout.stamp.surface,
        layout_epoch: layout.stamp.geometry_epoch,
        source_node: node,
        strokes: vec![],
        triangles: vec![],
        commands: vec![
            FillRoundedRect {
                source: node,
                rect,
                clip,
                color: stroke,
                radius: 7.0,
            },
            FillRoundedRect {
                source: node,
                rect: inner,
                clip,
                color: fill,
                radius: 6.0,
            },
            FillRoundedRect {
                source: node,
                rect: underline,
                clip,
                color: if state.selected && state.enabled {
                    palette.selected_marker
                } else {
                    Rgba8::new(0, 0, 0, 0)
                },
                radius: 1.0,
            },
        ],
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use blobin_ui_core::layout::{self, Length, Size, Style};
    use blobin_ui_core::{NodeProperties, UiTree};
    fn fixture() -> (UiTree, LayoutStyles, Viewport, NodeId) {
        let mut tree = UiTree::new();
        let mut id = None;
        tree.transact(|tx| {
            tx.open_surface(SurfaceId(7))?;
            let root =
                tx.append_root(SurfaceId(7), NodeProperties::new(Role::Container, "root"))?;
            id = Some(tx.append_child(root, NodeProperties::new(Role::Button, "show overlays"))?);
            Ok(())
        })
        .unwrap();
        let viewport = Viewport::new(Size::new(220.0, 80.0), 2.0, 1);
        let mut styles = LayoutStyles::new();
        styles
            .set(
                &tree.snapshot(),
                tree.snapshot().roots(SurfaceId(7)).unwrap()[0],
                Style::fill(),
            )
            .unwrap();
        styles
            .set(
                &tree.snapshot(),
                id.unwrap(),
                Style {
                    width: Length::Px(52.0),
                    height: Length::Px(26.0),
                    stretch_cross: false,
                    ..Style::default()
                },
            )
            .unwrap();
        (tree, styles, viewport, id.unwrap())
    }
    fn palette() -> TogglePalette {
        TogglePalette {
            track_off: Rgba8::new(1, 2, 3, 255),
            track_on: Rgba8::new(4, 5, 6, 255),
            border: Rgba8::new(7, 8, 9, 255),
            thumb: Rgba8::new(255, 255, 255, 255),
            thumb_disabled: Rgba8::new(50, 50, 50, 255),
            focus: Rgba8::new(10, 11, 12, 255),
        }
    }
    fn compile(
        tree: &UiTree,
        styles: &LayoutStyles,
        v: Viewport,
        id: NodeId,
        checked: bool,
    ) -> Result<DisplayList, SceneError> {
        let snapshot = tree.snapshot();
        let layout = layout::compute(&snapshot, styles, SurfaceId(7), v).unwrap();
        toggle(
            &snapshot,
            styles,
            &layout,
            v,
            id,
            ToggleVisualState {
                checked,
                hovered: false,
                focused: false,
                enabled: true,
            },
            palette(),
            Rect::new(0.0, 0.0, 220.0, 80.0),
        )
    }
    fn action_palette() -> ActionPalette {
        ActionPalette {
            idle: Rgba8::new(4, 5, 6, 255),
            selected: Rgba8::new(21, 39, 51, 255),
            hover: Rgba8::new(35, 45, 55, 255),
            pressed: Rgba8::new(10, 15, 19, 255),
            border: Rgba8::new(9, 8, 7, 255),
            focus: Rgba8::new(200, 200, 0, 255),
            disabled: Rgba8::new(20, 20, 20, 255),
            selected_marker: Rgba8::new(240, 40, 40, 255),
        }
    }
    #[test]
    fn action_visual_state_is_semantic_and_deterministic() {
        let (tree, styles, v, id) = fixture();
        let snapshot = tree.snapshot();
        let layout = layout::compute(&snapshot, &styles, SurfaceId(7), v).unwrap();
        let mut state = ActionVisualState {
            selected: false,
            hovered: false,
            focused: false,
            pressed: false,
            enabled: true,
        };
        let clip = Rect::new(0., 0., 220., 80.);
        let a = action_button(
            &snapshot,
            &styles,
            &layout,
            v,
            id,
            state,
            action_palette(),
            clip,
        )
        .unwrap();
        state.selected = true;
        let b = action_button(
            &snapshot,
            &styles,
            &layout,
            v,
            id,
            state,
            action_palette(),
            clip,
        )
        .unwrap();
        assert_eq!(a.commands.len(), 3);
        assert_eq!(a.commands[0].rect, b.commands[0].rect);
        assert_ne!(a.commands[1].color, b.commands[1].color);
        assert_eq!(a.commands[2].color.a, 0);
        assert_eq!(b.commands[2].color.a, 255);
        assert_eq!(a.source_node, b.source_node);
    }
    #[test]
    fn action_rejects_stale_layout_and_empty_clip() {
        let (tree, styles, v, id) = fixture();
        let snapshot = tree.snapshot();
        let layout = layout::compute(&snapshot, &styles, SurfaceId(7), v).unwrap();
        let state = ActionVisualState {
            selected: true,
            hovered: false,
            focused: false,
            pressed: false,
            enabled: true,
        };
        let bad = Viewport::new(v.logical, v.scale_factor, v.geometry_epoch + 1);
        assert_eq!(
            action_button(
                &snapshot,
                &styles,
                &layout,
                bad,
                id,
                state,
                action_palette(),
                Rect::new(0., 0., 220., 80.)
            ),
            Err(SceneError::StaleLayout)
        );
        assert_eq!(
            action_button(
                &snapshot,
                &styles,
                &layout,
                v,
                id,
                state,
                action_palette(),
                Rect::new(500., 500., 20., 20.)
            ),
            Err(SceneError::Invisible)
        );
    }
    #[test]
    fn transform_and_nested_clips_preserve_semantics() {
        let (t, s, v, id) = fixture();
        let original = compile(&t, &s, v, id, true).unwrap();
        let transform = UiTransform2D {
            sx: 2.,
            sy: 1.5,
            tx: 4.,
            ty: 8.,
        };
        let parent = Rect::new(0., 0., 300., 120.);
        let scroller = Rect::new(4., 8., 50., 24.);
        let painted = transform_and_clip(&original, transform, &[parent, scroller]).unwrap();
        assert_eq!(painted.source_node, original.source_node);
        assert_eq!(painted.source_ui_revision, original.source_ui_revision);
        assert_eq!(painted.commands.len(), 3);
        assert_eq!(painted.commands[0].clip, scroller);
        assert_eq!(
            painted.commands[0].rect,
            transform.rect(original.commands[0].rect).unwrap()
        );
    }
    #[test]
    fn transforms_reject_nonfinite_and_inverted_scales() {
        let (t, s, v, id) = fixture();
        let list = compile(&t, &s, v, id, true).unwrap();
        for sx in [0., -1., f32::NAN, f32::INFINITY] {
            assert_eq!(
                transform_and_clip(
                    &list,
                    UiTransform2D {
                        sx,
                        sy: 1.,
                        tx: 0.,
                        ty: 0.
                    },
                    &[]
                ),
                Err(SceneError::InvalidBounds)
            );
        }
        assert_eq!(
            transform_and_clip(
                &list,
                UiTransform2D::IDENTITY,
                &[Rect::new(900., 900., 20., 20.)]
            ),
            Err(SceneError::Invisible)
        );
    }
    #[test]
    fn state_changes_only_thumb_and_track() {
        let (t, s, v, id) = fixture();
        let a = compile(&t, &s, v, id, false).unwrap();
        let b = compile(&t, &s, v, id, true).unwrap();
        assert_eq!(a.commands.len(), 3);
        assert_eq!(a.commands[0], b.commands[0]);
        assert_ne!(a.commands[1].color, b.commands[1].color);
        assert_ne!(a.commands[2].rect, b.commands[2].rect);
        assert_eq!(a.source_node, id);
    }
    #[test]
    fn rejects_stale_geometry_epoch() {
        let (t, s, v, id) = fixture();
        let snapshot = t.snapshot();
        let layout = layout::compute(&snapshot, &s, SurfaceId(7), v).unwrap();
        let changed = Viewport::new(v.logical, v.scale_factor, 2);
        assert_eq!(
            toggle(
                &snapshot,
                &s,
                &layout,
                changed,
                id,
                ToggleVisualState {
                    checked: false,
                    hovered: false,
                    focused: false,
                    enabled: true
                },
                palette(),
                Rect::new(0., 0., 220., 80.)
            ),
            Err(SceneError::StaleLayout)
        );
    }
    #[test]
    fn clipping_and_semantic_target() {
        let (t, s, v, id) = fixture();
        let snapshot = t.snapshot();
        let layout = layout::compute(&snapshot, &s, SurfaceId(7), v).unwrap();
        let cut = Rect::new(0., 0., 20., 15.);
        let list = toggle(
            &snapshot,
            &s,
            &layout,
            v,
            id,
            ToggleVisualState {
                checked: false,
                hovered: false,
                focused: false,
                enabled: true,
            },
            palette(),
            cut,
        )
        .unwrap();
        assert_eq!(list.commands[0].clip, cut);
        assert_eq!(list.commands[2].source, id);
    }
    #[test]
    fn no_brand_dependency_or_external_renderer() {
        let (t, s, v, id) = fixture();
        let scene = compile(&t, &s, v, id, true).unwrap();
        assert!(scene
            .commands
            .iter()
            .all(|r| r.color.a > 0 && r.radius > 0.0));
        assert_eq!(scene.layout_epoch, 1);
    }
}
