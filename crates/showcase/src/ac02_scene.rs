//! BLOB-AC-02: native-consumer semantics, independent of Vulkan, egui and F4.
//! A temporary drag preview changes only projection. Completed card reordering
//! uses one UI-G02 transaction, followed by a fresh UI-G03 layout.
use blobin_ui_core::gestures::{CancelReason, GestureAction, GestureCoordinator, Translation};
use blobin_ui_core::input::{EventKind, InputError, InputEvent, InputRouter, Point};
use blobin_ui_core::layout::{
    self, Axis, Insets, LayoutSnapshot, LayoutStyles, Length, Rect, Style, Viewport,
};
use blobin_ui_core::{NodeId, NodeProperties, Role, SurfaceId, UiError, UiTree};

#[derive(Clone, Debug, PartialEq)]
pub enum Change {
    Begin {
        target: NodeId,
    },
    Preview {
        target: NodeId,
        delta: Translation,
    },
    Reordered {
        target: NodeId,
        revision: u64,
    },
    NoReorder {
        target: NodeId,
    },
    Cancel {
        target: NodeId,
        reason: CancelReason,
    },
    Activated {
        target: NodeId,
    },
}

#[derive(Clone, Debug, PartialEq)]
pub struct VisualCard {
    pub id: NodeId,
    pub bounds: Rect,
    pub is_dragging: bool,
    pub is_focused: bool,
    pub identity: usize,
}

