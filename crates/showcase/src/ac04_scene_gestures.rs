//! BLOB-AC-04: a production-canvas adapter for the AC-01 absolute-delta
//! transaction contract. egui owns hit-testing/capture for this existing app;
//! no second UI-G04 input router is installed over an egui window.
//! Previews are local overlays / camera projection; BLOB-FRAME requests are
//! invalidated once on Commit, never on Preview.
use crate::scene::{Camera, Lab, SceneState};
use crate::view::View;
use blobin_ui_core::gestures::Translation;

#[derive(Clone, Copy, Debug, PartialEq)]
enum Active {
    Move {
        id: u32,
        from: (f32, f32),
        next: (f32, f32),
        lab: Lab,
        camera: Camera,
    },
    Pan {
        from: Camera,
        next: Camera,
    },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Commit {
    Moved(u32),
    Panned,
    NoChange,
    Cancelled,
}

#[derive(Clone, Copy, Debug, PartialEq)]
struct MoveUndo {
    id: u32,
    lab: Lab,
    from: (f32, f32),
    to: (f32, f32),
}

/// One egui-recognized gesture = one semantic commit and one undo entry.
/// All deltas are recomputed against their first-state snapshot, never summed.
#[derive(Default)]
pub struct CanvasTransactions {
    active: Option<Active>,
    move_history: Vec<MoveUndo>,
    commits: u64,
    cancels: u64,
}

const MAX_HISTORY: usize = 32;
impl CanvasTransactions {
    pub fn new() -> Self {
        Self::default()
    }
    pub fn active(&self) -> bool {
        self.active.is_some()
    }
    pub fn commits(&self) -> u64 {
        self.commits
    }
    pub fn cancellations(&self) -> u64 {
        self.cancels
    }
    pub fn undo_count(&self) -> usize {
        self.move_history.len()
    }
    pub fn begin(&mut self, scene: &SceneState, camera: Camera, hit: Option<u32>) -> bool {
        if self.active.is_some() {
            return false;
        }
        self.active = Some(if let Some(id) = hit {
            let Some(circle) = scene.get(id) else {
                return false;
            };
            Active::Move {
                id,
                from: (circle.x, circle.y),
                next: (circle.x, circle.y),
                lab: scene.lab,
                camera,
            }
        } else {
            Active::Pan {
                from: camera,
                next: camera,
            }
        });
        true
    }
    pub fn preview(&mut self, scene: &SceneState, view: View, delta: Translation) -> bool {
        let Some(active) = self.active else {
            return false;
        };
        if !delta.x.is_finite()
            || !delta.y.is_finite()
            || delta.x.abs() > 1_000_000.0
            || delta.y.abs() > 1_000_000.0
        {
            self.cancel();
            return false;
        }
        let next = match active {
            Active::Move {
                id,
                from,
                lab,
                camera,
                ..
            } => {
                if scene.lab != lab
                    || scene.get(id).is_none_or(|c| (c.x, c.y) != from)
                    || camera != view.camera
                {
                    self.cancel();
                    return false;
                }
                let target = (
                    from.0 + view.world_len(delta.x),
                    from.1 + view.world_len(delta.y),
                );
                if !target.0.is_finite()
                    || !target.1.is_finite()
                    || !(-2.0..=2.0).contains(&((target.0 - camera.cx) * camera.zoom))
                    || !(-2.0..=2.0).contains(&((target.1 - camera.cy) * camera.zoom))
                {
                    self.cancel();
                    return false;
                }
                Active::Move {
                    id,
                    from,
                    next: target,
                    lab,
                    camera,
                }
            }
            Active::Pan { from, .. } => {
                let cam = Camera {
                    cx: from.cx - view.world_len(delta.x),
                    cy: from.cy - view.world_len(delta.y),
                    ..from
                };
                if !cam.cx.is_finite() || !cam.cy.is_finite() {
                    self.cancel();
                    return false;
                }
                Active::Pan { from, next: cam }
            }
        };
        self.active = Some(next);
        true
    }
    /// Position of a preview overlay; the canonical scene is unchanged.
    pub fn preview_position(&self, id: u32) -> Option<(f32, f32)> {
        match self.active {
            Some(Active::Move {
                id: selected, next, ..
            }) if selected == id => Some(next),
            _ => None,
        }
    }
    /// Preview-only camera for moving the last valid BLOB-FRAME image.
    pub fn preview_camera(&self, canonical: Camera) -> Camera {
        match self.active {
            Some(Active::Pan { next, .. }) => next,
            _ => canonical,
        }
    }
    pub fn cancel(&mut self) -> bool {
        let had = self.active.take().is_some();
        if had {
            self.cancels += 1;
        }
        had
    }
    /// Document/scene mutations happen only here; caller invalidates scheduler
    /// once after a changed result. No render request is issued by this module.
    pub fn commit(&mut self, scene: &mut SceneState, camera: &mut Camera) -> Commit {
        let Some(active) = self.active.take() else {
            return Commit::NoChange;
        };
        match active {
            Active::Move {
                id,
                from,
                next,
                lab,
                camera: baseline,
            } => {
                if scene.lab != lab
                    || scene.get(id).is_none_or(|c| (c.x, c.y) != from)
                    || *camera != baseline
                {
                    self.cancels += 1;
                    return Commit::Cancelled;
                }
                if next == from {
                    return Commit::NoChange;
                }
                let Some(circle) = scene.get_mut(id) else {
                    return Commit::Cancelled;
                };
                circle.x = next.0;
                circle.y = next.1;
                if self.move_history.len() >= MAX_HISTORY {
                    self.move_history.remove(0);
                }
                self.move_history.push(MoveUndo {
                    id,
                    lab,
                    from,
                    to: next,
                });
                self.commits += 1;
                Commit::Moved(id)
            }
            Active::Pan { from, next } => {
                if *camera != from {
                    self.cancels += 1;
                    return Commit::Cancelled;
                }
                if from == next {
                    return Commit::NoChange;
                }
                *camera = next;
                self.commits += 1;
                Commit::Panned
            }
        }
    }
    /// Undo the most recent committed move only if its target remains at the
    /// committed state. External edits never get silently overwritten.
    pub fn undo_move(&mut self, scene: &mut SceneState) -> bool {
        if self.active.is_some() {
            return false;
        }
        let Some(last) = self.move_history.pop() else {
            return false;
        };
        if scene.lab != last.lab || scene.get(last.id).is_none_or(|c| (c.x, c.y) != last.to) {
            self.move_history.clear();
            return false;
        }
        if let Some(circle) = scene.get_mut(last.id) {
            circle.x = last.from.0;
            circle.y = last.from.1;
            return true;
        }
        false
    }
    /// When replacing the complete scene, prune stale move-undo authority.
    pub fn clear_history(&mut self) {
        self.cancel();
        self.move_history.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::scene::Lab;
    use crate::view::Rect;
    fn view(camera: Camera) -> View {
        View {
            rect: Rect {
                x0: 0.0,
                y0: 0.0,
                x1: 900.0,
                y1: 600.0,
            },
            camera,
        }
    }
    #[test]
    fn previews_are_absolute_and_only_one_canonical_commit() {
        let mut scene = SceneState::new(Lab::Primitive);
        let mut cam = Camera::default();
        let original = scene.clone();
        let id = scene.circles[0].id;
        let mut g = CanvasTransactions::new();
        assert!(g.begin(&scene, cam, Some(id)));
        assert!(g.preview(&scene, view(cam), Translation { x: 30.0, y: 0.0 }));
        assert!(g.preview(&scene, view(cam), Translation { x: 60.0, y: 12.0 }));
        assert_eq!(scene, original, "must not mutate scene on previews");
        assert_eq!(g.commits(), 0);
        let expect = (original.circles[0].x + 0.1, original.circles[0].y + 0.02);
        assert_eq!(g.preview_position(id), Some(expect));
        assert_eq!(g.commit(&mut scene, &mut cam), Commit::Moved(id));
        assert_eq!(scene.get(id).map(|c| (c.x, c.y)), Some(expect));
        assert_eq!(g.commits(), 1);
        assert_eq!(g.undo_count(), 1);
        assert!(g.undo_move(&mut scene));
        assert_eq!(scene, original);
        assert!(!g.undo_move(&mut scene));
    }
    #[test]
    fn pan_absolute_preview_does_not_change_canonical_camera() {
        let mut scene = SceneState::new(Lab::Csg);
        let mut cam = Camera::default();
        let mut g = CanvasTransactions::new();
        g.begin(&scene, cam, None);
        assert!(g.preview(&scene, view(cam), Translation { x: 30.0, y: -60.0 }));
        assert!(g.preview(&scene, view(cam), Translation { x: 60.0, y: -120.0 }));
        assert_eq!(cam, Camera::default());
        assert_eq!(g.preview_camera(cam).cx, -0.1);
        assert_eq!(g.preview_camera(cam).cy, 0.2);
        assert_eq!(g.commit(&mut scene, &mut cam), Commit::Panned);
        assert_eq!((cam.cx, cam.cy), (-0.1, 0.2));
        assert_eq!(g.commits(), 1);
    }
    #[test]
    fn focus_loss_and_escape_cancel_without_mutation() {
        let mut scene = SceneState::new(Lab::Smooth);
        let mut cam = Camera::default();
        let snapshot = scene.clone();
        let id = scene.circles[0].id;
        let mut g = CanvasTransactions::new();
        assert!(g.begin(&scene, cam, Some(id)));
        assert!(g.preview(&scene, view(cam), Translation { x: 60.0, y: 0.0 }));
        assert!(g.cancel());
        assert_eq!(g.commit(&mut scene, &mut cam), Commit::NoChange);
        assert_eq!(scene, snapshot);
        assert_eq!(g.cancellations(), 1);
    }
    #[test]
    fn stale_target_and_external_mutation_fail_closed() {
        let mut scene = SceneState::new(Lab::Primitive);
        let mut cam = Camera::default();
        let mut g = CanvasTransactions::new();
        let id = scene.circles[0].id;
        g.begin(&scene, cam, Some(id));
        g.preview(&scene, view(cam), Translation { x: 60.0, y: 0.0 });
        scene.get_mut(id).unwrap().x = 0.9;
        assert_eq!(g.commit(&mut scene, &mut cam), Commit::Cancelled);
        assert_eq!(scene.get(id).unwrap().x, 0.9);
        assert_eq!(g.commits(), 0);
    }
    #[test]
    fn invalid_deltas_cancel_not_commit() {
        let mut scene = SceneState::new(Lab::Primitive);
        let mut cam = Camera::default();
        let mut g = CanvasTransactions::new();
        g.begin(&scene, cam, Some(scene.circles[0].id));
        assert!(!g.preview(
            &scene,
            view(cam),
            Translation {
                x: f32::NAN,
                y: 0.0
            }
        ));
        assert_eq!(g.commit(&mut scene, &mut cam), Commit::NoChange);
        assert_eq!(g.cancellations(), 1);
    }
    #[test]
    fn external_edit_prevents_clobbering_undo() {
        let mut scene = SceneState::new(Lab::Primitive);
        let mut cam = Camera::default();
        let mut g = CanvasTransactions::new();
        let id = scene.circles[0].id;
        g.begin(&scene, cam, Some(id));
        g.preview(&scene, view(cam), Translation { x: 60.0, y: 0.0 });
        assert_eq!(g.commit(&mut scene, &mut cam), Commit::Moved(id));
        scene.get_mut(id).unwrap().x = 0.9;
        assert!(!g.undo_move(&mut scene));
        assert_eq!(scene.get(id).unwrap().x, 0.9);
    }
}
