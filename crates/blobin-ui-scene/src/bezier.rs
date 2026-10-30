//! Deterministic first-party adaptive Bézier subdivision into the existing
//! stroked segments. This is a stroke *centerline* approximation only.
//! Convex-hull flatness bound is in logical pixels BEFORE G03 transforms.
//! Not arbitrary path fills, exact joins, rotation or device-pixel quality.
use crate::strokes::{stroke_polyline, Point2, StrokeSegment};
use crate::{Rgba8, SceneError};
use blobin_ui_core::layout::Rect;
use blobin_ui_core::NodeId;

pub const MAX_BEZIER_DEPTH: u8 = 12;
pub const MAX_BEZIER_SEGMENTS: usize = 64;
pub const MIN_TOLERANCE: f32 = 0.125;
pub const MAX_TOLERANCE: f32 = 8.0;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum BezierCurve {
    Quadratic([Point2; 3]),
    Cubic([Point2; 4]),
}
impl BezierCurve {
    pub fn first(self) -> Point2 {
        match self {
            Self::Quadratic(v) => v[0],
            Self::Cubic(v) => v[0],
        }
    }
    pub fn last(self) -> Point2 {
        match self {
            Self::Quadratic(v) => v[2],
            Self::Cubic(v) => v[3],
        }
    }
    fn controls(self) -> Vec<Point2> {
        match self {
            Self::Quadratic(v) => v.to_vec(),
            Self::Cubic(v) => v.to_vec(),
        }
    }
}
fn finite(p: Point2) -> bool {
    p.x.is_finite() && p.y.is_finite()
}
fn dist_from_chord(point: Point2, a: Point2, b: Point2) -> f64 {
    let dx = f64::from(b.x) - f64::from(a.x);
    let dy = f64::from(b.y) - f64::from(a.y);
    let px = f64::from(point.x) - f64::from(a.x);
    let py = f64::from(point.y) - f64::from(a.y);
    let denom = dx.hypot(dy);
    if denom == 0.0 {
        return px.hypot(py);
    }
    // Distance to the segment, not the infinite supporting line. This
    // ensures a bound even when control points project past the endpoints.
    let t = ((px * dx + py * dy) / (denom * denom)).clamp(0.0, 1.0);
    (px - t * dx).hypot(py - t * dy)
}
fn flat_enough(points: &[Point2], tolerance: f32) -> bool {
    let first = points[0];
    let last = points[points.len() - 1];
    points[1..points.len() - 1]
        .iter()
        .all(|p| dist_from_chord(*p, first, last) <= f64::from(tolerance))
}
fn mid(a: Point2, b: Point2) -> Point2 {
    Point2::new(a.x * 0.5 + b.x * 0.5, a.y * 0.5 + b.y * 0.5)
}
fn split(points: &[Point2]) -> (Vec<Point2>, Vec<Point2>) {
    // De Casteljau at t=1/2, deterministic in ordered f32 arithmetic.
    let mut row = points.to_vec();
    let mut left = vec![row[0]];
    let mut right = vec![row[row.len() - 1]];
    while row.len() > 1 {
        row = row.windows(2).map(|a| mid(a[0], a[1])).collect();
        left.push(row[0]);
        right.push(row[row.len() - 1]);
    }
    right.reverse();
    (left, right)
}
fn flatten(
    points: &[Point2],
    tol: f32,
    depth: u8,
    out: &mut Vec<Point2>,
    segment_limit: usize,
) -> Result<(), SceneError> {
    if flat_enough(points, tol) {
        let end = *points.last().ok_or(SceneError::InvalidBounds)?;
        if out.last() == Some(&end) {
            return Err(SceneError::InvalidBounds);
        }
        if out.len() > segment_limit {
            return Err(SceneError::InvalidBounds);
        }
        out.push(end);
        return Ok(());
    }
    if depth >= MAX_BEZIER_DEPTH {
        return Err(SceneError::InvalidBounds);
    }
    let (left, right) = split(points);
    flatten(&left, tol, depth + 1, out, segment_limit)?;
    flatten(&right, tol, depth + 1, out, segment_limit)
}
/// Flatten one quadratic or cubic stroke into *bounded* native line segments.
/// Fails closed for invalid/nonfinite geometry, degenerate segments, excessive
/// subdivisions, or a tolerance smaller than bounded depth can satisfy.
/// No partial result is exposed on failure.
#[allow(clippy::too_many_arguments)]
pub fn stroke_bezier(
    source: NodeId,
    curve: BezierCurve,
    width: f32,
    clip: Rect,
    color: Rgba8,
    tolerance: f32,
    max_segments: usize,
) -> Result<Vec<StrokeSegment>, SceneError> {
    if !tolerance.is_finite()
        || !(MIN_TOLERANCE..=MAX_TOLERANCE).contains(&tolerance)
        || !(1..=MAX_BEZIER_SEGMENTS).contains(&max_segments)
    {
        return Err(SceneError::InvalidBounds);
    }
    let points = curve.controls();
    if points.iter().any(|p| !finite(*p)) {
        return Err(SceneError::InvalidBounds);
    }
    let mut polyline = vec![curve.first()];
    flatten(&points, tolerance, 0, &mut polyline, max_segments)?;
    if polyline.len() - 1 > max_segments {
        return Err(SceneError::InvalidBounds);
    }
    stroke_polyline(source, &polyline, width, clip, color)
}
#[cfg(test)]
mod tests {
    use super::*;
    fn source() -> NodeId {
        NodeId {
            slot: 3,
            generation: 1,
        }
    }
    fn clip() -> Rect {
        Rect::new(0., 0., 500., 400.)
    }
    fn color() -> Rgba8 {
        Rgba8::new(20, 230, 150, 255)
    }
    fn quad() -> BezierCurve {
        BezierCurve::Quadratic([
            Point2::new(100., 100.),
            Point2::new(140., 180.),
            Point2::new(180., 100.),
        ])
    }
    fn cubic() -> BezierCurve {
        BezierCurve::Cubic([
            Point2::new(200., 100.),
            Point2::new(220., 200.),
            Point2::new(260., 20.),
            Point2::new(280., 100.),
        ])
    }
    fn run(c: BezierCurve, tol: f32, max: usize) -> Result<Vec<StrokeSegment>, SceneError> {
        stroke_bezier(source(), c, 6., clip(), color(), tol, max)
    }
    #[test]
    fn deterministic_quadratic_and_cubic_provenance() {
        for curve in [quad(), cubic()] {
            let a = run(curve, 0.75, 64).unwrap();
            assert_eq!(a, run(curve, 0.75, 64).unwrap());
            assert!(a.len() > 2);
            assert_eq!(a.first().unwrap().start, curve.first());
            assert_eq!(a.last().unwrap().end, curve.last());
            assert!(a.iter().all(|s| s.source == source() && s.width == 6.));
            for segment in a.windows(2) {
                assert_eq!(segment[0].end, segment[1].start);
            }
        }
    }
    #[test]
    fn collinear_control_points_produce_exact_one_segment() {
        let c = BezierCurve::Cubic([
            Point2::new(10., 10.),
            Point2::new(30., 30.),
            Point2::new(40., 40.),
            Point2::new(70., 70.),
        ]);
        assert_eq!(run(c, 0.125, 64).unwrap().len(), 1);
    }
    #[test]
    fn invalid_inputs_and_limits_fail_closed() {
        assert_eq!(run(quad(), f32::NAN, 64), Err(SceneError::InvalidBounds));
        assert_eq!(run(cubic(), 0., 64), Err(SceneError::InvalidBounds));
        assert_eq!(run(quad(), 0.75, 0), Err(SceneError::InvalidBounds));
        assert_eq!(run(quad(), 0.75, 65), Err(SceneError::InvalidBounds));
        assert_eq!(run(quad(), 0.125, 1), Err(SceneError::InvalidBounds));
        assert_eq!(
            run(
                BezierCurve::Quadratic([
                    Point2::new(10., 10.),
                    Point2::new(f32::INFINITY, 20.),
                    Point2::new(40., 30.)
                ]),
                1.,
                64
            ),
            Err(SceneError::InvalidBounds)
        );
        assert_eq!(
            run(BezierCurve::Cubic([Point2::new(5., 5.); 4]), 1., 64),
            Err(SceneError::InvalidBounds)
        );
    }
    #[test]
    fn flatness_is_bounded_by_segment_tolerance() {
        for curve in [quad(), cubic()] {
            let path = run(curve, 0.5, 64).unwrap();
            // Independently sample the exact Bernstein curve, compare
            // against the nearest polyline segment (a conservative check).
            for k in 0..=256 {
                let t = k as f64 / 256.;
                let pt = match curve {
                    BezierCurve::Quadratic(v) => {
                        let a = (1. - t) * (1. - t);
                        let b = 2. * (1. - t) * t;
                        let c = t * t;
                        (
                            f64::from(v[0].x) * a + f64::from(v[1].x) * b + f64::from(v[2].x) * c,
                            f64::from(v[0].y) * a + f64::from(v[1].y) * b + f64::from(v[2].y) * c,
                        )
                    }
                    BezierCurve::Cubic(v) => {
                        let a = (1. - t).powi(3);
                        let b = 3. * t * (1. - t).powi(2);
                        let c = 3. * t * t * (1. - t);
                        let d = t.powi(3);
                        (
                            f64::from(v[0].x) * a
                                + f64::from(v[1].x) * b
                                + f64::from(v[2].x) * c
                                + f64::from(v[3].x) * d,
                            f64::from(v[0].y) * a
                                + f64::from(v[1].y) * b
                                + f64::from(v[2].y) * c
                                + f64::from(v[3].y) * d,
                        )
                    }
                };
                let sample = Point2::new(pt.0 as f32, pt.1 as f32);
                let nearest = path
                    .iter()
                    .map(|s| dist_from_chord(sample, s.start, s.end))
                    .fold(f64::INFINITY, f64::min);
                assert!(nearest <= 0.51, "distance={nearest} t={t}");
            }
        }
    }
}
