//! CP-JA4 native Ash Vulkan WSI with typed present-id and present-wait.
//! Dedicated experimental presenter, not a wgpu-hal patch.
use ash::{khr, vk, Device, Entry, Instance};
use blob_frame::{qchain, MappedFrame, SeqPacket};
use raw_window_handle::{HasDisplayHandle, HasWindowHandle, RawDisplayHandle, RawWindowHandle};
use std::{
    env,
    ffi::CStr,
    fs,
    path::PathBuf,
    sync::{
        mpsc::{self, Receiver},
        Arc,
    },
    thread,
    time::{Duration, Instant},
};
use winit::platform::wayland::WindowAttributesExtWayland;
use winit::{
    application::ApplicationHandler,
    event::WindowEvent,
    event_loop::{ActiveEventLoop, ControlFlow, EventLoop},
    window::{Window, WindowId},
};

struct Frame {
    pixels: Vec<u8>,
    scene_sha: String,
    rgba_sha: String,
    epoch: u64,
    seq: usize,
    received: Instant,
}
fn stream(
    socket: PathBuf,
    receipt: PathBuf,
    frames: usize,
    sender: mpsc::SyncSender<Result<Frame, String>>,
) {
    let execute = || -> Result<(), String> {
        let cpu: serde_json::Value =
            serde_json::from_slice(&fs::read(&receipt).map_err(|e| e.to_string())?)
                .map_err(|e| e.to_string())?;
        let canonical = cpu["stages"].as_array().ok_or("CPU_STAGES_MISSING")?;
        if canonical.len() != 5 {
            return Err("CANONICAL_FIVE_SCENES_REQUIRED".into());
        }
        for seq in 0..frames {
            let conn = SeqPacket::connect(&socket).map_err(|e| e.to_string())?;
            conn.require_same_uid().map_err(|e| e.to_string())?;
            conn.set_read_timeout(Some(Duration::from_secs(5)))
                .map_err(|e| e.to_string())?;
            let request = serde_json::json!({"version":"QCHAIN-GPU-STREAM-v1","seq":seq});
            conn.send(
                &serde_json::to_vec(&request).map_err(|e| e.to_string())?,
                &[],
            )
            .map_err(|e| e.to_string())?;
            let mut packet = conn.recv().map_err(|e| e.to_string())?;
            if packet.fds.len() != 1 {
                return Err("STREAM_MEMFD_COUNT_INVALID".into());
            }
            let m: serde_json::Value = serde_json::from_slice(&packet.bytes)
                .map_err(|_| "STREAM_METADATA_JSON_INVALID")?;
            let stage = seq.min(4);
            let canonical_scene = &canonical[stage];
            if m["version"] != "QCHAIN-GPU-STREAM-v1"
                || m["seq"].as_u64() != Some(seq as u64)
                || m["stage"].as_u64() != Some(stage as u64)
                || m["scene_sha256"] != canonical_scene["scene_sha256"]
                || m["semantic_digest"] != canonical_scene["f2_semantic_digest"]
                || m["backend"] != "Vulkan/WGSL"
                || m["source"] != "CP-F-PersistentSession"
                || m["compute_source_commit"] != "5132cf59b3842e27dcacf89bfe7060e807706e90"
                || m["bytes"] != 786432
                || m["stride"] != 2048
                || m["width"] != 512
                || m["height"] != 384
                || m["zero_copy"] != false
            {
                return Err("STREAM_METADATA_AUTHORITY_MISMATCH".into());
            }
            let stat = rustix::fs::fstat(&packet.fds[0]).map_err(|e| e.to_string())?;
            if stat.st_size != 786432 {
                return Err("STREAM_MEMFD_SIZE_INVALID".into());
            }
            let mapped =
                MappedFrame::map(packet.fds.remove(0), 786432).map_err(|e| e.to_string())?;
            let hash = qchain::digest(mapped.bytes());
            if m["pixel_sha256"].as_str() != Some(hash.as_str()) {
                return Err("STREAM_PIXEL_INTEGRITY_FAILED".into());
            }
            let received = Instant::now();
            let frame = Frame {
                pixels: mapped.bytes().to_vec(),
                seq,
                scene_sha: m["scene_sha256"].as_str().unwrap().into(),
                rgba_sha: hash,
                epoch: stage as u64,
                received,
            };
            if sender.send(Ok(frame)).is_err() {
                return Ok(());
            }
        }
        Ok(())
    };
    if let Err(error) = execute() {
        let _ = sender.send(Err(error));
    }
}
struct Native {
    _window: Arc<Window>,
    _entry: Entry,
    instance: Instance,
    surface_api: khr::surface::Instance,
    surface: vk::SurfaceKHR,
    device: Device,
    swap_api: khr::swapchain::Device,
    wait_api: khr::present_wait::Device,
    swapchain: vk::SwapchainKHR,
    queue: vk::Queue,
    images: Vec<vk::Image>,
    layouts: Vec<vk::ImageLayout>,
    format: vk::Format,
    pool: vk::CommandPool,
    cmd: vk::CommandBuffer,
    staging: vk::Buffer,
    memory: vk::DeviceMemory,
    mapped: *mut u8,
    acquired: vk::Semaphore,
    rendered: vk::Semaphore,
    fence: vk::Fence,
}
fn err<T: std::fmt::Debug>(x: T) -> String {
    format!("{x:?}")
}
impl Native {
    fn new(window: Arc<Window>) -> Result<Self, String> {
        let entry = unsafe { Entry::load().map_err(err)? };
        let display = window.display_handle().map_err(err)?.as_raw();
        let wh = window.window_handle().map_err(err)?.as_raw();
        let (RawDisplayHandle::Wayland(d), RawWindowHandle::Wayland(w)) = (display, wh) else {
            return Err("ONLY_WAYLAND_HANDLES_ALLOWED".into());
        };
        let extensions = [
            khr::surface::NAME.as_ptr(),
            khr::wayland_surface::NAME.as_ptr(),
        ];
        let app = vk::ApplicationInfo::default().api_version(vk::API_VERSION_1_3);
        let info = vk::InstanceCreateInfo::default()
            .application_info(&app)
            .enabled_extension_names(&extensions);
        let instance = unsafe { entry.create_instance(&info, None).map_err(err)? };
        let wayland = khr::wayland_surface::Instance::new(&entry, &instance);
        let surface = unsafe {
            wayland
                .create_wayland_surface(
                    &vk::WaylandSurfaceCreateInfoKHR::default()
                        .display(d.display.as_ptr())
                        .surface(w.surface.as_ptr()),
                    None,
                )
                .map_err(err)?
        };
        let surface_api = khr::surface::Instance::new(&entry, &instance);
        let mut selected = None;
        for gpu in unsafe { instance.enumerate_physical_devices().map_err(err)? } {
            let props = unsafe { instance.get_physical_device_properties(gpu) };
            let name = unsafe { CStr::from_ptr(props.device_name.as_ptr()) }.to_string_lossy();
            if name != "NVIDIA GeForce RTX 3070" {
                continue;
            }
            let ext = unsafe {
                instance
                    .enumerate_device_extension_properties(gpu)
                    .map_err(err)?
            };
            let supports = |req: &CStr| {
                ext.iter()
                    .any(|e| (unsafe { CStr::from_ptr(e.extension_name.as_ptr()) }) == req)
            };
            if ![
                khr::swapchain::NAME,
                khr::present_id::NAME,
                khr::present_wait::NAME,
            ]
            .iter()
            .all(|&req| supports(req))
            {
                return Err("PRESENT_ID_WAIT_EXTENSION_ABSENT".into());
            }
            let mut id = vk::PhysicalDevicePresentIdFeaturesKHR::default();
            let mut wait = vk::PhysicalDevicePresentWaitFeaturesKHR::default();
            let mut queried = vk::PhysicalDeviceFeatures2::default()
                .push_next(&mut id)
                .push_next(&mut wait);
            unsafe {
                instance.get_physical_device_features2(gpu, &mut queried);
            }
            if id.present_id == 0 || wait.present_wait == 0 {
                return Err("PRESENT_ID_WAIT_FEATURE_ABSENT".into());
            }
            let families = unsafe { instance.get_physical_device_queue_family_properties(gpu) };
            for (n, f) in families.iter().enumerate() {
                let present = unsafe {
                    surface_api
                        .get_physical_device_surface_support(gpu, n as u32, surface)
                        .map_err(err)?
                };
                if f.queue_flags.contains(vk::QueueFlags::GRAPHICS) && present {
                    selected = Some((gpu, n as u32));
                    break;
                }
            }
            if selected.is_some() {
                break;
            }
        }
        let (physical, family) = selected.ok_or("RTX3070_PRESENT_QUEUE_NOT_FOUND")?;
        let priorities = [1.0f32];
        let qinfo = [vk::DeviceQueueCreateInfo::default()
            .queue_family_index(family)
            .queue_priorities(&priorities)];
        let names = [
            khr::swapchain::NAME.as_ptr(),
            khr::present_id::NAME.as_ptr(),
            khr::present_wait::NAME.as_ptr(),
        ];
        let mut id_feature = vk::PhysicalDevicePresentIdFeaturesKHR::default().present_id(true);
        let mut wait_feature =
            vk::PhysicalDevicePresentWaitFeaturesKHR::default().present_wait(true);
        let mut features = vk::PhysicalDeviceFeatures2::default()
            .push_next(&mut id_feature)
            .push_next(&mut wait_feature);
        let device_info = vk::DeviceCreateInfo::default()
            .queue_create_infos(&qinfo)
            .enabled_extension_names(&names)
            .push_next(&mut features);
        let device = unsafe {
            instance
                .create_device(physical, &device_info, None)
                .map_err(err)?
        };
        let queue = unsafe { device.get_device_queue(family, 0) };
        let swap_api = khr::swapchain::Device::new(&instance, &device);
        let wait_api = khr::present_wait::Device::new(&instance, &device);

        let caps = unsafe {
            surface_api
                .get_physical_device_surface_capabilities(physical, surface)
                .map_err(err)?
        };
        if !caps
            .supported_usage_flags
            .contains(vk::ImageUsageFlags::TRANSFER_DST)
        {
            return Err("SWAPCHAIN_TRANSFER_DST_NOT_SUPPORTED".into());
        }
        let formats = unsafe {
            surface_api
                .get_physical_device_surface_formats(physical, surface)
                .map_err(err)?
        };
        let format = formats
            .iter()
            .find(|x| x.format == vk::Format::R8G8B8A8_UNORM)
            .or_else(|| {
                formats
                    .iter()
                    .find(|x| x.format == vk::Format::R8G8B8A8_SRGB)
            })
            .or_else(|| {
                formats
                    .iter()
                    .find(|x| x.format == vk::Format::B8G8R8A8_UNORM)
            })
            .or_else(|| {
                formats
                    .iter()
                    .find(|x| x.format == vk::Format::B8G8R8A8_SRGB)
            })
            .ok_or("SWAPCHAIN_SUPPORTED_RGBA_FORMAT_MISSING")?;
        let extent = if caps.current_extent.width == u32::MAX {
            vk::Extent2D {
                width: 512,
                height: 384,
            }
        } else {
            caps.current_extent
        };
        if extent.width != 512 || extent.height != 384 {
            return Err(format!("SWAPCHAIN_WRONG_DIMENSIONS {extent:?}"));
        }
        let mode = vk::PresentModeKHR::FIFO;
        let count = 2u32.max(caps.min_image_count);
        if caps.max_image_count != 0 && count > caps.max_image_count {
            return Err("SWAPCHAIN_TOO_FEW_IMAGES".into());
        }
        let alpha = [
            vk::CompositeAlphaFlagsKHR::OPAQUE,
            vk::CompositeAlphaFlagsKHR::INHERIT,
            vk::CompositeAlphaFlagsKHR::PRE_MULTIPLIED,
        ]
        .into_iter()
        .find(|f| caps.supported_composite_alpha.contains(*f))
        .ok_or("SWAPCHAIN_COMPOSITE_ALPHA_UNSUPPORTED")?;
        let desc = vk::SwapchainCreateInfoKHR::default()
            .surface(surface)
            .min_image_count(count)
            .image_color_space(format.color_space)
            .image_format(format.format)
            .image_extent(extent)
            .image_array_layers(1)
            .image_usage(vk::ImageUsageFlags::TRANSFER_DST)
            .image_sharing_mode(vk::SharingMode::EXCLUSIVE)
            .pre_transform(caps.current_transform)
            .composite_alpha(alpha)
            .present_mode(mode)
            .clipped(true);
        let swapchain = unsafe { swap_api.create_swapchain(&desc, None).map_err(err)? };
        let images = unsafe { swap_api.get_swapchain_images(swapchain).map_err(err)? };
        let layouts = vec![vk::ImageLayout::UNDEFINED; images.len()];
        let pool = unsafe {
            device
                .create_command_pool(
                    &vk::CommandPoolCreateInfo::default()
                        .queue_family_index(family)
                        .flags(vk::CommandPoolCreateFlags::RESET_COMMAND_BUFFER),
                    None,
                )
                .map_err(err)?
        };
        let cmd = unsafe {
            device
                .allocate_command_buffers(
                    &vk::CommandBufferAllocateInfo::default()
                        .command_pool(pool)
                        .level(vk::CommandBufferLevel::PRIMARY)
                        .command_buffer_count(1),
                )
                .map_err(err)?
        }[0];
        let size = 786432u64;
        let staging = unsafe {
            device
                .create_buffer(
                    &vk::BufferCreateInfo::default()
                        .size(size)
                        .usage(vk::BufferUsageFlags::TRANSFER_SRC)
                        .sharing_mode(vk::SharingMode::EXCLUSIVE),
                    None,
                )
                .map_err(err)?
        };
        let requirements = unsafe { device.get_buffer_memory_requirements(staging) };
        let properties = unsafe { instance.get_physical_device_memory_properties(physical) };
        let index = (0..properties.memory_type_count)
            .find(|idx| {
                requirements.memory_type_bits & (1 << idx) != 0
                    && properties.memory_types[*idx as usize]
                        .property_flags
                        .contains(
                            vk::MemoryPropertyFlags::HOST_VISIBLE
                                | vk::MemoryPropertyFlags::HOST_COHERENT,
                        )
            })
            .ok_or("HOST_COHERENT_STAGING_MEMORY_UNAVAILABLE")?;
        let memory = unsafe {
            device
                .allocate_memory(
                    &vk::MemoryAllocateInfo::default()
                        .allocation_size(requirements.size)
                        .memory_type_index(index),
                    None,
                )
                .map_err(err)?
        };
        unsafe {
            device.bind_buffer_memory(staging, memory, 0).map_err(err)?;
        }
        let mapped = unsafe {
            device
                .map_memory(memory, 0, size, vk::MemoryMapFlags::empty())
                .map_err(err)?
        } as *mut u8;
        let sem = vk::SemaphoreCreateInfo::default();
        let acquired = unsafe { device.create_semaphore(&sem, None).map_err(err)? };
        let rendered = unsafe { device.create_semaphore(&sem, None).map_err(err)? };
        let fence = unsafe {
            device
                .create_fence(
                    &vk::FenceCreateInfo::default().flags(vk::FenceCreateFlags::SIGNALED),
                    None,
                )
                .map_err(err)?
        };
        println!("CPJA4_DEVICE_READY format={:?} images={} enabled=VK_KHR_swapchain,VK_KHR_present_id,VK_KHR_present_wait present_features=true,true",
            format.format,images.len());
        Ok(Self {
            _window: window,
            _entry: entry,
            instance,
            surface_api,
            surface,
            device,
            swap_api,
            wait_api,
            swapchain,
            queue,
            images,
            layouts,
            format: format.format,
            pool,
            cmd,
            staging,
            memory,
            mapped,
            acquired,
            rendered,
            fence,
        })
    }

