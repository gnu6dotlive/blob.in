//! Sealed memfd pixel buffers.
//!
//! The receiver maps a buffer only if the sender sealed it against writes,
//! shrinking and growing: contents cannot change under the reader (no tearing)
//! and the file cannot be truncated after mapping (no SIGBUS).

use std::fs::File;
use std::io::{self, Write};
use std::os::fd::OwnedFd;
use std::ptr::NonNull;

use rustix::fs::{FileType, MemfdFlags, SealFlags};
use rustix::mm::{MapFlags, ProtFlags};

use crate::proto::MAX_FRAME_BYTES;

pub const REQUIRED_SEALS: SealFlags =
    SealFlags::SEAL.union(SealFlags::SHRINK).union(SealFlags::GROW).union(SealFlags::WRITE);

/// Creates a memfd holding `bytes`, sealed with [`REQUIRED_SEALS`].
pub fn sealed_memfd(name: &str, bytes: &[u8]) -> io::Result<OwnedFd> {
    memfd_with(name, bytes, true)
}

/// Like [`sealed_memfd`] but sealing is optional. Unsealed buffers exist only for fault injection.
#[doc(hidden)]
pub fn memfd_with(name: &str, bytes: &[u8], seal: bool) -> io::Result<OwnedFd> {
    let fd = rustix::fs::memfd_create(name, MemfdFlags::CLOEXEC | MemfdFlags::ALLOW_SEALING)?;
    let mut file = File::from(fd);
    file.write_all(bytes)?;
    let fd = OwnedFd::from(file);
    if seal {
        rustix::fs::fcntl_add_seals(&fd, REQUIRED_SEALS)?;
    }
    Ok(fd)
}

#[derive(Debug, thiserror::Error, PartialEq)]
pub enum MapError {
    #[error("descriptor is not a sealable memfd")]
    NotSealable,
    #[error("buffer is not sealed (have {have:?}, need {REQUIRED_SEALS:?})")]
    Unsealed { have: SealFlags },
    #[error("descriptor is not a regular file")]
    NotRegular,
    #[error("buffer holds {have} bytes, frame needs {need}")]
    Truncated { have: u64, need: u64 },
    #[error("frame length {0} outside 1..={MAX_FRAME_BYTES}")]
    BadLength(u64),
    #[error("{0}")]
    Os(String),
}

/// A read-only shared mapping of a sealed pixel buffer. The descriptor is closed
/// once mapped; the mapping is released on drop.
pub struct MappedFrame {
    ptr: NonNull<u8>,
    len: usize,
}

// SAFETY: the mapping is PROT_READ of a write-sealed, size-sealed memfd; nobody can
// mutate or shrink it, so shared references from any thread are sound.
unsafe impl Send for MappedFrame {}
unsafe impl Sync for MappedFrame {}

impl MappedFrame {
    pub fn map(fd: OwnedFd, len: u64) -> Result<Self, MapError> {
        if len == 0 || len > MAX_FRAME_BYTES {
            return Err(MapError::BadLength(len));
        }
        let have = rustix::fs::fcntl_get_seals(&fd).map_err(|_| MapError::NotSealable)?;
        if !have.contains(REQUIRED_SEALS) {
            return Err(MapError::Unsealed { have });
        }
        let st = rustix::fs::fstat(&fd).map_err(|e| MapError::Os(e.to_string()))?;
        if FileType::from_raw_mode(st.st_mode) != FileType::RegularFile {
            return Err(MapError::NotRegular);
        }
        let size = st.st_size as u64;
        if size < len {
            return Err(MapError::Truncated { have: size, need: len });
        }
        // SAFETY: fresh mapping of a sealed file at least `len` bytes long.
        let ptr = unsafe {
            rustix::mm::mmap(std::ptr::null_mut(), len as usize, ProtFlags::READ, MapFlags::SHARED, &fd, 0)
        }
        .map_err(|e| MapError::Os(e.to_string()))?;
        Ok(Self { ptr: NonNull::new(ptr.cast()).expect("mmap returned null"), len: len as usize })
    }

    pub fn bytes(&self) -> &[u8] {
        // SAFETY: valid read-only mapping of `len` bytes for the lifetime of self.
        unsafe { std::slice::from_raw_parts(self.ptr.as_ptr(), self.len) }
    }
}

impl Drop for MappedFrame {
    fn drop(&mut self) {
        // SAFETY: unmapping exactly what `map` mapped.
        unsafe {
            let _ = rustix::mm::munmap(self.ptr.as_ptr().cast(), self.len);
        }
    }
}

impl std::fmt::Debug for MappedFrame {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("MappedFrame").field("len", &self.len).finish()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sealed_roundtrip() {
        let fd = sealed_memfd("t", &[1, 2, 3, 4, 5, 6, 7, 8]).unwrap();
        let m = MappedFrame::map(fd, 8).unwrap();
        assert_eq!(m.bytes(), &[1, 2, 3, 4, 5, 6, 7, 8]);
    }

    #[test]
    fn sealed_buffer_cannot_be_modified() {
        let fd = sealed_memfd("t", &[0; 16]).unwrap();
        assert!(rustix::fs::ftruncate(&fd, 4).is_err());
        assert!(rustix::io::pwrite(&fd, &[1], 0).is_err());
    }

    #[test]
    fn rejects_unsealed_truncated_and_foreign() {
        let fd = memfd_with("t", &[0; 16], false).unwrap();
        assert!(matches!(MappedFrame::map(fd, 16), Err(MapError::Unsealed { .. })));
        let fd = sealed_memfd("t", &[0; 16]).unwrap();
        assert_eq!(MappedFrame::map(fd, 17).unwrap_err(), MapError::Truncated { have: 16, need: 17 });
        let fd = sealed_memfd("t", &[0; 16]).unwrap();
        assert_eq!(MappedFrame::map(fd, 0).unwrap_err(), MapError::BadLength(0));
        let dev_null = OwnedFd::from(File::open("/dev/null").unwrap());
        assert_eq!(MappedFrame::map(dev_null, 16).unwrap_err(), MapError::NotSealable);
    }
}
