//! 01G bounded *convex* closed paths. No SVG winding, concave triangulation,
//! holes, self-intersections, Bézier fills or general path booleans.
use crate::strokes::{stroke_polyline, Point2, StrokeSegment};
use crate::{Rgba8, SceneError, UiTransform2D};
use blobin_ui_core::layout::Rect;
use blobin_ui_core::NodeId;

pub const MAX_CONVEX_VERTICES: usize = 16;
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct FillTriangle {
    pub source: NodeId,
    pub vertices: [Point2; 3],
    pub clip: Rect,
    pub color: Rgba8,
}
fn finite(p: Point2) -> bool {
    p.x.is_finite() && p.y.is_finite()
}
fn valid_clip(r: Rect) -> bool {
    [r.x, r.y, r.width, r.height, r.x + r.width, r.y + r.height]
        .iter()
        .all(|n| n.is_finite())
        && r.width >= 0.
        && r.height >= 0.
}
fn cross(a: Point2, b: Point2, c: Point2) -> f64 {
    let (ax, ay) = (f64::from(a.x), f64::from(a.y));
    let (bx, by) = (f64::from(b.x), f64::from(b.y));
    let (cx, cy) = (f64::from(c.x), f64::from(c.y));
    (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
}
fn touches_segment(a: Point2, b: Point2, p: Point2) -> bool {
    cross(a, b, p).abs() <= 0.0001
        && f64::from(p.x) >= f64::from(a.x.min(b.x))
        && f64::from(p.x) <= f64::from(a.x.max(b.x))
        && f64::from(p.y) >= f64::from(a.y.min(b.y))
        && f64::from(p.y) <= f64::from(a.y.max(b.y))
}
fn crosses(a: Point2, b: Point2, c: Point2, d: Point2) -> bool {
    let (o1, o2, o3, o4) = (
        cross(a, b, c),
        cross(a, b, d),
        cross(c, d, a),
        cross(c, d, b),
    );
    (o1 * o2 < 0. && o3 * o4 < 0.)
        || touches_segment(a, b, c)
        || touches_segment(a, b, d)
        || touches_segment(c, d, a)
        || touches_segment(c, d, b)
}
impl FillTriangle {
    pub fn bounds(self) -> Result<Rect, SceneError> {
        if !self.vertices.iter().copied().all(finite) {
            return Err(SceneError::InvalidBounds);
        }
        let minx = self
            .vertices
            .iter()
            .map(|p| p.x)
            .fold(f32::INFINITY, f32::min);
        let miny = self
            .vertices
            .iter()
            .map(|p| p.y)
            .fold(f32::INFINITY, f32::min);
        let maxx = self
            .vertices
            .iter()
            .map(|p| p.x)
            .fold(f32::NEG_INFINITY, f32::max);
        let maxy = self
            .vertices
            .iter()
            .map(|p| p.y)
            .fold(f32::NEG_INFINITY, f32::max);
        let r = Rect::new(minx, miny, maxx - minx, maxy - miny);
        if !valid_clip(r) || r.width == 0. || r.height == 0. {
            Err(SceneError::InvalidBounds)
        } else {
            Ok(r)
        }
    }
    pub fn validated(self) -> Result<(), SceneError> {
        if !valid_clip(self.clip)
            || cross(self.vertices[0], self.vertices[1], self.vertices[2]).abs() < 0.0001
        {
            return Err(SceneError::InvalidBounds);
        }
        let bounds = self.bounds()?;
        let visible = bounds.intersect(self.clip);
        if visible.width == 0. || visible.height == 0. {
            Err(SceneError::Invisible)
        } else {
            Ok(())
        }
    }
    pub fn transformed(self, t: UiTransform2D, parents: &[Rect]) -> Result<Self, SceneError> {
        t.checked()?;
        if parents.iter().any(|r| !valid_clip(*r)) {
            return Err(SceneError::InvalidBounds);
        }
        let mut copy = Self {
            vertices: self
                .vertices
                .map(|p| Point2::new(p.x * t.sx + t.tx, p.y * t.sy + t.ty)),
            clip: t.rect(self.clip)?,
            ..self
        };
        for parent in parents {
            copy.clip = copy.clip.intersect(*parent);
        }
        copy.validated()?;
        Ok(copy)
    }
}
fn checked_polygon(points: &[Point2], clip: Rect) -> Result<(), SceneError> {
    if !(3..=MAX_CONVEX_VERTICES).contains(&points.len())
        || !valid_clip(clip)
        || points.iter().copied().any(|p| !finite(p))
    {
        return Err(SceneError::InvalidBounds);
    }
    let mut sign = 0i8;
    for i in 0..points.len() {
        let turn = cross(
            points[i],
            points[(i + 1) % points.len()],
            points[(i + 2) % points.len()],
        );
        if !turn.is_finite() || turn.abs() <= 0.0001 {
            return Err(SceneError::InvalidBounds);
        }
        let this = if turn > 0. { 1 } else { -1 };
        if sign != 0 && sign != this {
            return Err(SceneError::InvalidBounds);
        }
        sign = this;
    }
    // Local winding alone is insufficient: star polygons can have all turns
    // of the same sign while non-adjacent edges still cross.
    for i in 0..points.len() {
        for j in i + 1..points.len() {
            if j == i + 1 || (i == 0 && j == points.len() - 1) {
                continue;
            }
            if crosses(
                points[i],
                points[(i + 1) % points.len()],
                points[j],
                points[(j + 1) % points.len()],
            ) {
                return Err(SceneError::InvalidBounds);
            }
        }
    }
    Ok(())
}
/// Strictly convex, simple, ordered polygon, explicitly OPEN point sequence.
/// CW and CCW are accepted; the last vertex must not repeat the first.
/// The fan contains n-2 independent GPU triangle commands; no implicit
/// tessellation in the renderer. Internal edges have no AA in 01G.
pub fn fill_convex_path(
    source: NodeId,
    points: &[Point2],
    clip: Rect,
    color: Rgba8,
) -> Result<Vec<FillTriangle>, SceneError> {
    checked_polygon(points, clip)?;
    let mut result = Vec::with_capacity(points.len() - 2);
    for i in 1..points.len() - 1 {
        let tri = FillTriangle {
            source,
            vertices: [points[0], points[i], points[i + 1]],
            clip,
            color,
        };
        tri.validated()?;
        result.push(tri);
    }
    Ok(result)
}
/// Closed outline with round joins constructed as the union of capsules.
/// Opaque colors only: translucent overdraw at joins is not qualified.
/// No miter/bevel/butt cap styles, per-segment antialias or non-convex loops.
pub fn stroke_closed_convex_path(
    source: NodeId,
    points: &[Point2],
    width: f32,
    clip: Rect,
    color: Rgba8,
) -> Result<Vec<StrokeSegment>, SceneError> {
    checked_polygon(points, clip)?;
    if color.a != 255 {
        return Err(SceneError::InvalidBounds);
    }
    let mut chain = points.to_vec();
    chain.push(points[0]);
    stroke_polyline(source, &chain, width, clip, color)
}
#[cfg(test)]
mod tests {
    use super::*;
    fn id() -> NodeId {
        NodeId {
            slot: 8,
            generation: 3,
        }
    }
    fn clip() -> Rect {
        Rect::new(0., 0., 500., 400.)
    }
    fn color() -> Rgba8 {
        Rgba8::new(25, 90, 220, 255)
    }
    fn square() -> [Point2; 4] {
        [
            Point2::new(10., 10.),
            Point2::new(90., 10.),
            Point2::new(90., 70.),
            Point2::new(10., 70.),
        ]
    }
    #[test]
    fn two_triangle_fan_and_round_closed_outline_are_deterministic() {
        let v = square();
        let tris = fill_convex_path(id(), &v, clip(), color()).unwrap();
        assert_eq!(tris.len(), 2);
        assert_eq!(tris, fill_convex_path(id(), &v, clip(), color()).unwrap());
        assert_eq!(tris[0].source, id());
        assert_eq!(tris[0].vertices, [v[0], v[1], v[2]]);
        assert_eq!(tris[1].vertices, [v[0], v[2], v[3]]);
        let border = stroke_closed_convex_path(id(), &v, 5., clip(), color()).unwrap();
        assert_eq!(border.len(), 4);
        assert_eq!(border[3].end, v[0]);
        assert_eq!(border[0].start, v[0]);
    }
    #[test]
    fn winding_reversal_keeps_coverage_and_concavity_fails_closed() {
        let v = square();
        let rev = [v[3], v[2], v[1], v[0]];
        assert_eq!(
            fill_convex_path(id(), &rev, clip(), color()).unwrap().len(),
            2
        );
        let concave = [
            Point2::new(10., 10.),
            Point2::new(100., 10.),
            Point2::new(35., 35.),
            Point2::new(100., 100.),
            Point2::new(10., 100.),
        ];
        assert_eq!(
            fill_convex_path(id(), &concave, clip(), color()),
            Err(SceneError::InvalidBounds)
        );
        let repeated = [v[0], v[1], v[2], v[3], v[0]];
        assert_eq!(
            fill_convex_path(id(), &repeated, clip(), color()),
            Err(SceneError::InvalidBounds)
        );
    }
    #[test]
    fn star_with_same_local_winding_is_still_rejected() {
        // Pentagram point order makes each local turn positive while its
        // diagonals self-intersect. Must not triangulate this as convex.
        let r = 35f32;
        let vertices = (0..5)
            .map(|i| {
                let theta =
                    (-std::f32::consts::FRAC_PI_2) + (i as f32) * 2. * std::f32::consts::PI / 5.;
                Point2::new(200. + r * theta.cos(), 200. + r * theta.sin())
            })
            .collect::<Vec<_>>();
        let star = [
            vertices[0],
            vertices[2],
            vertices[4],
            vertices[1],
            vertices[3],
        ];
        assert_eq!(
            fill_convex_path(id(), &star, clip(), color()),
            Err(SceneError::InvalidBounds)
        );
    }
    #[test]
    fn reject_translucent_outline_nan_degenerate_and_out_of_view() {
        let v = square();
        assert_eq!(
            stroke_closed_convex_path(id(), &v, 3., clip(), Rgba8::new(1, 2, 3, 100)),
            Err(SceneError::InvalidBounds)
        );
        assert_eq!(
            fill_convex_path(id(), &v, Rect::new(600., 600., 20., 20.), color()),
            Err(SceneError::Invisible)
        );
        let mut broken = v;
        broken[1].x = f32::NAN;
        assert_eq!(
            fill_convex_path(id(), &broken, clip(), color()),
            Err(SceneError::InvalidBounds)
        );
        let collinear = [
            Point2::new(10., 10.),
            Point2::new(20., 20.),
            Point2::new(30., 30.),
        ];
        assert_eq!(
            fill_convex_path(id(), &collinear, clip(), color()),
            Err(SceneError::InvalidBounds)
        );
        assert_eq!(
            fill_convex_path(id(), &[v[0]; 17], clip(), color()),
            Err(SceneError::InvalidBounds)
        );
    }
    #[test]
    fn transforms_and_nested_clip_preserve_identity_and_bounds() {
        let original = fill_convex_path(id(), &square(), clip(), color()).unwrap()[0];
        let transformed = original
            .transformed(
                UiTransform2D {
                    sx: 2.,
                    sy: 1.5,
                    tx: 3.,
                    ty: 4.,
                },
                &[Rect::new(0., 0., 180., 150.)],
            )
            .unwrap();
        assert_eq!(transformed.source, id());
        assert_eq!(transformed.vertices[0], Point2::new(23., 19.));
        assert_eq!(transformed.clip, Rect::new(3., 4., 177., 146.));
    }
}
