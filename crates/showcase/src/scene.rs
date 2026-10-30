//! Editable scene state on the surface side. This is a list of control values
//! (circle centres, radii, operators) that the runtime evaluates; the surface
//! never evaluates the field itself.

use blob_frame::{CsgOp, Primitive, ViewMode, COORD_LIMIT, MAX_RADIUS};

/// Practical cap for the editor; the contract allows 64.
pub const MAX_UI_PRIMITIVES: usize = 24;
pub const MIN_RADIUS: f32 = 0.01;
pub const MIN_ZOOM: f32 = 0.25;
pub const MAX_ZOOM: f32 = 4.0;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Lab {
    Primitive,
    Csg,
    Smooth,
    Field,
    Normal,
    Material,
}

impl Lab {
    pub const ALL: [Lab; 6] = [Lab::Primitive, Lab::Csg, Lab::Smooth, Lab::Field, Lab::Normal, Lab::Material];

    pub fn name(self) -> &'static str {
        match self {
            Lab::Primitive => "Primitive Lab",
            Lab::Csg => "CSG Lab",
            Lab::Smooth => "Smooth Lab",
            Lab::Field => "Field Inspector",
            Lab::Normal => "Normal Inspector",
            Lab::Material => "Material Preview",
        }
    }

    pub fn blurb(self) -> &'static str {
        match self {
            Lab::Primitive => "Cercles élémentaires combinés par union.",
            Lab::Csg => "Union, soustraction et intersection, évaluées de gauche à droite.",
            Lab::Smooth => "Union lisse (k = 0,08, fixé par le moteur) : transitions organiques.",
            Lab::Field => "Distance signée colorée par le runtime. Le champ est exprimé en unités de vue.",
            Lab::Normal => "Normales par différences finies du champ, encodées en couleur.",
            Lab::Material => {
                "Ombrage dérivé des normales calculées : post-traitement 2D, pas un rendu 3D ni un matériau physique."
            }
        }
    }

    pub fn default_view(self) -> ViewMode {
        match self {
            Lab::Primitive | Lab::Csg => ViewMode::Coverage,
            Lab::Smooth | Lab::Material => ViewMode::Lit,
            Lab::Field => ViewMode::Distance,
            Lab::Normal => ViewMode::Normals,
        }
    }

    fn circles(self) -> Vec<(f32, f32, f32, CsgOp)> {
        use CsgOp::*;
        match self {
            Lab::Primitive => vec![(-0.26, 0.0, 0.10, Union), (0.0, 0.0, 0.14, Union), (0.27, 0.02, 0.08, Union)],
            Lab::Csg | Lab::Field => vec![
                (0.0, 0.0, 0.27, Union),
                (0.03, 0.0, 0.13, Subtract),
                (-0.18, -0.05, 0.30, Intersect),
                (0.24, 0.08, 0.12, Union),
            ],
            Lab::Smooth | Lab::Normal | Lab::Material => vec![
                (0.0, 0.0, 0.14, Union),
                (-0.14, -0.05, 0.11, SmoothUnion),
                (0.13, 0.07, 0.12, SmoothUnion),
                (-0.025, 0.14, 0.10, SmoothUnion),
                (0.08, -0.14, 0.11, SmoothUnion),
            ],
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Circle {
    pub id: u32,
    pub x: f32,
    pub y: f32,
    pub radius: f32,
    pub op: CsgOp,
}

/// World → engine: e = (w - centre) * zoom. Applied on the surface because
/// BLOB-FRAME-v1 carries no camera.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Camera {
    pub cx: f32,
    pub cy: f32,
    pub zoom: f32,
}

impl Default for Camera {
    fn default() -> Self {
        Self { cx: 0.0, cy: 0.0, zoom: 1.0 }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct SceneState {
    pub lab: Lab,
    pub circles: Vec<Circle>,
    pub selected: Option<u32>,
    next_id: u32,
}

impl SceneState {
    pub fn new(lab: Lab) -> Self {
        let circles: Vec<Circle> = lab
            .circles()
            .into_iter()
            .enumerate()
            .map(|(i, (x, y, radius, op))| Circle { id: i as u32 + 1, x, y, radius, op })
            .collect();
        let next_id = circles.len() as u32 + 1;
        Self { lab, circles, selected: None, next_id }
    }

    pub fn get(&self, id: u32) -> Option<&Circle> {
        self.circles.iter().find(|c| c.id == id)
    }

    pub fn get_mut(&mut self, id: u32) -> Option<&mut Circle> {
        self.circles.iter_mut().find(|c| c.id == id)
    }

    pub fn index_of(&self, id: u32) -> Option<usize> {
        self.circles.iter().position(|c| c.id == id)
    }

    /// The circle under `p` (world units), topmost (last evaluated) first.
    /// `tol` widens the pick area so that thin rings stay grabbable.
    pub fn hit(&self, p: (f32, f32), tol: f32) -> Option<u32> {
        self.circles
            .iter()
            .rev()
            .find(|c| ((p.0 - c.x).powi(2) + (p.1 - c.y).powi(2)).sqrt() <= c.radius + tol)
            .map(|c| c.id)
    }

    pub fn add(&mut self, at: (f32, f32), op: CsgOp) -> Option<u32> {
        if self.circles.len() >= MAX_UI_PRIMITIVES {
            return None;
        }
        let id = self.next_id;
        self.next_id += 1;
        let op = if self.circles.is_empty() { CsgOp::Union } else { op };
        self.circles.push(Circle { id, x: at.0, y: at.1, radius: 0.08, op });
        Some(id)
    }

    /// The last circle cannot be removed; the new first circle becomes a union.
    pub fn remove(&mut self, id: u32) -> bool {
        if self.circles.len() <= 1 {
            return false;
        }
        let Some(i) = self.index_of(id) else { return false };
        self.circles.remove(i);
        self.circles[0].op = CsgOp::Union;
        if self.selected == Some(id) {
            self.selected = None;
        }
        true
    }

    /// Cycles the operator of a circle. The first circle is always a union.
    pub fn cycle_op(&mut self, id: u32) -> bool {
        match self.index_of(id) {
            Some(0) | None => false,
            Some(i) => {
                let c = &mut self.circles[i];
                let k = CsgOp::ALL.iter().position(|o| *o == c.op).unwrap_or(0);
                c.op = CsgOp::ALL[(k + 1) % CsgOp::ALL.len()];
                true
            }
        }
    }

    pub fn set_radius(&mut self, id: u32, r: f32) -> bool {
        match self.get_mut(id) {
            Some(c) => {
                c.radius = r.clamp(MIN_RADIUS, 1.0);
                true
            }
            None => false,
        }
    }

    /// Wire primitives for `camera`, or why the view cannot be expressed within the
    /// contract bounds (centres in [-2, 2], radius in (0, 2]).
    pub fn to_wire(&self, cam: &Camera) -> Result<Vec<Primitive>, String> {
        self.circles
            .iter()
            .map(|c| {
                let p = Primitive {
                    x: (c.x - cam.cx) * cam.zoom,
                    y: (c.y - cam.cy) * cam.zoom,
                    radius: c.radius * cam.zoom,
                    op: c.op,
                };
                let inside = |v: f32| (-COORD_LIMIT..=COORD_LIMIT).contains(&v);
                if !inside(p.x) || !inside(p.y) || !(p.radius > 0.0 && p.radius <= MAX_RADIUS) {
                    Err(format!(
                        "le cercle {} sort des bornes du contrat (|x|, |y| ≤ {COORD_LIMIT}, r ≤ {MAX_RADIUS}) à ce zoom : dézoomer ou recentrer",
                        c.id
                    ))
                } else {
                    Ok(p)
                }
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn labs_are_valid_scenes() {
        for lab in Lab::ALL {
            let s = SceneState::new(lab);
            let wire = s.to_wire(&Camera::default()).unwrap();
            assert_eq!(wire[0].op, CsgOp::Union, "{lab:?}");
            assert!(wire.len() <= MAX_UI_PRIMITIVES);
        }
    }

    #[test]
    fn camera_transform_and_bounds() {
        let s = SceneState::new(Lab::Primitive);
        let cam = Camera { cx: 0.1, cy: -0.2, zoom: 2.0 };
        let w = s.to_wire(&cam).unwrap();
        let c = s.circles[1];
        assert_eq!((w[1].x, w[1].y, w[1].radius), ((c.x - 0.1) * 2.0, (c.y + 0.2) * 2.0, c.radius * 2.0));
        assert!(s.to_wire(&Camera { cx: 1.5, cy: 0.0, zoom: 4.0 }).is_err());
    }

    #[test]
    fn editing_keeps_the_first_circle_a_union() {
        let mut s = SceneState::new(Lab::Csg);
        let first = s.circles[0].id;
        assert!(!s.cycle_op(first));
        let second = s.circles[1].id;
        assert!(s.cycle_op(second));
        assert!(s.remove(first));
        assert_eq!(s.circles[0].op, CsgOp::Union);
        while s.circles.len() > 1 {
            let id = s.circles[0].id;
            assert!(s.remove(id));
        }
        assert!(!s.remove(s.circles[0].id), "the last circle stays");
        while s.add((0.0, 0.0), CsgOp::Subtract).is_some() {}
        assert_eq!(s.circles.len(), MAX_UI_PRIMITIVES);
    }

    #[test]
    fn hit_prefers_topmost() {
        let mut s = SceneState::new(Lab::Primitive);
        let top = s.add((0.0, 0.0), CsgOp::Union).unwrap();
        assert_eq!(s.hit((0.0, 0.0), 0.0), Some(top));
        assert_eq!(s.hit((-0.26, 0.0), 0.0), Some(1));
        assert_eq!(s.hit((0.45, 0.45), 0.0), None);
    }
}
