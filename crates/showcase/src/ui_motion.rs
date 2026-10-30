//! Reusable blob.in UI motion and typed interaction state.
//! No GPU dependency; real Vulkan UI surface consumes these values.
use std::f32::consts::PI;

#[derive(Clone, Copy, Debug)]
pub struct Spring {
    pub value: f32,
    pub velocity: f32,
    pub target: f32,
    pub frequency_hz: f32,
}

impl Spring {
    pub fn new(value: f32) -> Self {
        Self {
            value,
            velocity: 0.0,
            target: value,
            frequency_hz: 5.0,
        }
    }

    /// Bounded semi-implicit spring; small steps avoid a background-tab hitch.
    pub fn advance(&mut self, seconds: f32, reduced_motion: bool) -> bool {
        if reduced_motion {
            let changed = (self.value - self.target).abs() > 0.0001;
            self.value = self.target;
            self.velocity = 0.0;
            return changed;
        }
        if !seconds.is_finite() || seconds <= 0.0 {
            return false;
        }
        let seconds = seconds.min(0.1);
        let count = (seconds / (1.0 / 240.0)).ceil().max(1.0) as u32;
        let dt = seconds / count as f32;
        let omega = 2.0 * PI * self.frequency_hz;
        let initial = self.value;
        for _ in 0..count {
            let acceleration =
                omega * omega * (self.target - self.value) - 2.0 * omega * self.velocity;
            self.velocity += acceleration * dt;
            self.value += self.velocity * dt;
        }
        if (self.value - self.target).abs() < 0.0005 && self.velocity.abs() < 0.005 {
            self.value = self.target;
            self.velocity = 0.0;
        }
        (self.value - initial).abs() > 0.0001
    }

    pub fn moving(&self) -> bool {
        (self.value - self.target).abs() > 0.0005 || self.velocity.abs() > 0.005
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum UiAction {
    SelectSurface(usize),
    ToggleMotion,
    ToggleInspector,
    ToggleReducedMotion,
    ToggleFocus,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Layout {
    pub width: f32,
    pub height: f32,
    pub rail: f32,
    pub inspector: f32,
    pub canvas_width: f32,
    pub compact: bool,
}

impl Layout {
    pub fn responsive(width: f32, height: f32, inspector_progress: f32) -> Self {
        let width = width.max(320.0);
        let height = height.max(300.0);
        let compact = width < 1050.0;
        let rail = if compact { 64.0 } else { 76.0 };
        let inspector = if compact {
            0.0
        } else {
            300.0 * inspector_progress.clamp(0.0, 1.0)
        };
        Self {
            width,
            height,
            rail,
            inspector,
            canvas_width: (width - rail - inspector).max(1.0),
            compact,
        }
    }
}

#[derive(Debug)]
pub struct UiRuntime {
    pub selected: usize,
    pub motion_on: bool,
    pub reduced_motion: bool,
    pub focused: bool,
    pub inspector_open: bool,
    pub inspector: Spring,
    pub emphasis: Spring,
    pub hover: Spring,
    pub phase: f32,
    pub ui_revision: u64,
}

impl Default for UiRuntime {
    fn default() -> Self {
        Self {
            selected: 0,
            motion_on: true,
            reduced_motion: false,
            focused: false,
            inspector_open: true,
            inspector: Spring::new(1.0),
            emphasis: Spring::new(0.0),
            hover: Spring::new(0.0),
            phase: 0.0,
            ui_revision: 0,
        }
    }
}

impl UiRuntime {
    pub fn dispatch(&mut self, action: UiAction) {
        match action {
            UiAction::SelectSurface(i) if i < 3 => {
                self.selected = i;
                self.emphasis.target = (i as f32) * 0.5;
            }
            UiAction::ToggleMotion => self.motion_on = !self.motion_on,
            UiAction::ToggleInspector => {
                self.inspector_open = !self.inspector_open;
                self.inspector.target = if self.inspector_open { 1.0 } else { 0.0 };
            }
            UiAction::ToggleReducedMotion => self.reduced_motion = !self.reduced_motion,
            UiAction::ToggleFocus => self.focused = !self.focused,
            _ => return,
        }
        self.ui_revision += 1;
    }

    pub fn advance(&mut self, dt: f32, pointer_over: bool) -> bool {
        self.hover.target = if pointer_over { 1.0 } else { 0.0 };
        let mut changed = false;
        changed |= self.inspector.advance(dt, self.reduced_motion);
        changed |= self.emphasis.advance(dt, self.reduced_motion);
        changed |= self.hover.advance(dt, self.reduced_motion);
        if self.motion_on && !self.reduced_motion && dt.is_finite() && dt > 0.0 {
            self.phase = (self.phase + dt.min(0.1) * 0.2).fract();
            changed = true;
        }
        changed
    }

    pub fn layout(&self, width: f32, height: f32) -> Layout {
        Layout::responsive(width, height, self.inspector.value)
    }

    pub fn active_motion(&self) -> bool {
        (self.motion_on && !self.reduced_motion)
            || self.inspector.moving()
            || self.emphasis.moving()
            || self.hover.moving()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn spring_converges_at_60hz() {
        let mut spring = Spring::new(0.0);
        spring.target = 1.0;
        for _ in 0..180 {
            spring.advance(1.0 / 60.0, false);
            assert!(spring.value.is_finite());
        }
        assert!((spring.value - 1.0).abs() < 0.001);
        assert!(!spring.moving());
    }

    #[test]
    fn frame_hitch_bounded() {
        let mut spring = Spring::new(0.0);
        spring.target = 1.0;
        spring.advance(10.0, false);
        assert!(spring.value.is_finite() && spring.value >= 0.0);
        assert!(spring.value < 1.5);
    }

    #[test]
    fn reduced_motion_is_immediate() {
        let mut state = UiRuntime::default();
        state.dispatch(UiAction::ToggleReducedMotion);
        state.dispatch(UiAction::ToggleInspector);
        state.advance(1.0 / 60.0, false);
        assert_eq!(state.inspector.value, 0.0);
        assert!(!state.inspector.moving());
    }

    #[test]
    fn selected_surface_identity_and_revision() {
        let mut state = UiRuntime::default();
        state.dispatch(UiAction::SelectSurface(2));
        assert_eq!(state.selected, 2);
        assert_eq!(state.ui_revision, 1);
        state.dispatch(UiAction::SelectSurface(30));
        assert_eq!(state.selected, 2);
        assert_eq!(state.ui_revision, 1);
    }

    #[test]
    fn responsive_layout_never_overflows() {
        for width in [320.0, 750.0, 1050.0, 1280.0, 1920.0] {
            for progress in [0.0, 0.3, 1.0] {
                let l = Layout::responsive(width, 720.0, progress);
                assert!(l.canvas_width > 0.0);
                assert!(l.rail + l.inspector + l.canvas_width <= l.width + 0.01);
            }
        }
        assert!(Layout::responsive(800.0, 700.0, 1.0).compact);
        assert!(!Layout::responsive(1280.0, 700.0, 1.0).compact);
    }

    #[test]
    fn pause_and_reduced_motion_do_not_accumulate_time() {
        let mut state = UiRuntime::default();
        state.dispatch(UiAction::ToggleMotion);
        let before = state.phase;
        state.advance(2.0, false);
        assert_eq!(state.phase, before);
        state.dispatch(UiAction::ToggleMotion);
        state.dispatch(UiAction::ToggleReducedMotion);
        state.advance(2.0, false);
        assert_eq!(state.phase, before);
    }
}
