//! 01H bounded simple concave polygons and rectangular frame holes.
//! No arbitrary holes, nesting, SVG even-odd, or self intersections.
use crate::fills::FillTriangle;
use crate::strokes::Point2;
use crate::{Rgba8, SceneError};
use blobin_ui_core::layout::Rect;
use blobin_ui_core::NodeId;

pub const MAX_SIMPLE_VERTICES: usize = 16;
fn cross(a: Point2, b: Point2, c: Point2) -> f64 {
    (f64::from(b.x) - f64::from(a.x)) * (f64::from(c.y) - f64::from(a.y))
        - (f64::from(b.y) - f64::from(a.y)) * (f64::from(c.x) - f64::from(a.x))
}
fn finite(p: Point2) -> bool {
    p.x.is_finite() && p.y.is_finite()
}
fn same(a: Point2, b: Point2) -> bool {
    a == b
}
fn on(a: Point2, b: Point2, p: Point2) -> bool {
    cross(a, b, p).abs() <= 1e-5
        && p.x >= a.x.min(b.x)
        && p.x <= a.x.max(b.x)
        && p.y >= a.y.min(b.y)
        && p.y <= a.y.max(b.y)
}
fn intersects(a: Point2, b: Point2, c: Point2, d: Point2) -> bool {
    let (p, q, r, s) = (
        cross(a, b, c),
        cross(a, b, d),
        cross(c, d, a),
        cross(c, d, b),
    );
    (p * q < 0. && r * s < 0.) || on(a, b, c) || on(a, b, d) || on(c, d, a) || on(c, d, b)
}
fn in_or_on(p: Point2, a: Point2, b: Point2, c: Point2, positive: bool) -> bool {
    let x = cross(a, b, p);
    let y = cross(b, c, p);
    let z = cross(c, a, p);
    if positive {
        x >= -1e-5 && y >= -1e-5 && z >= -1e-5
    } else {
        x <= 1e-5 && y <= 1e-5 && z <= 1e-5
    }
}
fn clip_valid(r: Rect) -> bool {
    [r.x, r.y, r.width, r.height, r.x + r.width, r.y + r.height]
        .iter()
        .all(|v| v.is_finite())
        && r.width > 0.
        && r.height > 0.
}
fn area(points: &[Point2]) -> f64 {
    (0..points.len())
        .map(|i| {
            let a = points[i];
            let b = points[(i + 1) % points.len()];
            f64::from(a.x) * f64::from(b.y) - f64::from(b.x) * f64::from(a.y)
        })
        .sum::<f64>()
        * 0.5
}
/// Ear clip a non-self-intersecting strictly non-collinear concave polygon.
/// No holes. Signed winding is preserved, and n-2 output triangles are
/// validated atomically before any caller receives them.
pub fn fill_simple_polygon(
    source: NodeId,
    points: &[Point2],
    clip: Rect,
    color: Rgba8,
) -> Result<Vec<FillTriangle>, SceneError> {
    if !(3..=MAX_SIMPLE_VERTICES).contains(&points.len())
        || !clip_valid(clip)
        || points.iter().copied().any(|p| !finite(p))
    {
        return Err(SceneError::InvalidBounds);
    }
    if points.windows(2).any(|v| same(v[0], v[1])) || same(points[0], points[points.len() - 1]) {
        return Err(SceneError::InvalidBounds);
    }
    for i in 0..points.len() {
        let a = points[i];
        let b = points[(i + 1) % points.len()];
        if same(a, b) || cross(points[(i + points.len() - 1) % points.len()], a, b).abs() < 1e-5 {
            return Err(SceneError::InvalidBounds);
        }
        for j in i + 1..points.len() {
            if j == i + 1 || (i == 0 && j == points.len() - 1) {
                continue;
            }
            if intersects(a, b, points[j], points[(j + 1) % points.len()]) {
                return Err(SceneError::InvalidBounds);
            }
        }
    }
    let signed = area(points);
    if !signed.is_finite() || signed.abs() < 1e-4 {
        return Err(SceneError::InvalidBounds);
    }
    let positive = signed > 0.;
    let mut remaining = (0..points.len()).collect::<Vec<_>>();
    let mut result = Vec::with_capacity(points.len() - 2);
    while remaining.len() > 3 {
        let mut ear = None;
        for i in 0..remaining.len() {
            let a = remaining[(i + remaining.len() - 1) % remaining.len()];
            let b = remaining[i];
            let c = remaining[(i + 1) % remaining.len()];
            let turn = cross(points[a], points[b], points[c]);
            if if positive {
                turn <= 1e-5
            } else {
                turn >= -1e-5
            } {
                continue;
            }
            if remaining.iter().any(|v| {
                *v != a
                    && *v != b
                    && *v != c
                    && in_or_on(points[*v], points[a], points[b], points[c], positive)
            }) {
                continue;
            }
            ear = Some((i, [points[a], points[b], points[c]]));
            break;
        }
        let (index, vertices) = ear.ok_or(SceneError::InvalidBounds)?;
        result.push(FillTriangle {
            source,
            vertices,
            clip,
            color,
        });
        remaining.remove(index);
    }
    result.push(FillTriangle {
        source,
        vertices: [
            points[remaining[0]],
            points[remaining[1]],
            points[remaining[2]],
        ],
        clip,
        color,
    });
    for triangle in &result {
        triangle.validated()?;
    }
    Ok(result)
}
/// A rectangular frame with ONE strictly interior rectangular hole.
/// This restriction is deliberate. Generates four disjoint strips
/// (each two triangles), leaving the central aperture *unpainted*.
pub fn fill_rectangular_frame(
    source: NodeId,
    outer: Rect,
    hole: Rect,
    clip: Rect,
    color: Rgba8,
) -> Result<Vec<FillTriangle>, SceneError> {
    if !clip_valid(outer)
        || !clip_valid(hole)
        || !clip_valid(clip)
        || hole.x <= outer.x
        || hole.y <= outer.y
        || hole.x + hole.width >= outer.x + outer.width
        || hole.y + hole.height >= outer.y + outer.height
    {
        return Err(SceneError::InvalidBounds);
    }
    let strips = [
        Rect::new(outer.x, outer.y, outer.width, hole.y - outer.y),
        Rect::new(outer.x, hole.y, hole.x - outer.x, hole.height),
        Rect::new(
            hole.x + hole.width,
            hole.y,
            outer.x + outer.width - (hole.x + hole.width),
            hole.height,
        ),
        Rect::new(
            outer.x,
            hole.y + hole.height,
            outer.width,
            outer.y + outer.height - (hole.y + hole.height),
        ),
    ];
    let mut result = Vec::with_capacity(8);
    for r in strips {
        let v = [
            Point2::new(r.x, r.y),
            Point2::new(r.x + r.width, r.y),
            Point2::new(r.x + r.width, r.y + r.height),
            Point2::new(r.x, r.y + r.height),
        ];
        result.extend(fill_simple_polygon(source, &v, clip, color)?);
    }
    Ok(result)
}
#[cfg(test)]
mod tests {
    use super::*;
    fn node() -> NodeId {
        NodeId {
            slot: 2,
            generation: 1,
        }
    }
    fn clip() -> Rect {
        Rect::new(0., 0., 1000., 1000.)
    }
    fn col() -> Rgba8 {
        Rgba8::new(30, 110, 230, 255)
    }
    fn concave() -> [Point2; 6] {
        [
            Point2::new(100., 100.),
            Point2::new(220., 100.),
            Point2::new(220., 140.),
            Point2::new(160., 140.),
            Point2::new(160., 220.),
            Point2::new(100., 220.),
        ]
    }
    #[test]
    fn l_shape_and_reverse_winding_triangulate_n_minus_two() {
        let v = concave();
        let r = fill_simple_polygon(node(), &v, clip(), col()).unwrap();
        assert_eq!(r.len(), 4);
        assert_eq!(r, fill_simple_polygon(node(), &v, clip(), col()).unwrap());
        let reversed = v.iter().copied().rev().collect::<Vec<_>>();
        assert_eq!(
            fill_simple_polygon(node(), &reversed, clip(), col())
                .unwrap()
                .len(),
            4
        );
        assert!(r.iter().all(|t| t.source == node()));
    }
    #[test]
    fn frame_has_eight_triangles_and_strictly_empty_hole() {
        let outer = Rect::new(300., 100., 160., 160.);
        let hole = Rect::new(340., 140., 80., 80.);
        let a = fill_rectangular_frame(node(), outer, hole, clip(), col()).unwrap();
        assert_eq!(a.len(), 8);
        assert_eq!(
            a,
            fill_rectangular_frame(node(), outer, hole, clip(), col()).unwrap()
        );
        assert_eq!(
            fill_rectangular_frame(node(), outer, outer, clip(), col()),
            Err(SceneError::InvalidBounds)
        );
    }
    #[test]
    fn bowtie_nan_and_duplicate_edges_fail_closed() {
        let bow = [
            Point2::new(10., 10.),
            Point2::new(90., 90.),
            Point2::new(10., 90.),
            Point2::new(90., 10.),
        ];
        assert_eq!(
            fill_simple_polygon(node(), &bow, clip(), col()),
            Err(SceneError::InvalidBounds)
        );
        let mut broken = concave();
        broken[0].x = f32::NAN;
        assert_eq!(
            fill_simple_polygon(node(), &broken, clip(), col()),
            Err(SceneError::InvalidBounds)
        );
        assert_eq!(
            fill_simple_polygon(node(), &[Point2::new(3., 3.); 17], clip(), col()),
            Err(SceneError::InvalidBounds)
        );
        let v = concave();
        let closed = [v[0], v[1], v[2], v[3], v[4], v[5], v[0]];
        assert_eq!(
            fill_simple_polygon(node(), &closed, clip(), col()),
            Err(SceneError::InvalidBounds)
        );
    }
}

