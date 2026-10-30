//! 01A: wgpu adapter renders the backend-free DisplayList in the host's
//! EXISTING swapchain. No window, queue, SDF kernel or presentation lifecycle.
//! One draw per rounded-rect command with a G03-derived scissor.
use blobin_ui_scene::fills::FillTriangle;
use blobin_ui_scene::strokes::StrokeSegment;
use blobin_ui_scene::{DisplayList, FillRoundedRect};
const SHADER: &str = r#"
struct Params { rect:vec4<f32>, tint:vec4<f32>, screen:vec4<f32>, segment:vec4<f32>, extra:vec4<f32> };
@group(0) @binding(0) var<uniform> params:Params;
struct V {
 @builtin(position) pos:vec4<f32>,
 @location(0) local:vec2<f32>,
 @location(1) size:vec2<f32>,
 @location(2) color:vec4<f32>,
 @location(3) radius:f32,
 @location(4) kind:f32,
 @location(5) endpoints:vec4<f32>,
 @location(6) vertex_c:vec2<f32>,
 @location(7) edge_mask:f32
};
@vertex fn vs(@builtin(vertex_index) i:u32)->V {
 let corners=array<vec2<f32>,6>(
  vec2<f32>(0.,0.),vec2<f32>(1.,0.),vec2<f32>(0.,1.),
  vec2<f32>(1.,0.),vec2<f32>(1.,1.),vec2<f32>(0.,1.));
 let local=corners[i]*params.rect.zw;
 let logical=params.rect.xy+local;
 var v:V;
 v.pos=vec4<f32>(2.*logical.x/params.screen.x-1.,
                 1.-2.*logical.y/params.screen.y,0.,1.);
 v.local=local;
 v.size=params.rect.zw;
 v.color=params.tint;
 v.radius=params.screen.z;
 v.kind=params.screen.w;
 v.endpoints=params.segment;
 v.vertex_c=params.extra.xy;
 v.edge_mask=params.extra.z;
 return v;
}
@fragment fn fs(v:V)->@location(0) vec4<f32> {
 let r=clamp(v.radius,0.,0.5*min(v.size.x,v.size.y));
 var signed_distance:f32;
 if v.kind>1.5 {
   let a=v.endpoints.xy;
   let b=v.endpoints.zw;
   let c=v.vertex_c;
   let e0=(b.x-a.x)*(v.local.y-a.y)-(b.y-a.y)*(v.local.x-a.x);
   let e1=(c.x-b.x)*(v.local.y-b.y)-(c.y-b.y)*(v.local.x-b.x);
   let e2=(a.x-c.x)*(v.local.y-c.y)-(a.y-c.y)*(v.local.x-c.x);
   let inside=(e0>=0. && e1>=0. && e2>=0.) ||
        (e0<=0. && e1<=0. && e2<=0.);
   if v.kind>2.5 {
      let ab=b-a;
      let bc=c-b;
      let ca=a-c;
      let winding=select(-1.,1.,((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))>0.);
      let d0=winding*e0/max(length(ab),0.0001);
      let d1=winding*e1/max(length(bc),0.0001);
      let d2=winding*e2/max(length(ca),0.0001);
      var coverage=1.;
      let mask=i32(v.edge_mask+0.5);
      if (mask & 1)!=0 {coverage=min(coverage,smoothstep(-0.5,0.5,d0));}
      if (mask & 2)!=0 {coverage=min(coverage,smoothstep(-0.5,0.5,d1));}
      if (mask & 4)!=0 {coverage=min(coverage,smoothstep(-0.5,0.5,d2));}
      if !inside && coverage==1. {discard;}
      return vec4<f32>(v.color.rgb,v.color.a*coverage);
   }
   if !inside {discard;}
   return v.color;
 }
 if v.kind>0.5 {
   let a=v.endpoints.xy;
   let b=v.endpoints.zw;
   let ab=b-a;
   let projection=clamp(dot(v.local-a,ab)/max(dot(ab,ab),1e-6),0.,1.);
   signed_distance=length(v.local-(a+projection*ab))-r;
 } else {
   let q=abs(v.local-v.size*0.5)-(v.size*0.5-vec2<f32>(r));
   signed_distance=length(max(q,vec2<f32>(0.,0.)))+
      min(max(q.x,q.y),0.)-r;
 }
 let coverage=1.-smoothstep(-0.65,0.65,signed_distance);
 return vec4<f32>(v.color.rgb,v.color.a*coverage);
}
"#;
const MAX_COMMANDS: usize = 64;
const UNIFORM_STRIDE: usize = 256;
/// Lifetime resource counters exclude egui's own texture allocations.
pub struct NativeOverlayRenderer {
    pipeline: wgpu::RenderPipeline,
    uniform: wgpu::Buffer,
    group: wgpu::BindGroup,
    bytes: Vec<u8>,
    last_uploaded: Vec<u8>,
    pub uploads: u64,
    pub resident_allocations: u64,
}
pub struct DrawReceipt {
    pub commands: usize,
    pub nodes: usize,
    pub node: u32,
    pub ui_revision: u64,
    pub geometry_epoch: u64,
    pub uniform_write: bool,
}
impl NativeOverlayRenderer {
    pub fn new(device: &wgpu::Device, format: wgpu::TextureFormat) -> Self {
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("01B first-party native UI WGSL"),
            source: wgpu::ShaderSource::Wgsl(std::borrow::Cow::Borrowed(SHADER)),
        });
        let bind_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("01B shared dynamic uniform"),
            entries: &[wgpu::BindGroupLayoutEntry {
                binding: 0,
                visibility: wgpu::ShaderStages::VERTEX_FRAGMENT,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset: true,
                    min_binding_size: None,
                },
                count: None,
            }],
        });
        let layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("01B native shared UI pipeline"),
            bind_group_layouts: &[Some(&bind_layout)],
            immediate_size: 0,
        });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("01B native UI multi-widget render pass"),
            layout: Some(&layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: Some("vs"),
                compilation_options: wgpu::PipelineCompilationOptions::default(),
                buffers: &[],
            },
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: Some("fs"),
                compilation_options: wgpu::PipelineCompilationOptions::default(),
                targets: &[Some(wgpu::ColorTargetState {
                    format,
                    blend: Some(wgpu::BlendState::ALPHA_BLENDING),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: None,
            multisample: wgpu::MultisampleState::default(),
            multiview_mask: None,
            cache: None,
        });
        let uniform = device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("01B persistent bounded 64-command uniform arena"),
            size: (MAX_COMMANDS * UNIFORM_STRIDE) as u64,
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });
        let group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("01B persistent bind group"),
            layout: &bind_layout,
            entries: &[wgpu::BindGroupEntry {
                binding: 0,
                resource: wgpu::BindingResource::Buffer(wgpu::BufferBinding {
                    buffer: &uniform,
                    offset: 0,
                    size: std::num::NonZeroU64::new(80),
                }),
            }],
        });
        Self {
            pipeline,
            uniform,
            group,
            bytes: Vec::with_capacity(6 * UNIFORM_STRIDE),
            last_uploaded: Vec::new(),
            uploads: 0,
            resident_allocations: 2,
        }
    }
    fn params(c: FillRoundedRect, w: f32, h: f32) -> [f32; 20] {
        [
            c.rect.x,
            c.rect.y,
            c.rect.width,
            c.rect.height,
            c.color.r as f32 / 255.,
            c.color.g as f32 / 255.,
            c.color.b as f32 / 255.,
            c.color.a as f32 / 255.,
            w,
            h,
            c.radius,
            0.,
            0.,
            0.,
            0.,
            0.,
            0.,
            0.,
            0.,
            0.,
        ]
    }
    fn stroke_params(
        c: StrokeSegment,
        w: f32,
        h: f32,
    ) -> Result<([f32; 20], blobin_ui_core::layout::Rect), String> {
        let rect = c.bounds().map_err(|e| format!("01E stroke bounds: {e}"))?;
        let start = (c.start.x - rect.x, c.start.y - rect.y);
        let end = (c.end.x - rect.x, c.end.y - rect.y);
        Ok((
            [
                rect.x,
                rect.y,
                rect.width,
                rect.height,
                c.color.r as f32 / 255.,
                c.color.g as f32 / 255.,
                c.color.b as f32 / 255.,
                c.color.a as f32 / 255.,
                w,
                h,
                c.width * 0.5,
                1.,
                start.0,
                start.1,
                end.0,
                end.1,
                0.,
                0.,
                0.,
                0.,
            ],
            rect,
        ))
    }
    fn triangle_params(
        c: FillTriangle,
        w: f32,
        h: f32,
        edge_mask: u8,
        aa: bool,
    ) -> Result<([f32; 20], blobin_ui_core::layout::Rect), String> {
        let rect = c
            .bounds()
            .map_err(|e| format!("01G triangle bounds: {e}"))?;
        // 01I: a one-logical-pixel guard band lets the fragment shader
        // sample BOTH sides of a boundary, not only the triangle interior.
        // The caller's original G03 scissor still clips the expanded quad.
        let rect = if aa {
            blobin_ui_core::layout::Rect::new(
                rect.x - 1.,
                rect.y - 1.,
                rect.width + 2.,
                rect.height + 2.,
            )
        } else {
            rect
        };
        let p = c.vertices.map(|p| (p.x - rect.x, p.y - rect.y));
        Ok((
            [
                rect.x,
                rect.y,
                rect.width,
                rect.height,
                c.color.r as f32 / 255.,
                c.color.g as f32 / 255.,
                c.color.b as f32 / 255.,
                c.color.a as f32 / 255.,
                w,
                h,
                0.,
                if aa { 3. } else { 2. },
                p[0].0,
                p[0].1,
                p[1].0,
                p[1].1,
                p[2].0,
                p[2].1,
                edge_mask as f32,
                0.,
            ],
            rect,
        ))
    }
    fn outer_edge_mask(triangle: &FillTriangle, all: &[FillTriangle]) -> u8 {
        let mut mask = 0u8;
        for i in 0..3 {
            let a = triangle.vertices[i];
            let b = triangle.vertices[(i + 1) % 3];
            let shared = all.iter().any(|other| {
                other.source == triangle.source
                    && other.color == triangle.color
                    && !std::ptr::eq(other, triangle)
                    && (0..3).any(|j| {
                        let p = other.vertices[j];
                        let q = other.vertices[(j + 1) % 3];
                        (p == a && q == b) || (p == b && q == a)
                    })
            });
            if !shared {
                mask |= 1 << i;
            }
        }
        mask
    }
    /// Backward compatible entry point. 01I AA is explicitly opt-in via
    /// encode_with_triangle_aa in a private gated Weston session only.
    /// One render pass, one persistent bind group, one bounded GPU allocation
    /// at initialization. Never create per-command buffers or bind groups.
    #[allow(clippy::too_many_arguments)]
    pub fn encode(
        &mut self,
        queue: &wgpu::Queue,
        encoder: &mut wgpu::CommandEncoder,
        target: &wgpu::TextureView,
        lists: &[&DisplayList],
        logical: (f32, f32),
        scale: f32,
        physical: (u32, u32),
    ) -> Result<DrawReceipt, String> {
        self.encode_with_triangle_aa(
            queue, encoder, target, lists, logical, scale, physical, false,
        )
    }
    #[allow(clippy::too_many_arguments)]
    pub fn encode_with_triangle_aa(
        &mut self,
        queue: &wgpu::Queue,
        encoder: &mut wgpu::CommandEncoder,
        target: &wgpu::TextureView,
        lists: &[&DisplayList],
        logical: (f32, f32),
        scale: f32,
        physical: (u32, u32),
        triangle_aa: bool,
    ) -> Result<DrawReceipt, String> {
        if !logical.0.is_finite()
            || !logical.1.is_finite()
            || logical.0 <= 0.
            || logical.1 <= 0.
            || !scale.is_finite()
            || scale <= 0.
            || physical.0 == 0
            || physical.1 == 0
        {
            return Err("01B invalid viewport".into());
        }
        let count: usize = lists
            .iter()
            .map(|l| l.commands.len() + l.strokes.len() + l.triangles.len())
            .sum();
        if count == 0 || count > MAX_COMMANDS {
            return Err("01B bounded dynamic uniform capacity exceeded".into());
        }
        self.bytes.clear();
        self.bytes.resize(count * UNIFORM_STRIDE, 0);
        let mut rectangles = Vec::with_capacity(count);
        let mut index = 0;
        for list in lists {
            // Intentional per-layer draw order: filled shapes, then strokes.
            // Across layers the input SceneLayer ordering is preserved.
            let shapes = list.commands.iter().map(|c| {
                Ok::<_, String>((
                    c.source,
                    c.clip,
                    c.rect,
                    Self::params(*c, logical.0, logical.1),
                ))
            });
            let triangles = list.triangles.iter().map(|c| {
                c.validated().map_err(|e| e.to_string())?;
                let mask = if triangle_aa {
                    Self::outer_edge_mask(c, &list.triangles)
                } else {
                    7
                };
                let (params, rect) =
                    Self::triangle_params(*c, logical.0, logical.1, mask, triangle_aa)?;
                Ok((c.source, c.clip, rect, params))
            });
            let strokes = list.strokes.iter().map(|c| {
                c.validated().map_err(|e| e.to_string())?;
                let (params, rect) = Self::stroke_params(*c, logical.0, logical.1)?;
                Ok((c.source, c.clip, rect, params))
            });
            for element in shapes.chain(triangles).chain(strokes) {
                let (source, c, r, params) = element?;
                if source != list.source_node {
                    return Err("01E mismatched semantic provenance".into());
                }
                if [c.x, c.y, c.width, c.height, r.x, r.y, r.width, r.height]
                    .iter()
                    .any(|x| !x.is_finite())
                    || c.width < 0.
                    || c.height < 0.
                    || r.width <= 0.
                    || r.height <= 0.
                {
                    return Err("01E command geometry invalid".into());
                }
                for (idx, value) in params.iter().enumerate() {
                    let begin = index * UNIFORM_STRIDE + idx * 4;
                    self.bytes[begin..begin + 4].copy_from_slice(&value.to_ne_bytes());
                }
                let (cw, ch) = (physical.0 as f32, physical.1 as f32);
                // Scissor also uses primitive bounds, avoiding drawing outside
                // the geometric capsule area even with larger ancestor clips.
                let visible = c.intersect(r);
                let x0 = (visible.x * scale).floor().clamp(0., cw) as u32;
                let y0 = (visible.y * scale).floor().clamp(0., ch) as u32;
                let x1 = ((visible.x + visible.width) * scale).ceil().clamp(0., cw) as u32;
                let y1 = ((visible.y + visible.height) * scale).ceil().clamp(0., ch) as u32;
                rectangles.push((x0, y0, x1.saturating_sub(x0), y1.saturating_sub(y0)));
                index += 1;
            }
        }
        let wrote = self.last_uploaded != self.bytes;
        if wrote {
            queue.write_buffer(&self.uniform, 0, &self.bytes);
            self.last_uploaded.clone_from(&self.bytes);
            self.uploads += 1;
        }
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("01B native controls on host Wayland swapchain"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: target,
                    depth_slice: None,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Load,
                        store: wgpu::StoreOp::Store,
                    },
                })],
                ..Default::default()
            });
            pass.set_pipeline(&self.pipeline);
            for (i, (x, y, w, h)) in rectangles.iter().enumerate() {
                if *w == 0 || *h == 0 {
                    continue;
                }
                pass.set_scissor_rect(*x, *y, *w, *h);
                pass.set_bind_group(0, &self.group, &[(i * UNIFORM_STRIDE) as u32]);
                pass.draw(0..6, 0..1);
            }
        }
        let first = lists[0];
        Ok(DrawReceipt {
            commands: count,
            nodes: lists.len(),
            node: first.source_node.slot,
            ui_revision: first.source_ui_revision,
            geometry_epoch: first.layout_epoch,
            uniform_write: wrote,
        })
    }
}