    fn present(&mut self, frame: &Frame) -> Result<u64, String> {
        if frame.pixels.len() != 786432 {
            return Err("FRAME_PIXEL_BYTES_INVALID".into());
        }
        let id = (frame.seq as u64) + 1;
        // Exactly one in-flight present: typed wait ensures swapchain semaphore reuse is safe.
        unsafe {
            self.device
                .wait_for_fences(&[self.fence], true, 5_000_000_000)
                .map_err(err)?;
        }
        let (index, suboptimal) = unsafe {
            self.swap_api
                .acquire_next_image(
                    self.swapchain,
                    5_000_000_000,
                    self.acquired,
                    vk::Fence::null(),
                )
                .map_err(err)?
        };
        if suboptimal {
            return Err("ACQUIRED_SUBOPTIMAL_SWAPCHAIN_HOLD".into());
        }
        unsafe {
            self.device.reset_fences(&[self.fence]).map_err(err)?;
        }
        let mut rgba = frame.pixels.clone();
        if [vk::Format::B8G8R8A8_SRGB, vk::Format::B8G8R8A8_UNORM].contains(&self.format) {
            for pixel in rgba.chunks_exact_mut(4) {
                pixel.swap(0, 2);
            }
        }
        unsafe {
            std::ptr::copy_nonoverlapping(rgba.as_ptr(), self.mapped, rgba.len());
        }
        unsafe {
            self.device
                .reset_command_buffer(self.cmd, vk::CommandBufferResetFlags::empty())
                .map_err(err)?;
            self.device
                .begin_command_buffer(
                    self.cmd,
                    &vk::CommandBufferBeginInfo::default()
                        .flags(vk::CommandBufferUsageFlags::ONE_TIME_SUBMIT),
                )
                .map_err(err)?;
        }
        let image = self.images[index as usize];
        let old = self.layouts[index as usize];
        let range = vk::ImageSubresourceRange::default()
            .aspect_mask(vk::ImageAspectFlags::COLOR)
            .base_mip_level(0)
            .level_count(1)
            .base_array_layer(0)
            .layer_count(1);
        let to_copy = vk::ImageMemoryBarrier::default()
            .src_access_mask(if old == vk::ImageLayout::PRESENT_SRC_KHR {
                vk::AccessFlags::MEMORY_READ
            } else {
                vk::AccessFlags::empty()
            })
            .dst_access_mask(vk::AccessFlags::TRANSFER_WRITE)
            .old_layout(old)
            .new_layout(vk::ImageLayout::TRANSFER_DST_OPTIMAL)
            .src_queue_family_index(vk::QUEUE_FAMILY_IGNORED)
            .dst_queue_family_index(vk::QUEUE_FAMILY_IGNORED)
            .image(image)
            .subresource_range(range);
        unsafe {
            self.device.cmd_pipeline_barrier(
                self.cmd,
                vk::PipelineStageFlags::TOP_OF_PIPE,
                vk::PipelineStageFlags::TRANSFER,
                vk::DependencyFlags::empty(),
                &[],
                &[],
                &[to_copy],
            );
        }
        let image_range = vk::ImageSubresourceLayers::default()
            .aspect_mask(vk::ImageAspectFlags::COLOR)
            .mip_level(0)
            .base_array_layer(0)
            .layer_count(1);
        let copy = vk::BufferImageCopy::default()
            .buffer_offset(0)
            .buffer_row_length(512)
            .buffer_image_height(384)
            .image_subresource(image_range)
            .image_offset(vk::Offset3D { x: 0, y: 0, z: 0 })
            .image_extent(vk::Extent3D {
                width: 512,
                height: 384,
                depth: 1,
            });
        unsafe {
            self.device.cmd_copy_buffer_to_image(
                self.cmd,
                self.staging,
                image,
                vk::ImageLayout::TRANSFER_DST_OPTIMAL,
                &[copy],
            );
        }
        let to_present = vk::ImageMemoryBarrier::default()
            .src_access_mask(vk::AccessFlags::TRANSFER_WRITE)
            .dst_access_mask(vk::AccessFlags::MEMORY_READ)
            .old_layout(vk::ImageLayout::TRANSFER_DST_OPTIMAL)
            .new_layout(vk::ImageLayout::PRESENT_SRC_KHR)
            .src_queue_family_index(vk::QUEUE_FAMILY_IGNORED)
            .dst_queue_family_index(vk::QUEUE_FAMILY_IGNORED)
            .image(image)
            .subresource_range(range);
        unsafe {
            self.device.cmd_pipeline_barrier(
                self.cmd,
                vk::PipelineStageFlags::TRANSFER,
                vk::PipelineStageFlags::BOTTOM_OF_PIPE,
                vk::DependencyFlags::empty(),
                &[],
                &[],
                &[to_present],
            );
            self.device.end_command_buffer(self.cmd).map_err(err)?;
        }
        self.layouts[index as usize] = vk::ImageLayout::PRESENT_SRC_KHR;
        let wait = [self.acquired];
        let signals = [self.rendered];
        let stages = [vk::PipelineStageFlags::TRANSFER];
        let cmds = [self.cmd];
        let submits = [vk::SubmitInfo::default()
            .wait_semaphores(&wait)
            .wait_dst_stage_mask(&stages)
            .command_buffers(&cmds)
            .signal_semaphores(&signals)];
        unsafe {
            self.device
                .queue_submit(self.queue, &submits, self.fence)
                .map_err(err)?;
        }
        let swapchains = [self.swapchain];
        let indices = [index];
        let ids = [id];
        let mut present_ids = vk::PresentIdKHR::default().present_ids(&ids);
        let info = vk::PresentInfoKHR::default()
            .wait_semaphores(&signals)
            .swapchains(&swapchains)
            .image_indices(&indices)
            .push_next(&mut present_ids);
        let suboptimal = unsafe {
            self.swap_api
                .queue_present(self.queue, &info)
                .map_err(err)?
        };
        if suboptimal {
            return Err("PRESENT_SUBOPTIMAL_SWAPCHAIN_HOLD".into());
        }
        let ack = unsafe {
            self.wait_api
                .wait_for_present(self.swapchain, id, 5_000_000_000)
        };
        match ack {
            Ok(()) => {
                println!("CPJA4_TYPED_PRESENT_ACK seq={} present_id={} scene_sha256={} rgba_sha256={} wait_result=VK_SUCCESS",frame.seq,id,frame.scene_sha,frame.rgba_sha);
                Ok(id)
            }
            Err(error) => Err(format!(
                "CPJA4_PRESENT_WAIT_FAILED seq={} id={} error={:?}",
                frame.seq, id, error
            )),
        }
    }
}