/// BLOB-UI-01I: explicit EvenOdd membership for axis-aligned rectangular
/// outer contour and at most two disjoint inner rectangular contours. The
/// grid-cell tiling is deterministic and does not use stencil/alpha cutouts.
/// Holes must be non-overlapping and strictly inside. No arbitrary winding.
pub fn fill_rectangular_even_odd(
    source: NodeId,
    outer: Rect,
    holes: &[Rect],
    clip: Rect,
    color: Rgba8,
) -> Result<Vec<FillTriangle>, SceneError> {
    if !clip_valid(outer) || !clip_valid(clip) || holes.is_empty() || holes.len() > 2 {
        return Err(SceneError::InvalidBounds);
    }
    for (i, h) in holes.iter().enumerate() {
        if !clip_valid(*h)
            || h.x <= outer.x
            || h.y <= outer.y
            || h.x + h.width >= outer.x + outer.width
            || h.y + h.height >= outer.y + outer.height
        {
            return Err(SceneError::InvalidBounds);
        }
        for other in holes.iter().skip(i + 1) {
            if h.x < other.x + other.width
                && h.x + h.width > other.x
                && h.y < other.y + other.height
                && h.y + h.height > other.y
            {
                return Err(SceneError::InvalidBounds);
            }
        }
    }
    let mut xs = vec![outer.x, outer.x + outer.width];
    let mut ys = vec![outer.y, outer.y + outer.height];
    for h in holes {
        xs.extend([h.x, h.x + h.width]);
        ys.extend([h.y, h.y + h.height]);
    }
    xs.sort_by(f32::total_cmp);
    ys.sort_by(f32::total_cmp);
    xs.dedup();
    ys.dedup();
    let mut result = Vec::new();
    for x in xs.windows(2) {
        for y in ys.windows(2) {
            let cx = (f64::from(x[0]) + f64::from(x[1])) / 2.;
            let cy = (f64::from(y[0]) + f64::from(y[1])) / 2.;
            if holes.iter().any(|h| {
                cx > f64::from(h.x)
                    && cx < f64::from(h.x + h.width)
                    && cy > f64::from(h.y)
                    && cy < f64::from(h.y + h.height)
            }) {
                continue;
            }
            let v = [
                Point2::new(x[0], y[0]),
                Point2::new(x[1], y[0]),
                Point2::new(x[1], y[1]),
                Point2::new(x[0], y[1]),
            ];
            result.extend(fill_simple_polygon(source, &v, clip, color)?);
            if result.len() > 64 {
                return Err(SceneError::InvalidBounds);
            }
        }
    }
    if result.is_empty() {
        Err(SceneError::Invisible)
    } else {
        Ok(result)
    }
}
#[cfg(test)]
mod even_odd_tests {
    use super::*;
    #[test]
    fn two_disjoint_holes_deterministic_and_invalid_cases_fail_closed() {
        let id = NodeId {
            slot: 4,
            generation: 1,
        };
        let outer = Rect::new(700., 110., 260., 150.);
        let h1 = Rect::new(745., 145., 40., 50.);
        let h2 = Rect::new(840., 165., 50., 55.);
        let clip = Rect::new(0., 0., 1280., 800.);
        let c = Rgba8::new(180, 80, 210, 255);
        let r = fill_rectangular_even_odd(id, outer, &[h1, h2], clip, c).unwrap();
        assert_eq!(
            r,
            fill_rectangular_even_odd(id, outer, &[h1, h2], clip, c).unwrap()
        );
        assert_eq!(r.len(), 42);
        assert!(r.iter().all(|t| t.source == id));
        assert_eq!(
            fill_rectangular_even_odd(id, outer, &[h1, h1], clip, c),
            Err(SceneError::InvalidBounds)
        );
        assert_eq!(
            fill_rectangular_even_odd(id, outer, &[], clip, c),
            Err(SceneError::InvalidBounds)
        );
        assert_eq!(
            fill_rectangular_even_odd(id, outer, &[outer], clip, c),
            Err(SceneError::InvalidBounds)
        );
    }
}
