//! blob.in showcase — native Wayland surface presenting BLOB-FRAME-v1 frames.
//!
//! The surface owns the window, interaction, scene controls and presentation.
//! It computes no geometry: every pixel of the viewport comes from a frame
//! received over BLOB-FRAME-v1 (overlays aside, which are drawn from the
//! surface's own control values and labelled as such).

pub mod app;
pub mod scene;
pub mod scheduler;
pub mod theme;
pub mod trace;
pub mod view;
pub mod ui_motion;
pub mod ui_widgets;

pub mod ac02_scene;

pub mod ac04_scene_gestures;

pub mod ac01a_toggle;

pub mod ac01a_native_gpu;

pub mod ac01b_control_layout;

pub mod ac01b_action;

pub mod ac01c_reset;

pub mod ac01d_stress;

pub mod ac01e_stroke_stress;

pub mod ac01f_bezier_stress;

pub mod ac01g_closed_path_stress;

pub mod ac01h_complex_paths;

pub mod ac01i_even_odd;