pub struct NativeGestureScene {
    tree: UiTree,
    styles: LayoutStyles,
    layout: LayoutSnapshot,
    viewport: Viewport,
    surface: SurfaceId,
    root: NodeId,
    cards: [NodeId; 2],
    input: InputRouter,
    gestures: GestureCoordinator,
    preview: Option<(NodeId, Translation)>,
    commits: u64,
    cancellations: u64,
}
impl NativeGestureScene {
    pub fn new(viewport: Viewport) -> Result<Self, String> {
        let surface = SurfaceId(202);
        let mut tree = UiTree::new();
        let mut ids = None;
        tree.transact(|tx| {
            tx.open_surface(surface)?;
            let root = tx.append_root(
                surface,
                NodeProperties::new(Role::Container, "AC02 2D workspace"),
            )?;
            let a = tx.append_child(
                root,
                NodeProperties::new(Role::Custom("gesture_card".into()), "First card"),
            )?;
            let b = tx.append_child(
                root,
                NodeProperties::new(Role::Custom("gesture_card".into()), "Second card"),
            )?;
            ids = Some((root, [a, b]));
            Ok(())
        })
        .map_err(|e| e.to_string())?;
        let (root, cards) = ids.ok_or("missing generated nodes")?;
        let mut styles = LayoutStyles::new();
        let mut root_style = Style::fill();
        root_style.axis = Axis::Row;
        root_style.padding = Insets::uniform(36.0);
        root_style.gap = 24.0;
        root_style.clip_children = false; // preview can move past original box
        styles
            .set(&tree.snapshot(), root, root_style)
            .map_err(|e| e.to_string())?;
        for card in cards {
            styles
                .set(
                    &tree.snapshot(),
                    card,
                    Style {
                        width: Length::Fraction(0.39),
                        height: Length::Px(180.0),
                        ..Style::default()
                    },
                )
                .map_err(|e| e.to_string())?;
        }
        let layout = layout::compute(&tree.snapshot(), &styles, surface, viewport)
            .map_err(|e| e.to_string())?;
        Ok(Self {
            tree,
            styles,
            layout,
            viewport,
            surface,
            root,
            cards,
            input: InputRouter::new(),
            gestures: GestureCoordinator::new(),
            preview: None,
            commits: 0,
            cancellations: 0,
        })
    }
    pub fn viewport(&self) -> Viewport {
        self.viewport
    }
    pub fn surface(&self) -> SurfaceId {
        self.surface
    }
    pub fn revision(&self) -> u64 {
        self.tree.snapshot().revision()
    }
    pub fn commits(&self) -> u64 {
        self.commits
    }
    pub fn cancellations(&self) -> u64 {
        self.cancellations
    }
    pub fn geometry_epoch(&self) -> u64 {
        self.viewport.geometry_epoch
    }
    pub fn order(&self) -> [NodeId; 2] {
        let snap = self.tree.snapshot();
        let children = snap.get(self.root).expect("fixture root").children();
        [children[0], children[1]]
    }
    pub fn cards(&self) -> Vec<VisualCard> {
        let focus = self.input.focus(self.surface);
        let mut order = self.order().to_vec();
        if let Some((dragged, _)) = self.preview {
            order.retain(|id| *id != dragged);
            order.push(dragged);
        }
        order
            .into_iter()
            .filter_map(|id| {
                self.layout.get(id).map(|box_| {
                    let mut bounds = box_.rect;
                    let dragging = self.preview.is_some_and(|(target, _)| target == id);
                    if let Some((target, delta)) = self.preview {
                        if target == id {
                            bounds.x += delta.x;
                            bounds.y += delta.y;
                        }
                    }
                    VisualCard {
                        id,
                        bounds,
                        is_dragging: dragging,
                        is_focused: focus == Some(id),
                        identity: usize::from(id == self.cards[1]),
                    }
                })
            })
            .collect()
    }
    /// The host may reposition a surface; this cancels any in-flight preview
    /// before publishing fresh geometry. No semantic document mutation occurs.
    pub fn resize(&mut self, viewport: Viewport) -> Result<Vec<Change>, String> {
        let actions = self
            .gestures
            .cancel_surface(self.surface, CancelReason::LayoutChanged);
        let cancelled = self.cancels(actions);
        self.preview = None;
        let next = layout::compute(&self.tree.snapshot(), &self.styles, self.surface, viewport)
            .map_err(|e| e.to_string())?;
        self.viewport = viewport;
        self.layout = next;
        Ok(cancelled)
    }
    fn cancels(&mut self, actions: Vec<GestureAction>) -> Vec<Change> {
        let mut changes = Vec::new();
        for action in actions {
            if let GestureAction::Cancel { target, reason, .. } = action {
                self.cancellations += 1;
                self.preview = None;
                changes.push(Change::Cancel { target, reason });
            }
        }
        changes
    }
    /// Acceptance path for a host input event: UI-G04 dispatch -> BLOB-AC-01
    /// coordinator -> projection or one UI-G02 reorder -> UI-G03 new layout.
    pub fn ingest(
        &mut self,
        serial: u64,
        timestamp_micros: u64,
        kind: EventKind,
    ) -> Result<Vec<Change>, String> {
        let event = InputEvent::for_layout(&self.layout, serial, timestamp_micros, kind);
        let tree = self.tree.snapshot();
        let receipt = self
            .input
            .dispatch(
                &tree,
                &self.styles,
                &self.layout,
                self.viewport,
                event.clone(),
            )
            .map_err(|e: InputError| format!("input: {e}"))?;
        let actions = self
            .gestures
            .observe(
                &tree,
                &self.styles,
                &self.layout,
                self.viewport,
                &event,
                &receipt,
            )
            .map_err(|e| format!("gesture: {e}"))?;
        let mut changed = Vec::new();
        let mut was_gesture = false;
        let had_preview = self.preview.is_some();
        for action in actions {
            match action {
                GestureAction::Begin { target, .. } => {
                    was_gesture = true;
                    self.preview = None;
                    changed.push(Change::Begin { target });
                }
                GestureAction::Preview { target, delta, .. } => {
                    was_gesture = true;
                    self.preview = Some((target, delta));
                    changed.push(Change::Preview { target, delta });
                }
                GestureAction::Cancel { target, reason, .. } => {
                    was_gesture |= reason != CancelReason::NoTravel || had_preview;
                    self.cancellations += 1;
                    self.preview = None;
                    changed.push(Change::Cancel { target, reason });
                }
                GestureAction::Commit { target, delta, .. } => {
                    was_gesture = true;
                    self.preview = None;
                    let current = self.order();
                    let src = if target == current[0] { 0 } else { 1 };
                    let width = self.layout.get(target).map_or(0.0, |x| x.rect.width);
                    // Commit only when the drag crosses 28% of its source box
                    // *in the direction of the other card*. No fake absolute transforms.
                    let target_index = if src == 0 && delta.x > width * 0.28 {
                        Some(1)
                    } else if src == 1 && delta.x < -(width * 0.28) {
                        Some(0)
                    } else {
                        None
                    };
                    if let Some(index) = target_index {
                        self.tree
                            .transact(|tx| tx.reorder(target, index))
                            .map_err(|e: UiError| e.to_string())?;
                        self.layout = layout::compute(
                            &self.tree.snapshot(),
                            &self.styles,
                            self.surface,
                            self.viewport,
                        )
                        .map_err(|e| e.to_string())?;
                        self.commits += 1;
                        changed.push(Change::Reordered {
                            target,
                            revision: self.revision(),
                        });
                    } else {
                        changed.push(Change::NoReorder { target });
                    }
                }
            }
        }
        // G04 pointer-up can report an activation even after small movement:
        // don't allow a completed drag to double as a click.
        if !was_gesture {
            if let Some(target) = receipt.activated {
                changed.push(Change::Activated { target });
            }
        }
        Ok(changed)
    }
    pub fn close(&mut self) -> Vec<Change> {
        let actions = self.gestures.close_surface(self.surface);
        let changed = self.cancels(actions);
        self.input.close_surface(self.surface);
        changed
    }
    pub fn hit(&self, p: Point) -> Option<NodeId> {
        InputRouter::hit_test(
            &self.tree.snapshot(),
            &self.styles,
            &self.layout,
            self.viewport,
            p,
        )
        .ok()
        .flatten()
        .map(|r| r.target)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use blobin_ui_core::input::Units;
    use blobin_ui_core::layout::Size;
    fn scene() -> NativeGestureScene {
        NativeGestureScene::new(Viewport::new(Size::new(720.0, 420.0), 1.5, 1)).unwrap()
    }
    fn pointer(p: Point, state: &'static str) -> EventKind {
        match state {
            "down" => EventKind::PointerDown {
                pointer: 1,
                button: 1,
                position: p,
                units: Units::Logical,
            },
            "up" => EventKind::PointerUp {
                pointer: 1,
                button: 1,
                position: p,
                units: Units::Logical,
            },
            _ => EventKind::PointerMove {
                pointer: 1,
                position: p,
                units: Units::Logical,
            },
        }
    }
    fn center(r: Rect) -> Point {
        Point::new(r.x + r.width / 2.0, r.y + r.height / 2.0)
    }
    #[test]
    fn preview_does_not_commit_reorder_updates_real_layout_and_hit() {
        let mut s = scene();
        let original = s.order();
        let left = s
            .cards()
            .into_iter()
            .find(|v| v.id == original[0])
            .unwrap()
            .bounds;
        let p = center(left);
        s.ingest(1, 1, pointer(p, "down")).unwrap();
        let r = s
            .ingest(2, 2, pointer(Point::new(p.x + 130.0, p.y), "move"))
            .unwrap();
        assert!(matches!(r.as_slice(), [Change::Preview{delta,..}] if delta.x==130.0));
        assert_eq!(s.revision(), 1);
        assert_eq!(s.order(), original);
        let preview = s.cards().into_iter().find(|v| v.id == original[0]).unwrap();
        assert_eq!(preview.bounds.x, left.x + 130.0);
        let result = s
            .ingest(3, 3, pointer(Point::new(p.x + 140.0, p.y), "up"))
            .unwrap();
        assert!(matches!(
            result.as_slice(),
            [Change::Reordered { revision: 2, .. }]
        ));
        assert_eq!(s.commits(), 1);
        assert_eq!(s.order(), [original[1], original[0]]);
        let moved = s
            .cards()
            .into_iter()
            .find(|v| v.id == original[0])
            .unwrap()
            .bounds;
        assert!(moved.x > left.x);
        assert_eq!(s.hit(center(moved)), Some(original[0]));
        assert_eq!(s.revision(), 2);
    }
    #[test]
    fn subthreshold_drag_does_not_mutate_tree() {
        let mut s = scene();
        let p = center(s.cards()[0].bounds);
        s.ingest(1, 1, pointer(p, "down")).unwrap();
        s.ingest(2, 2, pointer(Point::new(p.x + 5.0, p.y), "move"))
            .unwrap();
        let out = s
            .ingest(3, 3, pointer(Point::new(p.x + 5.0, p.y), "up"))
            .unwrap();
        assert!(matches!(out.as_slice(), [Change::NoReorder { .. }]));
        assert_eq!(s.revision(), 1);
        assert_eq!(s.commits(), 0);
        assert!(s.cards().iter().all(|v| !v.is_dragging));
    }
    #[test]
    fn cancelled_drag_and_resize_preserve_revision() {
        let mut s = scene();
        let p = center(s.cards()[0].bounds);
        s.ingest(1, 1, pointer(p, "down")).unwrap();
        s.ingest(2, 2, pointer(Point::new(p.x + 130.0, p.y), "move"))
            .unwrap();
        let cancelled = s
            .resize(Viewport::new(Size::new(600.0, 400.0), 2.0, 2))
            .unwrap();
        assert!(matches!(
            cancelled.as_slice(),
            [Change::Cancel {
                reason: CancelReason::LayoutChanged,
                ..
            }]
        ));
        assert_eq!(s.revision(), 1);
        assert!(s.cards().iter().all(|v| !v.is_dragging));
    }
    #[test]
    fn simple_click_still_activates_once_without_drag_commit() {
        let mut s = scene();
        let p = center(s.cards()[0].bounds);
        s.ingest(1, 1, pointer(p, "down")).unwrap();
        let actions = s.ingest(2, 2, pointer(p, "up")).unwrap();
        assert_eq!(
            actions
                .iter()
                .filter(|x| matches!(x, Change::Activated { .. }))
                .count(),
            1
        );
        assert_eq!(s.commits(), 0);
        assert_eq!(s.revision(), 1);
    }
    #[test]
    fn second_card_can_be_reordered_left_with_exactly_one_revision() {
        let mut s = scene();
        let order = s.order();
        let right = s
            .cards()
            .into_iter()
            .find(|v| v.id == order[1])
            .unwrap()
            .bounds;
        let p = center(right);
        s.ingest(1, 1, pointer(p, "down")).unwrap();
        s.ingest(2, 2, pointer(Point::new(p.x - 120.0, p.y), "move"))
            .unwrap();
        let actions = s
            .ingest(3, 3, pointer(Point::new(p.x - 150.0, p.y), "up"))
            .unwrap();
        assert_eq!(
            actions
                .iter()
                .filter(|x| matches!(x, Change::Reordered { .. }))
                .count(),
            1
        );
        assert_eq!(s.order(), [order[1], order[0]]);
        assert_eq!(s.revision(), 2);
        assert_eq!(s.commits(), 1);
    }
    #[test]
    fn escape_clears_preview_without_reorder() {
        let mut s = scene();
        let p = center(s.cards()[0].bounds);
        s.ingest(1, 1, pointer(p, "down")).unwrap();
        s.ingest(2, 2, pointer(Point::new(p.x + 155.0, p.y), "move"))
            .unwrap();
        let out = s
            .ingest(
                3,
                3,
                EventKind::KeyDown {
                    key: blobin_ui_core::input::Key::Escape,
                    shift: false,
                    repeat: false,
                },
            )
            .unwrap();
        assert!(matches!(
            out.as_slice(),
            [Change::Cancel {
                reason: CancelReason::Escape,
                ..
            }]
        ));
        assert_eq!(s.revision(), 1);
    }
}
