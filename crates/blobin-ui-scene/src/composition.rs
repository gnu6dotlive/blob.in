//! UI01D: backend-free ordered composition of distinct G02 surfaces.
//!
//! Coordinate convention: steps are listed inner-to-outer. Each step maps
//! current geometry into its parent's coordinate space; that step's clip,
//! when present, is already expressed in parent coordinates. This yields
//! deterministic cumulative transforms, including nested scroll clips.
use crate::{transform_and_clip, DisplayList, SceneError, UiTransform2D};
use blobin_ui_core::layout::Rect;
use blobin_ui_core::{NodeId, SurfaceId};
use std::collections::BTreeSet;

pub const MAX_NATIVE_UI_COMMANDS: usize = 64;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct LayerStep {
    pub transform: UiTransform2D,
    pub parent_clip: Option<Rect>,
}
impl LayerStep {
    pub const IDENTITY: Self = Self {
        transform: UiTransform2D::IDENTITY,
        parent_clip: None,
    };
}

#[derive(Clone, Copy, Debug)]
pub struct SceneLayer<'a> {
    pub list: &'a DisplayList,
    /// Inner -> outer, preserving transform-then-clip semantics at each step.
    pub ancestors: &'a [LayerStep],
}

#[derive(Clone, Debug, PartialEq)]
pub struct ComposedScene {
    pub lists: Vec<DisplayList>,
    pub command_count: usize,
    pub input_layers: usize,
    pub clipped_layers: usize,
}
impl ComposedScene {
    pub fn as_refs(&self) -> Vec<&DisplayList> {
        self.lists.iter().collect()
    }
}
/// Explicit deterministic limit. No hidden GPU allocation, window or IO.
/// Reject duplicate (surface,node) entries and invalid transforms atomically.
pub fn compose(layers: &[SceneLayer<'_>], limit: usize) -> Result<ComposedScene, SceneError> {
    if limit == 0 || limit > MAX_NATIVE_UI_COMMANDS {
        return Err(SceneError::InvalidBounds);
    }
    let mut seen = BTreeSet::<(SurfaceId, NodeId)>::new();
    let mut output = Vec::with_capacity(layers.len());
    let mut total = 0usize;
    let mut clipped = 0usize;
    for layer in layers {
        let list = layer.list;
        if !seen.insert((list.surface, list.source_node)) {
            return Err(SceneError::InvalidTarget);
        }
        if list
            .commands
            .iter()
            .any(|cmd| cmd.source != list.source_node)
            || list
                .strokes
                .iter()
                .any(|cmd| cmd.source != list.source_node)
            || list.triangles.iter().any(|t| t.source != list.source_node)
        {
            return Err(SceneError::InvalidTarget);
        }
        let mut current = list.clone();
        let mut vanished = false;
        for ancestor in layer.ancestors {
            let clips = ancestor.parent_clip.as_slice();
            match transform_and_clip(&current, ancestor.transform, clips) {
                Ok(value) => current = value,
                Err(SceneError::Invisible) => {
                    vanished = true;
                    break;
                }
                Err(error) => return Err(error),
            }
        }
        if vanished
            || (current.commands.is_empty()
                && current.strokes.is_empty()
                && current.triangles.is_empty())
        {
            clipped += 1;
            continue;
        }
        total = total
            .checked_add(current.commands.len() + current.strokes.len() + current.triangles.len())
            .ok_or(SceneError::InvalidBounds)?;
        if total > limit {
            return Err(SceneError::InvalidBounds);
        }
        output.push(current);
    }
    if total == 0 {
        return Err(SceneError::Invisible);
    }
    Ok(ComposedScene {
        lists: output,
        command_count: total,
        input_layers: layers.len(),
        clipped_layers: clipped,
    })
}
#[cfg(test)]
mod tests {
    use super::*;
    use crate::{FillRoundedRect, Rgba8};
    fn dummy(surface: u64, slot: u32, n: usize) -> DisplayList {
        let source = NodeId {
            slot,
            generation: 1,
        };
        let rect = Rect::new(2., 3., 10., 8.);
        let clip = Rect::new(0., 0., 100., 80.);
        DisplayList {
            source_ui_revision: 7,
            surface: SurfaceId(surface),
            layout_epoch: 4,
            source_node: source,
            strokes: vec![],
            triangles: vec![],
            commands: (0..n)
                .map(|i| FillRoundedRect {
                    source,
                    rect: Rect::new(rect.x + i as f32 * 2., rect.y, rect.width, rect.height),
                    clip,
                    color: Rgba8::new(255, 60, 20, 255),
                    radius: 3.,
                })
                .collect(),
        }
    }
    #[test]
    fn order_and_distinct_surface_identity_are_preserved() {
        let a = dummy(10, 1, 3);
        let b = dummy(11, 1, 3);
        let scene = compose(
            &[
                SceneLayer {
                    list: &a,
                    ancestors: &[],
                },
                SceneLayer {
                    list: &b,
                    ancestors: &[],
                },
            ],
            64,
        )
        .unwrap();
        assert_eq!(scene.command_count, 6);
        assert_eq!(scene.lists.len(), 2);
        assert_eq!(scene.lists[0].surface, SurfaceId(10));
        assert_eq!(scene.lists[1].surface, SurfaceId(11));
        assert_eq!(scene.lists[0].source_ui_revision, 7);
        assert_eq!(scene.lists[1].source_ui_revision, 7);
        assert_eq!(scene.as_refs().len(), 2);
    }
    #[test]
    fn nested_transforms_and_clips_compose_inner_to_outer() {
        let a = dummy(10, 1, 1);
        let child = LayerStep {
            transform: UiTransform2D {
                sx: 2.,
                sy: 2.,
                tx: 4.,
                ty: 6.,
            },
            parent_clip: Some(Rect::new(5., 8., 50., 25.)),
        };
        let parent = LayerStep {
            transform: UiTransform2D {
                sx: 1.5,
                sy: 1.,
                tx: 3.,
                ty: 9.,
            },
            parent_clip: Some(Rect::new(12., 18., 37., 18.)),
        };
        let result = compose(
            &[SceneLayer {
                list: &a,
                ancestors: &[child, parent],
            }],
            64,
        )
        .unwrap();
        let cmd = result.lists[0].commands[0];
        assert_eq!(cmd.rect, Rect::new(15., 21., 30., 16.));
        assert_eq!(cmd.clip, Rect::new(12., 18., 37., 18.));
        assert_eq!(cmd.radius, 6.);
        assert_eq!(result.lists[0].source_ui_revision, 7);
        assert_eq!(result.lists[0].layout_epoch, 4);
    }
    #[test]
    fn invisible_layer_culls_without_hiding_siblings() {
        let a = dummy(10, 1, 3);
        let b = dummy(11, 1, 3);
        let invisible = [LayerStep {
            transform: UiTransform2D::IDENTITY,
            parent_clip: Some(Rect::new(600., 600., 10., 10.)),
        }];
        let result = compose(
            &[
                SceneLayer {
                    list: &a,
                    ancestors: &invisible,
                },
                SceneLayer {
                    list: &b,
                    ancestors: &[],
                },
            ],
            64,
        )
        .unwrap();
        assert_eq!(result.command_count, 3);
        assert_eq!(result.clipped_layers, 1);
        assert_eq!(result.lists[0].surface, SurfaceId(11));
    }
    #[test]
    fn fills_count_and_transform_against_same_bounded_gpu_budget() {
        use crate::fills::fill_convex_path;
        use crate::strokes::Point2;
        let a = dummy(9, 1, 60);
        let mut b = dummy(10, 1, 0);
        let p = [
            Point2::new(4., 4.),
            Point2::new(20., 4.),
            Point2::new(20., 20.),
            Point2::new(4., 20.),
        ];
        b.triangles = fill_convex_path(
            b.source_node,
            &p,
            Rect::new(0., 0., 100., 80.),
            Rgba8::new(40, 90, 230, 255),
        )
        .unwrap();
        let t = [LayerStep {
            transform: UiTransform2D {
                sx: 2.,
                sy: 1.5,
                tx: 3.,
                ty: 4.,
            },
            parent_clip: Some(Rect::new(0., 0., 65., 65.)),
        }];
        let scoped = compose(
            &[SceneLayer {
                list: &b,
                ancestors: &t,
            }],
            64,
        )
        .unwrap();
        assert_eq!(scoped.command_count, 2);
        assert_eq!(
            scoped.lists[0].triangles[0].vertices[0],
            Point2::new(11., 10.)
        );
        let same = compose(
            &[
                SceneLayer {
                    list: &a,
                    ancestors: &[],
                },
                SceneLayer {
                    list: &b,
                    ancestors: &[],
                },
            ],
            64,
        )
        .unwrap();
        assert_eq!(same.command_count, 62);
        assert_eq!(same.lists[1].triangles.len(), 2);
        let mut more = dummy(11, 1, 3);
        assert_eq!(
            compose(
                &[
                    SceneLayer {
                        list: &a,
                        ancestors: &[]
                    },
                    SceneLayer {
                        list: &b,
                        ancestors: &[]
                    },
                    SceneLayer {
                        list: &more,
                        ancestors: &[]
                    },
                ],
                64
            ),
            Err(SceneError::InvalidBounds)
        );
        more.commands.truncate(2);
        assert_eq!(
            compose(
                &[
                    SceneLayer {
                        list: &a,
                        ancestors: &[]
                    },
                    SceneLayer {
                        list: &b,
                        ancestors: &[]
                    },
                    SceneLayer {
                        list: &more,
                        ancestors: &[]
                    },
                ],
                64
            )
            .unwrap()
            .command_count,
            64
        );
    }
    #[test]
    fn stroke_commands_count_against_gpu_budget_and_preserve_layer_order() {
        use crate::strokes::{stroke_polyline, Point2};
        let a = dummy(20, 4, 60);
        let mut b = dummy(21, 3, 0);
        b.strokes = stroke_polyline(
            b.source_node,
            &[
                Point2::new(4., 4.),
                Point2::new(12., 10.),
                Point2::new(16., 10.),
                Point2::new(24., 4.),
                Point2::new(32., 12.),
            ],
            3.,
            Rect::new(0., 0., 100., 80.),
            Rgba8::new(255, 10, 10, 255),
        )
        .unwrap();
        let layer_a = SceneLayer {
            list: &a,
            ancestors: &[],
        };
        let layer_b = SceneLayer {
            list: &b,
            ancestors: &[],
        };
        let result = compose(&[layer_a, layer_b], 64).unwrap();
        assert_eq!(result.command_count, 64);
        assert_eq!(result.lists[1].strokes.len(), 4);
        assert_eq!(result.lists[1].source_node, b.source_node);
        assert_eq!(
            compose(&[layer_a, layer_b], 63),
            Err(SceneError::InvalidBounds)
        );
        let ancestor = [LayerStep {
            transform: UiTransform2D {
                sx: 2.,
                sy: 2.,
                tx: 1.,
                ty: 1.,
            },
            parent_clip: Some(Rect::new(0., 0., 75., 75.)),
        }];
        let scaled = compose(
            &[SceneLayer {
                list: &b,
                ancestors: &ancestor,
            }],
            64,
        )
        .unwrap();
        assert_eq!(scaled.lists[0].strokes[0].width, 6.);
        assert_eq!(scaled.lists[0].strokes[0].start, Point2::new(9., 9.));
    }

    #[test]
    fn budget_stress_64_commands_passes_and_65_fails_closed() {
        let a = dummy(10, 1, 40);
        let b = dummy(11, 1, 24);
        let c = dummy(12, 1, 1);
        assert_eq!(
            compose(
                &[
                    SceneLayer {
                        list: &a,
                        ancestors: &[]
                    },
                    SceneLayer {
                        list: &b,
                        ancestors: &[]
                    }
                ],
                64
            )
            .unwrap()
            .command_count,
            64
        );
        assert_eq!(
            compose(
                &[
                    SceneLayer {
                        list: &a,
                        ancestors: &[]
                    },
                    SceneLayer {
                        list: &b,
                        ancestors: &[]
                    },
                    SceneLayer {
                        list: &c,
                        ancestors: &[]
                    },
                ],
                64
            ),
            Err(SceneError::InvalidBounds)
        );
    }
    #[test]
    fn twelve_levels_compose_in_deterministic_inner_to_outer_order() {
        let source = dummy(100, 2, 1);
        let steps = (0..12)
            .map(|_| LayerStep {
                transform: UiTransform2D {
                    sx: 1.01,
                    sy: 1.02,
                    tx: 1.,
                    ty: 0.5,
                },
                parent_clip: Some(Rect::new(0., 0., 500., 400.)),
            })
            .collect::<Vec<_>>();
        let one = compose(
            &[SceneLayer {
                list: &source,
                ancestors: &steps,
            }],
            64,
        )
        .unwrap();
        let two = compose(
            &[SceneLayer {
                list: &source,
                ancestors: &steps,
            }],
            64,
        )
        .unwrap();
        assert_eq!(one, two);
        let actual = one.lists[0].commands[0];
        let mut expected = source.commands[0].rect;
        for step in &steps {
            expected = step.transform.rect(expected).unwrap();
        }
        assert!((expected.x - actual.rect.x).abs() < 0.001);
        assert!((expected.y - actual.rect.y).abs() < 0.001);
        assert!((expected.width - actual.rect.width).abs() < 0.001);
        assert!(actual.clip.width > 0. && actual.clip.height > 0.);
    }
    #[test]
    fn rectangular_primitive_has_no_corner_radius_and_fails_closed() {
        let source = NodeId {
            slot: 3,
            generation: 8,
        };
        let rect = Rect::new(1., 2., 24., 10.);
        let clip = Rect::new(0., 0., 50., 50.);
        let color = Rgba8::new(40, 90, 120, 255);
        let cmd = crate::solid_rectangle(source, rect, clip, color).unwrap();
        assert_eq!(cmd.radius, 0.);
        assert_eq!(cmd.source, source);
        assert_eq!(cmd.color, color);
        assert_eq!(
            crate::solid_rectangle(source, rect, Rect::new(100., 100., 2., 2.), color),
            Err(SceneError::Invisible)
        );
        assert_eq!(
            crate::solid_rectangle(source, rect, Rect::new(0., f32::NAN, 30., 30.), color),
            Err(SceneError::InvalidBounds)
        );
    }
    #[test]
    fn rejects_duplicate_identity_bad_clip_and_overflow() {
        let a = dummy(10, 1, 1);
        assert_eq!(
            compose(
                &[
                    SceneLayer {
                        list: &a,
                        ancestors: &[]
                    },
                    SceneLayer {
                        list: &a,
                        ancestors: &[]
                    },
                ],
                64
            ),
            Err(SceneError::InvalidTarget)
        );
        assert_eq!(
            compose(
                &[SceneLayer {
                    list: &a,
                    ancestors: &[]
                }],
                65
            ),
            Err(SceneError::InvalidBounds)
        );
        let wrong = [LayerStep {
            transform: UiTransform2D {
                sx: f32::NAN,
                ..UiTransform2D::IDENTITY
            },
            parent_clip: None,
        }];
        assert_eq!(
            compose(
                &[SceneLayer {
                    list: &a,
                    ancestors: &wrong
                }],
                64
            ),
            Err(SceneError::InvalidBounds)
        );
    }
}
