//! Resource accounting. One sequential test so that the process-wide descriptor
//! and mapping counts are not disturbed by concurrently running tests.

mod common;

use std::time::Duration;

use blob_frame::{Backend, ClientEvent, ViewMode};
use blob_frame_testserver::{Fault, ServerConfig};
use common::{frame_mappings, open_fds, Harness};

fn settle() {
    std::thread::sleep(Duration::from_millis(50));
}

#[test]
fn descriptors_and_mappings_are_released() {
    let fds0 = open_fds();

    // 300 frames of varying size, each dropped after inspection.
    {
        let mut h = Harness::start(ServerConfig::default());
        h.connected();
        for i in 0..300u32 {
            let r = h.request(64 + i % 50, 64 + (i * 7) % 90, Backend::Cpu, ViewMode::Distance);
            drop(h.expect_frame(&r));
        }
        assert_eq!(frame_mappings(), 0, "no mapping outlives its frame");
    }
    settle();
    assert_eq!(open_fds(), fds0, "after 300 frames");

    // Every rejected-frame fault: the descriptor is closed, nothing stays mapped.
    for fault in [
        Fault::WrongSize,
        Fault::Truncated,
        Fault::Unsealed,
        Fault::BackendMismatch,
        Fault::WrongRevision,
        Fault::PaddedStride,
        Fault::BadFormat,
        Fault::BadDigest,
        Fault::ExtraDescriptor,
        Fault::NoDescriptor,
    ] {
        {
            let mut h = Harness::start(ServerConfig { fault, fault_every: 1, ..ServerConfig::default() });
            h.connected();
            for _ in 0..20 {
                h.request(128, 96, Backend::Cuda, ViewMode::Normals);
                match h.next() {
                    ClientEvent::FrameRejected { .. } => {}
                    other => panic!("{fault:?}: {other:?}"),
                }
            }
            assert_eq!(frame_mappings(), 0, "{fault:?}");
        }
        settle();
        assert_eq!(open_fds(), fds0, "{fault:?}");
    }

    // Session-ending violations with a descriptor attached.
    for fault in [Fault::WrongId, Fault::ExtraField] {
        {
            let mut h = Harness::start(ServerConfig { fault, fault_every: 1, ..ServerConfig::default() });
            for _ in 0..5 {
                h.connected();
                h.request(128, 96, Backend::Cpu, ViewMode::Lit);
                assert!(matches!(h.next(), ClientEvent::RequestFailed { .. }), "{fault:?}");
                assert!(matches!(h.next(), ClientEvent::Disconnected { .. }), "{fault:?}");
            }
            assert_eq!(frame_mappings(), 0, "{fault:?}");
        }
        settle();
        assert_eq!(open_fds(), fds0, "{fault:?}");
    }

    // Shutdown with an unanswered request in flight is prompt and clean.
    {
        let mut h = Harness::start(ServerConfig { fault: Fault::Drop, ..ServerConfig::default() });
        h.connected();
        h.request(64, 64, Backend::Cpu, ViewMode::Distance);
        let t = std::time::Instant::now();
        h.client.shutdown();
        assert!(t.elapsed() < Duration::from_millis(500), "shutdown took {:?}", t.elapsed());
    }
    settle();
    assert_eq!(open_fds(), fds0, "after shutdown with a request in flight");

    // Frames still held by the application at shutdown stay valid, then release cleanly.
    {
        let mut h = Harness::start(ServerConfig::default());
        h.connected();
        let r = h.request(256, 128, Backend::Vulkan, ViewMode::Lit);
        let f = h.expect_frame(&r);
        h.client.shutdown();
        common::check_pixels(&f);
        assert_eq!(frame_mappings(), 1);
        drop(f);
        assert_eq!(frame_mappings(), 0);
    }
    settle();
    assert_eq!(open_fds(), fds0, "final");
}