impl Drop for Native {
    fn drop(&mut self) {
        unsafe {
            let _ = self.device.device_wait_idle();
            self.device.destroy_fence(self.fence, None);
            self.device.destroy_semaphore(self.rendered, None);
            self.device.destroy_semaphore(self.acquired, None);
            self.device.unmap_memory(self.memory);
            self.device.destroy_buffer(self.staging, None);
            self.device.free_memory(self.memory, None);
            self.device.destroy_command_pool(self.pool, None);
            self.swap_api.destroy_swapchain(self.swapchain, None);
            self.device.destroy_device(None);
            self.surface_api.destroy_surface(self.surface, None);
            self.instance.destroy_instance(None);
        }
    }
}
struct Viewer {
    gpu: Option<Native>,
    receiver: Receiver<Result<Frame, String>>,
    next: Instant,
    submitted: usize,
    target: usize,
    error: Option<String>,
    started: Instant,
}
impl ApplicationHandler for Viewer {
    fn resumed(&mut self, el: &ActiveEventLoop) {
        if self.gpu.is_some() {
            return;
        }
        let attrs = Window::default_attributes()
            .with_title("QCHAIN CP-JA4 · native Vulkan typed presentation")
            .with_name("qchain-cpja4-vk-wsi", "qchain-cpja4-vk-wsi")
            .with_inner_size(winit::dpi::LogicalSize::new(512.0, 384.0))
            .with_resizable(false);
        match el.create_window(attrs).map_err(err).and_then(|w| {
            w.set_cursor_visible(false);
            Native::new(Arc::new(w))
        }) {
            Ok(gpu) => {
                self.gpu = Some(gpu);
                self.next = Instant::now() + Duration::from_millis(120);
            }
            Err(e) => {
                self.error = Some(e);
                el.exit();
            }
        }
    }
    fn window_event(&mut self, el: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        if let WindowEvent::CloseRequested = event {
            self.error = Some("CPJA4_WINDOW_CLOSED_BEFORE_ALL_ACKS".into());
            el.exit();
        }
    }
    fn about_to_wait(&mut self, el: &ActiveEventLoop) {
        if self.gpu.is_none() {
            return;
        }
        if self.submitted == self.target {
            println!("CPJA4_VK_STREAM_COMPLETE submitted={}", self.target);
            println!("CPJA4_TYPED_STREAM_COMPLETE source_frames={} typed_acknowledgements={} sentinel_frames=0",self.target,self.submitted);
            el.exit();
            return;
        }
        let now = Instant::now();
        if now < self.next {
            el.set_control_flow(ControlFlow::WaitUntil(self.next));
            return;
        }
        match self.receiver.try_recv() {
            Ok(Ok(frame)) => {
                if frame.seq != self.submitted {
                    self.error = Some("CPJA4_FRAME_SEQUENCE_DRIFT".into());
                    el.exit();
                    return;
                }
                let started = Instant::now();
                let wait = self.gpu.as_mut().unwrap().present(&frame);
                if let Err(e) = wait {
                    self.error = Some(e);
                    el.exit();
                    return;
                }
                self.submitted += 1;
                println!("CPJA4_VK_PRESENT_SUBMITTED seq={} stage={} elapsed_us={} received_to_submit_us={} epoch={} scene_sha256={} rgba_sha256={} dimensions=512x384",
                    frame.seq,frame.epoch,self.started.elapsed().as_micros(),
                    frame.received.elapsed().as_micros(),frame.epoch,frame.scene_sha,frame.rgba_sha);
                println!(
                    "CPJA4_WAIT_DURATION seq={} microseconds={}",
                    frame.seq,
                    started.elapsed().as_micros()
                );
                self.next = Instant::now() + Duration::from_millis(33);
                el.set_control_flow(ControlFlow::WaitUntil(self.next));
            }
            Ok(Err(e)) => {
                self.error = Some(e);
                el.exit();
            }
            Err(mpsc::TryRecvError::Disconnected) => {
                self.error = Some("CPJA4_SOURCE_DISCONNECTED".into());
                el.exit();
            }
            Err(mpsc::TryRecvError::Empty) => {
                self.next = now + Duration::from_millis(4);
                el.set_control_flow(ControlFlow::WaitUntil(self.next));
            }
        }
    }
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = env::args().skip(1);
    let socket = PathBuf::from(args.next().ok_or("SOCKET_REQUIRED")?);
    let receipt = PathBuf::from(args.next().ok_or("CPU_RECEIPT_REQUIRED")?);
    let target: usize = args.next().ok_or("FRAME_COUNT_REQUIRED")?.parse()?;
    if args.next().is_some() || target != 120 {
        return Err("CPJA4_REQUIRES_EXACT_120_FRAMES".into());
    }
    if env::var_os("WAYLAND_DISPLAY").is_none() {
        return Err("WAYLAND_DISPLAY_REQUIRED".into());
    }
    let (sender, receiver) = mpsc::sync_channel(1);
    let worker = thread::spawn(move || stream(socket, receipt, target, sender));
    let el = EventLoop::new()?;
    let mut viewer = Viewer {
        gpu: None,
        receiver,
        next: Instant::now(),
        submitted: 0,
        target,
        error: None,
        started: Instant::now(),
    };
    el.set_control_flow(ControlFlow::Wait);
    el.run_app(&mut viewer)?;
    if let Some(e) = viewer.error {
        return Err(e.into());
    }
    if viewer.submitted != target {
        return Err("CPJA4_INCOMPLETE_TYPED_ACKS".into());
    }
    worker.join().map_err(|_| "CPJA4_STREAM_THREAD_FAILED")?;
    Ok(())
}
