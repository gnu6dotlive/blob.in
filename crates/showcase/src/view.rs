//! Mapping between screen points, world units and frames.
//!
//! The runtime samples pixel (ix, iy) of a w×h frame at engine coordinates
//! ((ix + 0.5 - w/2) / min(w, h), (iy + 0.5 - h/2) / min(w, h)), y down, and
//! the surface maps world → engine with its camera. A frame therefore covers a
//! known world rectangle, which lets the last frame be placed correctly while
//! the viewport is resized or the camera moves and the next frame is computed.

use crate::scene::Camera;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Rect {
    pub x0: f32,
    pub y0: f32,
    pub x1: f32,
    pub y1: f32,
}

impl Rect {
    pub fn width(&self) -> f32 {
        self.x1 - self.x0
    }
    pub fn height(&self) -> f32 {
        self.y1 - self.y0
    }
    pub fn center(&self) -> (f32, f32) {
        ((self.x0 + self.x1) * 0.5, (self.y0 + self.y1) * 0.5)
    }
}

/// A viewport on screen (any unit, typically egui points) showing `camera`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct View {
    pub rect: Rect,
    pub camera: Camera,
}

impl View {
    /// Screen units per engine unit.
    fn scale(&self) -> f32 {
        self.rect.width().min(self.rect.height()).max(1e-6)
    }

    pub fn world_to_screen(&self, (x, y): (f32, f32)) -> (f32, f32) {
        let (cx, cy) = self.rect.center();
        let k = self.camera.zoom * self.scale();
        (cx + (x - self.camera.cx) * k, cy + (y - self.camera.cy) * k)
    }

    pub fn screen_to_world(&self, (sx, sy): (f32, f32)) -> (f32, f32) {
        let (cx, cy) = self.rect.center();
        let k = self.camera.zoom * self.scale();
        (self.camera.cx + (sx - cx) / k, self.camera.cy + (sy - cy) / k)
    }

    /// World length of `len` screen units.
    pub fn world_len(&self, len: f32) -> f32 {
        len / (self.camera.zoom * self.scale())
    }

    /// Where a w×h frame rendered for `frame_camera` lands in this view.
    pub fn frame_rect(&self, frame_camera: &Camera, w: u32, h: u32) -> Rect {
        let m = w.min(h).max(1) as f32;
        let (ex, ey) = (w as f32 / (2.0 * m), h as f32 / (2.0 * m));
        let z = frame_camera.zoom;
        let (x0, y0) = self.world_to_screen((frame_camera.cx - ex / z, frame_camera.cy - ey / z));
        let (x1, y1) = self.world_to_screen((frame_camera.cx + ex / z, frame_camera.cy + ey / z));
        Rect { x0, y0, x1, y1 }
    }

    /// Camera after zooming by `factor` about screen point `at`, keeping the world point under it fixed.
    pub fn zoom_about(&self, at: (f32, f32), factor: f32, min: f32, max: f32) -> Camera {
        let anchor = self.screen_to_world(at);
        let zoom = (self.camera.zoom * factor).clamp(min, max);
        let next = View { rect: self.rect, camera: Camera { zoom, ..self.camera } };
        let moved = next.screen_to_world(at);
        Camera { cx: self.camera.cx + anchor.0 - moved.0, cy: self.camera.cy + anchor.1 - moved.1, zoom }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn close(a: (f32, f32), b: (f32, f32)) -> bool {
        (a.0 - b.0).abs() < 1e-3 && (a.1 - b.1).abs() < 1e-3
    }

    #[test]
    fn round_trip() {
        let v = View { rect: Rect { x0: 10.0, y0: 20.0, x1: 810.0, y1: 620.0 }, camera: Camera { cx: 0.1, cy: -0.3, zoom: 1.7 } };
        for p in [(0.0, 0.0), (0.4, -0.2), (-1.0, 1.0)] {
            assert!(close(v.screen_to_world(v.world_to_screen(p)), p));
        }
    }

    #[test]
    fn current_frame_fills_the_viewport_exactly() {
        let rect = Rect { x0: 0.0, y0: 0.0, x1: 900.0, y1: 600.0 };
        let cam = Camera { cx: 0.2, cy: 0.1, zoom: 1.3 };
        let v = View { rect, camera: cam };
        // A frame rendered at the viewport's aspect (any resolution) covers it exactly.
        for (w, h) in [(900, 600), (450, 300), (1024, 683)] {
            let r = v.frame_rect(&cam, w, h);
            assert!((r.x0 - rect.x0).abs() < 1.0 && (r.x1 - rect.x1).abs() < 1.0, "{w}x{h}: {r:?}");
            assert!((r.y0 - rect.y0).abs() < 1.0 && (r.y1 - rect.y1).abs() < 1.0, "{w}x{h}: {r:?}");
        }
    }

    #[test]
    fn stale_frame_keeps_world_geometry_after_resize() {
        let cam = Camera::default();
        let old = View { rect: Rect { x0: 0.0, y0: 0.0, x1: 800.0, y1: 600.0 }, camera: cam };
        let new = View { rect: Rect { x0: 0.0, y0: 0.0, x1: 1200.0, y1: 600.0 }, camera: cam };
        // The old 800x600 frame keeps its scale (min side unchanged) and is centred.
        let r = new.frame_rect(&cam, 800, 600);
        assert!(close((r.x0, r.y0), (200.0, 0.0)) && close((r.x1, r.y1), (1000.0, 600.0)), "{r:?}");
        // And a world point keeps its place relative to the frame.
        let p = (0.1, 0.2);
        let a = old.world_to_screen(p);
        let b = new.world_to_screen(p);
        assert!(close((a.0 + 200.0, a.1), b));
    }

    #[test]
    fn zoom_about_keeps_anchor() {
        let v = View { rect: Rect { x0: 0.0, y0: 0.0, x1: 800.0, y1: 600.0 }, camera: Camera::default() };
        let at = (600.0, 150.0);
        let before = v.screen_to_world(at);
        let cam = v.zoom_about(at, 2.0, 0.25, 4.0);
        let after = View { camera: cam, ..v }.screen_to_world(at);
        assert!(close(before, after));
        assert_eq!(v.zoom_about(at, 100.0, 0.25, 4.0).zoom, 4.0);
    }
}
