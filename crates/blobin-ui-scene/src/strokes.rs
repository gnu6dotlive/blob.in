//! First-party bounded stroked polyline commands; no external tessellator.
//! Segments have round end-caps in the native GPU shader.
use crate::{Rgba8, SceneError, UiTransform2D};
use blobin_ui_core::layout::Rect;
use blobin_ui_core::NodeId;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Point2 {
    pub x: f32,
    pub y: f32,
}
impl Point2 {
    pub const fn new(x: f32, y: f32) -> Self {
        Self { x, y }
    }
    fn finite(self) -> bool {
        self.x.is_finite() && self.y.is_finite()
    }
}
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct StrokeSegment {
    pub source: NodeId,
    pub start: Point2,
    pub end: Point2,
    pub width: f32,
    pub clip: Rect,
    pub color: Rgba8,
}
fn valid_rect(r: Rect) -> bool {
    [r.x, r.y, r.width, r.height, r.x + r.width, r.y + r.height]
        .iter()
        .all(|x| x.is_finite())
        && r.width >= 0.
        && r.height >= 0.
}
impl StrokeSegment {
    pub fn validated(&self) -> Result<(), SceneError> {
        if !self.start.finite()
            || !self.end.finite()
            || !self.width.is_finite()
            || self.width <= 0.
            || self.width > 4096.
            || !valid_rect(self.clip)
        {
            return Err(SceneError::InvalidBounds);
        }
        if self.start == self.end {
            return Err(SceneError::InvalidBounds);
        }
        let extent = self.bounds()?;
        if extent.intersect(self.clip).width == 0. || extent.intersect(self.clip).height == 0. {
            return Err(SceneError::Invisible);
        }
        Ok(())
    }
    pub fn bounds(&self) -> Result<Rect, SceneError> {
        if !self.start.finite() || !self.end.finite() || !self.width.is_finite() || self.width <= 0.
        {
            return Err(SceneError::InvalidBounds);
        }
        let r = self.width * 0.5 + 1.0; // AA guard in logical pixels
        let x = self.start.x.min(self.end.x) - r;
        let y = self.start.y.min(self.end.y) - r;
        let width = (self.start.x - self.end.x).abs() + r * 2.;
        let height = (self.start.y - self.end.y).abs() + r * 2.;
        let result = Rect::new(x, y, width, height);
        if valid_rect(result) {
            Ok(result)
        } else {
            Err(SceneError::InvalidBounds)
        }
    }
    /// Width scales by min(sx,sy) for non-uniform transforms; documented
    /// conservative rule, not general affine stroke semantics.
    pub fn transformed(&self, t: UiTransform2D, ancestors: &[Rect]) -> Result<Self, SceneError> {
        t.checked()?;
        if ancestors.iter().any(|r| !valid_rect(*r)) {
            return Err(SceneError::InvalidBounds);
        }
        let point = |p: Point2| Point2::new(p.x * t.sx + t.tx, p.y * t.sy + t.ty);
        let mut copy = Self {
            start: point(self.start),
            end: point(self.end),
            width: self.width * t.sx.min(t.sy),
            clip: t.rect(self.clip)?,
            ..*self
        };
        for ancestor in ancestors {
            copy.clip = copy.clip.intersect(*ancestor);
        }
        copy.validated()?;
        Ok(copy)
    }
}
/// A path is a finite ordered polyline (not Bézier/fill/joins).
/// At most 64 independently attributable segments; duplicate consecutive
/// points fail closed rather than creating NaN normals.
pub fn stroke_polyline(
    source: NodeId,
    points: &[Point2],
    width: f32,
    clip: Rect,
    color: Rgba8,
) -> Result<Vec<StrokeSegment>, SceneError> {
    if points.len() < 2 || points.len() > 65 || !valid_rect(clip) {
        return Err(SceneError::InvalidBounds);
    }
    let mut output = Vec::with_capacity(points.len() - 1);
    for pair in points.windows(2) {
        let segment = StrokeSegment {
            source,
            start: pair[0],
            end: pair[1],
            width,
            clip,
            color,
        };
        segment.validated()?;
        output.push(segment);
    }
    Ok(output)
}
#[cfg(test)]
mod tests {
    use super::*;
    fn id() -> NodeId {
        NodeId {
            slot: 3,
            generation: 2,
        }
    }
    fn clip() -> Rect {
        Rect::new(0., 0., 220., 140.)
    }
    #[test]
    fn path_preserves_order_color_and_bounds() {
        let pts = [
            Point2::new(10., 10.),
            Point2::new(70., 40.),
            Point2::new(90., 20.),
        ];
        let p = stroke_polyline(id(), &pts, 4., clip(), Rgba8::new(160, 20, 30, 255)).unwrap();
        assert_eq!(p.len(), 2);
        assert_eq!(p[0].start, pts[0]);
        assert_eq!(p[1].end, pts[2]);
        assert_eq!(p[0].bounds().unwrap(), Rect::new(7., 7., 66., 36.));
        assert_eq!(p[0].source, id());
    }
    #[test]
    fn invalid_zero_nan_clipping_and_capacity_are_rejected() {
        let same = [Point2::new(9., 5.), Point2::new(9., 5.)];
        let good = [Point2::new(9., 5.), Point2::new(12., 8.)];
        let f = |p: &[Point2], w, clip| stroke_polyline(id(), p, w, clip, Rgba8::new(1, 2, 3, 255));
        assert_eq!(f(&same, 2., clip()), Err(SceneError::InvalidBounds));
        assert_eq!(
            f(&good, f32::INFINITY, clip()),
            Err(SceneError::InvalidBounds)
        );
        assert_eq!(f(&good, 0., clip()), Err(SceneError::InvalidBounds));
        assert_eq!(
            f(&good, 2., Rect::new(600., 600., 2., 2.)),
            Err(SceneError::Invisible)
        );
        assert_eq!(
            f(&vec![Point2::new(1., 1.); 66], 2., clip()),
            Err(SceneError::InvalidBounds)
        );
    }
    #[test]
    fn parent_transforms_and_clips_change_actual_segments() {
        let original = stroke_polyline(
            id(),
            &[Point2::new(10., 10.), Point2::new(40., 30.)],
            4.,
            clip(),
            Rgba8::new(1, 2, 3, 255),
        )
        .unwrap()[0];
        let scaled = original
            .transformed(
                UiTransform2D {
                    sx: 2.,
                    sy: 1.5,
                    tx: 3.,
                    ty: 4.,
                },
                &[Rect::new(0., 0., 100., 55.)],
            )
            .unwrap();
        assert_eq!(scaled.start, Point2::new(23., 19.));
        assert_eq!(scaled.end, Point2::new(83., 49.));
        assert_eq!(scaled.width, 6.);
        assert_eq!(scaled.clip, Rect::new(3., 4., 97., 51.));
        assert_eq!(scaled.source, original.source);
    }
}
