//! Reference test card. Depends only on the frame geometry and request metadata,
//! never on the scene: this server evaluates no SDF and must not be mistaken
//! for a renderer.
//!
//! Layout (all clipped to the frame):
//! - 1 px white border: no cropping, no off-by-one.
//! - 12x12 corner markers TL red, TR green, BL blue, BR white: orientation and channel order.
//! - 32-bit barcode of `scene_revision` (LSB first, 4 px cells at x = 20.., rows 20..28).
//! - 6 px bottom stripe coloured by requested backend.
//! - Background pattern per view mode, 64 px grid.
//! - Row padding bytes, if a fault asks for a padded stride, are 0xAB.

use blob_frame::{Backend, RenderRequest, ViewMode};

pub const PAD_BYTE: u8 = 0xAB;
pub const MARKER: u32 = 12;
pub const BARCODE_X: u32 = 20;
pub const BARCODE_Y: u32 = 20;
pub const BARCODE_CELL: u32 = 4;
pub const BARCODE_BITS: u32 = 32;
pub const BARCODE_H: u32 = 8;
pub const STRIPE_H: u32 = 6;

pub const TL: [u8; 3] = [255, 0, 0];
pub const TR: [u8; 3] = [0, 255, 0];
pub const BL: [u8; 3] = [0, 0, 255];
pub const BR: [u8; 3] = [255, 255, 255];

pub fn backend_colour(b: Backend) -> [u8; 3] {
    match b {
        Backend::Cpu => [160, 160, 160],
        Backend::Cuda => [118, 185, 0],
        Backend::Vulkan => [172, 22, 44],
    }
}

fn background(mode: ViewMode, x: u32, y: u32, w: u32, h: u32) -> [u8; 3] {
    let grid = x % 64 == 0 || y % 64 == 0;
    let c = match mode {
        ViewMode::Distance => {
            if ((x + y) / 16) % 2 == 0 {
                [24, 58, 92]
            } else {
                [36, 84, 128]
            }
        }
        ViewMode::Normals => [(x * 255 / w.max(1)) as u8, (y * 255 / h.max(1)) as u8, 128],
        ViewMode::Coverage => {
            if ((x / 32) + (y / 32)) % 2 == 0 {
                [70, 70, 70]
            } else {
                [110, 110, 110]
            }
        }
        ViewMode::Lit => {
            let t = (x + y) * 255 / (w + h).max(1);
            [(90 + t / 2) as u8, (60 + t / 3) as u8, 40]
        }
    };
    if grid {
        c.map(|v| v / 2)
    } else {
        c
    }
}

pub fn render(req: &RenderRequest, stride: u32) -> Vec<u8> {
    let (w, h) = (req.width_px, req.height_px);
    assert!(stride >= w * 4);
    let mut buf = vec![PAD_BYTE; stride as usize * h as usize];
    let m = MARKER.min(w / 2).min(h / 2);
    let barcode = w >= BARCODE_X + BARCODE_BITS * BARCODE_CELL + 2 && h >= BARCODE_Y + BARCODE_H + STRIPE_H + 2;
    let bits = req.scene_revision as u32;
    let stripe = backend_colour(req.backend_requested);
    for y in 0..h {
        let row = &mut buf[(y * stride) as usize..][..(w * 4) as usize];
        for x in 0..w {
            let rgb = if x == 0 || y == 0 || x == w - 1 || y == h - 1 {
                [255, 255, 255]
            } else if x < m && y < m {
                TL
            } else if x >= w - m && y < m {
                TR
            } else if x < m && y >= h - m {
                BL
            } else if x >= w - m && y >= h - m {
                BR
            } else if y + 1 + STRIPE_H >= h {
                stripe
            } else if barcode
                && (BARCODE_Y..BARCODE_Y + BARCODE_H).contains(&y)
                && (BARCODE_X..BARCODE_X + BARCODE_BITS * BARCODE_CELL).contains(&x)
            {
                if bits >> ((x - BARCODE_X) / BARCODE_CELL) & 1 == 1 {
                    [255, 255, 255]
                } else {
                    [0, 0, 0]
                }
            } else {
                background(req.view_mode, x, y, w, h)
            };
            row[(x * 4) as usize..][..4].copy_from_slice(&[rgb[0], rgb[1], rgb[2], 255]);
        }
    }
    buf
}

/// Reads an RGBA8 pixel from a tightly or loosely strided buffer.
pub fn pixel(buf: &[u8], stride: u32, x: u32, y: u32) -> [u8; 4] {
    let o = (y * stride + x * 4) as usize;
    [buf[o], buf[o + 1], buf[o + 2], buf[o + 3]]
}

/// Decodes the revision barcode (low 32 bits), if the frame is large enough to carry one.
pub fn decode_revision(buf: &[u8], stride: u32, w: u32, h: u32) -> Option<u32> {
    if w < BARCODE_X + BARCODE_BITS * BARCODE_CELL + 2 || h < BARCODE_Y + BARCODE_H + STRIPE_H + 2 {
        return None;
    }
    let y = BARCODE_Y + BARCODE_H / 2;
    let mut v = 0u32;
    for i in 0..BARCODE_BITS {
        let p = pixel(buf, stride, BARCODE_X + i * BARCODE_CELL + BARCODE_CELL / 2, y);
        match p {
            [255, 255, 255, 255] => v |= 1 << i,
            [0, 0, 0, 255] => {}
            _ => return None,
        }
    }
    Some(v)
}

/// Structural check of a test card: corners, border, alpha. Returns a reason on failure.
pub fn verify(buf: &[u8], stride: u32, w: u32, h: u32) -> Result<(), String> {
    let m = MARKER.min(w / 2).min(h / 2);
    if m >= 3 {
        for (name, (x, y), want) in [
            ("TL", (m / 2, m / 2), TL),
            ("TR", (w - 1 - m / 2, m / 2), TR),
            ("BL", (m / 2, h - 1 - m / 2), BL),
            ("BR", (w - 1 - m / 2, h - 1 - m / 2), BR),
        ] {
            let p = pixel(buf, stride, x, y);
            if p[..3] != want {
                return Err(format!("{name} marker at ({x},{y}) is {p:?}, want {want:?}"));
            }
        }
    }
    for (x, y) in [(0, h / 2), (w - 1, h / 2), (w / 2, 0), (w / 2, h - 1)] {
        if pixel(buf, stride, x, y) != [255, 255, 255, 255] {
            return Err(format!("border pixel ({x},{y}) not white"));
        }
    }
    for y in 0..h {
        for x in 0..w {
            if pixel(buf, stride, x, y)[3] != 255 {
                return Err(format!("pixel ({x},{y}) not opaque"));
            }
        }
    }
    Ok(())
}
