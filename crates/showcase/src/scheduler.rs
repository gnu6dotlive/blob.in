//! Render scheduling: which size to request, when to request, which frames to keep.
//!
//! Every change of an input that affects the output (scene, camera, viewport
//! size, backend, view mode) bumps `revision`. At most one request is in flight
//! (the contract allows one at a time); when it settles, a single request with
//! the latest inputs follows, so bursts of resize or drag events coalesce into
//! one request instead of queueing. A frame is presented only if its revision is
//! newer than the one on screen; anything older is dropped.

use std::time::Instant;

use blob_frame::{Capabilities, MIN_DIMENSION};

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Fit {
    /// The viewport is smaller than the runtime minimum in some axis.
    TooSmall,
    /// Request w×h; `scale` = request pixels / viewport physical pixels (≤ 1).
    Render { w: u32, h: u32, scale: f32 },
}

/// The largest request size with the viewport's aspect that fits the runtime limits.
pub fn fit(physical: (u32, u32), caps: &Capabilities) -> Fit {
    let (w, h) = physical;
    if w < MIN_DIMENSION || h < MIN_DIMENSION {
        return Fit::TooSmall;
    }
    let (wf, hf) = (w as f64, h as f64);
    let mut s = 1.0f64
        .min(caps.max_width_px as f64 / wf)
        .min(caps.max_height_px as f64 / hf)
        .min((caps.max_pixels as f64 / (wf * hf)).sqrt());
    loop {
        let (rw, rh) = ((wf * s).floor() as u32, (hf * s).floor() as u32);
        if rw < MIN_DIMENSION || rh < MIN_DIMENSION {
            return Fit::TooSmall;
        }
        if caps.accepts_size(rw, rh) {
            return Fit::Render { w: rw, h: rh, scale: s as f32 };
        }
        s *= 0.999;
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Verdict {
    Present,
    /// Older than the frame on screen.
    Stale,
    /// Not the request in flight (e.g. from a reset session).
    Unknown,
}

#[derive(Clone, Copy, Debug)]
pub struct InFlight {
    pub request_id: u64,
    pub revision: u64,
    pub issued_at: Instant,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Counters {
    pub issued: u64,
    pub presented: u64,
    pub stale: u64,
    pub failed: u64,
}

#[derive(Debug)]
pub struct Scheduler {
    next_request_id: u64,
    revision: u64,
    issued: u64,
    presented: u64,
    in_flight: Option<InFlight>,
    pub counters: Counters,
}

impl Default for Scheduler {
    fn default() -> Self {
        Self::new()
    }
}

impl Scheduler {
    pub fn new() -> Self {
        // Request ids start at 1: the runtime uses 0 for errors not tied to a request.
        Self { next_request_id: 1, revision: 1, issued: 0, presented: 0, in_flight: None, counters: Counters::default() }
    }

    /// Records that the render inputs changed.
    pub fn invalidate(&mut self) {
        self.revision += 1;
    }

    pub fn revision(&self) -> u64 {
        self.revision
    }

    pub fn presented_revision(&self) -> u64 {
        self.presented
    }

    pub fn in_flight(&self) -> Option<InFlight> {
        self.in_flight
    }

    /// Inputs changed since the last request was issued.
    pub fn dirty(&self) -> bool {
        self.revision > self.issued
    }

    /// Claims the request slot for the current revision, if free and needed.
    pub fn issue(&mut self, now: Instant) -> Option<InFlight> {
        if self.in_flight.is_some() || !self.dirty() {
            return None;
        }
        let f = InFlight { request_id: self.next_request_id, revision: self.revision, issued_at: now };
        self.next_request_id += 1;
        self.issued = self.revision;
        self.in_flight = Some(f);
        self.counters.issued += 1;
        Some(f)
    }

    pub fn on_frame(&mut self, request_id: u64, revision: u64) -> Verdict {
        match self.in_flight {
            Some(f) if f.request_id == request_id => self.in_flight = None,
            _ => return Verdict::Unknown,
        }
        if revision <= self.presented {
            self.counters.stale += 1;
            return Verdict::Stale;
        }
        self.presented = revision;
        self.counters.presented += 1;
        Verdict::Present
    }

    /// The request in flight settled without a presentable frame. No automatic
    /// retry: the next input change issues a new request.
    pub fn on_failed(&mut self, request_id: u64) -> bool {
        match self.in_flight {
            Some(f) if f.request_id == request_id => {
                self.in_flight = None;
                self.counters.failed += 1;
                true
            }
            _ => false,
        }
    }

    /// Session lost or (re)established: forget the request in flight and render again.
    pub fn reset_session(&mut self) {
        self.in_flight = None;
        self.invalidate();
    }

    /// Explicit retry of the current inputs (e.g. after an error).
    pub fn retry(&mut self) {
        if self.in_flight.is_none() {
            self.invalidate();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use blob_frame::{Backend, ViewMode, VERSION};

    fn caps() -> Capabilities {
        Capabilities {
            version: VERSION.into(),
            backends_implemented: Backend::ALL.to_vec(),
            cuda_configured: true,
            view_modes: ViewMode::ALL.to_vec(),
            max_width_px: 1024,
            max_height_px: 1024,
            max_pixels: 1_048_576,
            device_healthy_now: "x".into(),
        }
    }

    #[test]
    fn fit_respects_limits_and_aspect() {
        let c = caps();
        assert_eq!(fit((800, 600), &c), Fit::Render { w: 800, h: 600, scale: 1.0 });
        assert_eq!(fit((15, 600), &c), Fit::TooSmall);
        for (w, h) in [(2560, 1440), (3000, 200), (1025, 1025), (5000, 5000), (17, 4000)] {
            match fit((w, h), &c) {
                Fit::Render { w: rw, h: rh, scale } => {
                    assert!(c.accepts_size(rw, rh), "{w}x{h} -> {rw}x{rh}");
                    assert!(scale <= 1.0);
                    let (a, b) = (w as f32 / h as f32, rw as f32 / rh as f32);
                    assert!((a - b).abs() / a < 0.08, "aspect {w}x{h} -> {rw}x{rh}");
                }
                Fit::TooSmall => assert_eq!((w, h), (17, 4000), "only the extreme strip is unrenderable"),
            }
        }
    }

    #[test]
    fn coalesces_bursts_into_one_request() {
        let mut s = Scheduler::new();
        let now = Instant::now();
        let a = s.issue(now).unwrap();
        for _ in 0..100 {
            s.invalidate();
            assert!(s.issue(now).is_none(), "one in flight");
        }
        assert_eq!(s.on_frame(a.request_id, a.revision), Verdict::Present);
        let b = s.issue(now).unwrap();
        assert_eq!(b.revision, s.revision(), "the follow-up carries the latest inputs");
        assert_eq!(s.counters.issued, 2);
        assert_eq!(s.on_frame(b.request_id, b.revision), Verdict::Present);
        assert!(s.issue(now).is_none(), "nothing changed");
    }

    #[test]
    fn stale_and_unknown_frames_are_not_presented() {
        let mut s = Scheduler::new();
        let now = Instant::now();
        let a = s.issue(now).unwrap();
        assert_eq!(s.on_frame(a.request_id + 7, a.revision), Verdict::Unknown);
        assert_eq!(s.on_frame(a.request_id, a.revision), Verdict::Present);
        s.invalidate();
        let b = s.issue(now).unwrap();
        // A runtime echoing an old revision for the new request is never shown.
        assert_eq!(s.on_frame(b.request_id, a.revision), Verdict::Stale);
        assert_eq!(s.presented_revision(), a.revision);
    }

    #[test]
    fn failure_frees_the_slot_without_retry_loop() {
        let mut s = Scheduler::new();
        let now = Instant::now();
        let a = s.issue(now).unwrap();
        assert!(s.on_failed(a.request_id));
        assert!(s.issue(now).is_none(), "no automatic retry");
        s.retry();
        assert!(s.issue(now).is_some());
    }

    #[test]
    fn session_reset_rerenders() {
        let mut s = Scheduler::new();
        let now = Instant::now();
        let a = s.issue(now).unwrap();
        assert_eq!(s.on_frame(a.request_id, a.revision), Verdict::Present);
        s.issue(now);
        s.reset_session();
        let b = s.issue(now).unwrap();
        assert_eq!(s.on_frame(b.request_id, b.revision), Verdict::Present, "post-reconnect frame is newer");
    }
}
