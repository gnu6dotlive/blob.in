//! Runtime VK_KHR_present_id/wait capability witness; DOES NOT enable on wgpu device.
use ash::{vk, Entry};
use std::{error::Error, ffi::CStr};

fn probe() -> Result<(), Box<dyn Error>> {
    let entry = unsafe { Entry::load()? };
    let app = vk::ApplicationInfo::default().api_version(vk::API_VERSION_1_3);
    let info = vk::InstanceCreateInfo::default().application_info(&app);
    let instance = unsafe { entry.create_instance(&info, None)? };
    let result = (|| -> Result<(), Box<dyn Error>> {
        for gpu in unsafe { instance.enumerate_physical_devices()? } {
            let props = unsafe { instance.get_physical_device_properties(gpu) };
            let name = unsafe { CStr::from_ptr(props.device_name.as_ptr()) }
                .to_string_lossy()
                .to_string();
            let extensions = unsafe { instance.enumerate_device_extension_properties(gpu)? };
            let supports = |name: &CStr| {
                extensions.iter().any(|ext| {
                    let n = unsafe { CStr::from_ptr(ext.extension_name.as_ptr()) };
                    n == name
                })
            };
            let present_id_supported = supports(ash::khr::present_id::NAME);
            let present_wait_supported = supports(ash::khr::present_wait::NAME);
            let mut id_features = vk::PhysicalDevicePresentIdFeaturesKHR::default();
            let mut wait_features = vk::PhysicalDevicePresentWaitFeaturesKHR::default();
            let mut features = vk::PhysicalDeviceFeatures2::default()
                .push_next(&mut id_features)
                .push_next(&mut wait_features);
            unsafe {
                instance.get_physical_device_features2(gpu, &mut features);
            }
            println!(
                "CPJA3_VK_DEVICE name={name:?} vendor=0x{:04x} device=0x{:04x} present_id_supported={} present_wait_supported={} present_id_feature={} present_wait_feature={}",
                props.vendor_id, props.device_id,
                present_id_supported, present_wait_supported,
                id_features.present_id != 0, wait_features.present_wait != 0
            );
        }
        Ok(())
    })();
    unsafe {
        instance.destroy_instance(None);
    }
    result
}
fn main() {
    if let Err(error) = probe() {
        eprintln!("CPJA3_VULKAN_PROBE_FAILED {error}");
        std::process::exit(1);
    }
}
