//! BLOB-FRAME-v1: the presentation-side contract between the blob.in showcase
//! surface and a render runtime. See `docs/BLOB-FRAME-v1.md`.
//!
//! This crate contains no geometry and no renderer. It moves bounded JSON
//! control messages and sealed, read-only pixel buffers over a private Unix
//! SEQPACKET socket.

pub mod client;
pub mod qchain;
pub mod qchain_gpu;
pub mod memfd;
pub mod proto;
pub mod transport;

pub use client::{Client, ClientConfig, ClientEvent, ReceivedFrame, Session};
pub use memfd::MappedFrame;
pub use proto::*;
pub use transport::{default_socket_path, default_test_socket_path, SeqListener, SeqPacket, TransportError};
