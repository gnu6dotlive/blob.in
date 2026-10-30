//! Unix SEQPACKET transport: one bounded control message per datagram, with
//! file descriptors carried as SCM_RIGHTS ancillary data on the same datagram.

use std::io::{self, IoSlice, IoSliceMut};
use std::mem::MaybeUninit;
use std::os::fd::{AsFd, BorrowedFd, OwnedFd};
use std::os::unix::fs::{DirBuilderExt, FileTypeExt, MetadataExt, PermissionsExt};
use std::path::{Path, PathBuf};
use std::time::Duration;

use rustix::io::Errno;
use rustix::net::{
    self, AddressFamily, RecvAncillaryBuffer, RecvAncillaryMessage, RecvFlags, ReturnFlags,
    SendAncillaryBuffer, SendAncillaryMessage, SendFlags, SocketAddrUnix, SocketFlags, SocketType,
};
use thiserror::Error;

use crate::proto::MAX_CONTROL_BYTES;

/// Descriptors accepted per datagram. FRAME_READY needs one; the slack lets the
/// receiver count (and reject) extras instead of seeing a truncated cmsg.
pub const MAX_FDS_PER_MESSAGE: usize = 2;

pub const SOCKET_DIR_NAME: &str = "blobin-showcase";
pub const SOCKET_FILE_NAME: &str = "render.sock";
/// The test server lives in its own directory so it can never be mistaken for the runtime.
pub const TEST_SOCKET_DIR_NAME: &str = "blobin-showcase-test";

#[derive(Debug, Error)]
pub enum TransportError {
    #[error("peer closed the connection")]
    Closed,
    #[error("control message exceeds {MAX_CONTROL_BYTES} bytes")]
    Oversize,
    #[error("empty control message")]
    Empty,
    #[error("ancillary data truncated (more than {MAX_FDS_PER_MESSAGE} descriptors)")]
    AncillaryTruncated,
    #[error("timed out waiting for the peer")]
    TimedOut,
    #[error("peer uid {peer} differs from ours ({ours})")]
    ForeignPeer { peer: u32, ours: u32 },
    #[error("insecure socket directory {path}: {why}")]
    InsecureDir { path: PathBuf, why: String },
    #[error("XDG_RUNTIME_DIR is not set")]
    NoRuntimeDir,
    #[error(transparent)]
    Io(#[from] io::Error),
}

impl From<Errno> for TransportError {
    fn from(e: Errno) -> Self {
        match e {
            Errno::AGAIN => TransportError::TimedOut,
            Errno::PIPE | Errno::CONNRESET => TransportError::Closed,
            e => TransportError::Io(e.into()),
        }
    }
}

pub struct Packet {
    pub bytes: Vec<u8>,
    pub fds: Vec<OwnedFd>,
}

/// A connected SOCK_SEQPACKET endpoint. `send` and `recv` take `&self` and may be
/// used from two threads at once (one reader, one writer).
#[derive(Debug)]
pub struct SeqPacket {
    fd: OwnedFd,
}

impl SeqPacket {
    pub fn connect(path: &Path) -> Result<Self, TransportError> {
        let fd = net::socket_with(AddressFamily::UNIX, SocketType::SEQPACKET, SocketFlags::CLOEXEC, None)?;
        net::connect(&fd, &SocketAddrUnix::new(path)?)?;
        Ok(Self { fd })
    }

    pub fn pair() -> Result<(Self, Self), TransportError> {
        let (a, b) = net::socketpair(AddressFamily::UNIX, SocketType::SEQPACKET, SocketFlags::CLOEXEC, None)?;
        Ok((Self { fd: a }, Self { fd: b }))
    }

    pub fn send(&self, bytes: &[u8], fds: &[BorrowedFd<'_>]) -> Result<(), TransportError> {
        if bytes.is_empty() {
            return Err(TransportError::Empty);
        }
        if bytes.len() > MAX_CONTROL_BYTES {
            return Err(TransportError::Oversize);
        }
        self.send_raw(bytes, fds)
    }

    /// Sends without the size checks. Only for fault injection in tests.
    #[doc(hidden)]
    pub fn send_raw(&self, bytes: &[u8], fds: &[BorrowedFd<'_>]) -> Result<(), TransportError> {
        if fds.len() > MAX_FDS_PER_MESSAGE {
            return Err(TransportError::AncillaryTruncated);
        }
        let mut space = [MaybeUninit::uninit(); rustix::cmsg_space!(ScmRights(MAX_FDS_PER_MESSAGE))];
        let mut control = SendAncillaryBuffer::new(&mut space);
        if !fds.is_empty() && !control.push(SendAncillaryMessage::ScmRights(fds)) {
            return Err(TransportError::AncillaryTruncated);
        }
        let iov = [IoSlice::new(bytes)];
        let sent = loop {
            match net::sendmsg(&self.fd, &iov, &mut control, SendFlags::NOSIGNAL) {
                Err(Errno::INTR) => continue,
                r => break r?,
            }
        };
        if sent != bytes.len() {
            return Err(io::Error::other(format!("short datagram: {sent}/{}", bytes.len())).into());
        }
        Ok(())
    }

    /// Receives one datagram. Received descriptors are owned (and closed on drop)
    /// even when the datagram is rejected.
    pub fn recv(&self) -> Result<Packet, TransportError> {
        let mut bytes = vec![0u8; MAX_CONTROL_BYTES];
        let mut space = [MaybeUninit::uninit(); rustix::cmsg_space!(ScmRights(MAX_FDS_PER_MESSAGE))];
        let mut control = RecvAncillaryBuffer::new(&mut space);
        let msg = loop {
            let mut iov = [IoSliceMut::new(&mut bytes)];
            match net::recvmsg(&self.fd, &mut iov, &mut control, RecvFlags::CMSG_CLOEXEC) {
                Err(Errno::INTR) => continue,
                r => break r?,
            }
        };
        let mut fds = Vec::new();
        for m in control.drain() {
            if let RecvAncillaryMessage::ScmRights(it) = m {
                fds.extend(it);
            }
        }
        if msg.flags.contains(ReturnFlags::CTRUNC) {
            return Err(TransportError::AncillaryTruncated);
        }
        if msg.flags.contains(ReturnFlags::TRUNC) {
            return Err(TransportError::Oversize);
        }
        if msg.bytes == 0 {
            // Orderly shutdown; we never send empty datagrams.
            return Err(TransportError::Closed);
        }
        bytes.truncate(msg.bytes);
        Ok(Packet { bytes, fds })
    }

    pub fn set_read_timeout(&self, timeout: Option<Duration>) -> Result<(), TransportError> {
        net::sockopt::set_socket_timeout(&self.fd, net::sockopt::Timeout::Recv, timeout)?;
        Ok(())
    }

    /// Unblocks a reader in `recv` (which then returns `Closed`).
    pub fn shutdown(&self) {
        let _ = net::shutdown(&self.fd, net::Shutdown::Both);
    }

    pub fn peer_uid(&self) -> Result<u32, TransportError> {
        Ok(net::sockopt::socket_peercred(&self.fd)?.uid.as_raw())
    }

    /// Rejects peers running as another user.
    pub fn require_same_uid(&self) -> Result<(), TransportError> {
        let peer = self.peer_uid()?;
        let ours = rustix::process::geteuid().as_raw();
        if peer != ours {
            return Err(TransportError::ForeignPeer { peer, ours });
        }
        Ok(())
    }
}

impl AsFd for SeqPacket {
    fn as_fd(&self) -> BorrowedFd<'_> {
        self.fd.as_fd()
    }
}

/// The runtime's socket, `$XDG_RUNTIME_DIR/blobin-showcase/render.sock`.
pub fn default_socket_path() -> Result<PathBuf, TransportError> {
    let base = std::env::var_os("XDG_RUNTIME_DIR").ok_or(TransportError::NoRuntimeDir)?;
    Ok(PathBuf::from(base).join(SOCKET_DIR_NAME).join(SOCKET_FILE_NAME))
}

/// The test server's socket, `$XDG_RUNTIME_DIR/blobin-showcase-test/render.sock`.
pub fn default_test_socket_path() -> Result<PathBuf, TransportError> {
    let base = std::env::var_os("XDG_RUNTIME_DIR").ok_or(TransportError::NoRuntimeDir)?;
    Ok(PathBuf::from(base).join(TEST_SOCKET_DIR_NAME).join(SOCKET_FILE_NAME))
}

/// Verifies `dir` is a real directory (not a symlink) owned by us with no group/other access.
/// With `create`, a missing directory is created 0700 first.
pub fn ensure_private_dir(dir: &Path, create: bool) -> Result<(), TransportError> {
    let insecure = |why: String| TransportError::InsecureDir { path: dir.to_owned(), why };
    let meta = match std::fs::symlink_metadata(dir) {
        Err(e) if e.kind() == io::ErrorKind::NotFound && create => {
            std::fs::DirBuilder::new().mode(0o700).create(dir)?;
            std::fs::symlink_metadata(dir)?
        }
        r => r?,
    };
    if !meta.file_type().is_dir() {
        return Err(insecure("not a directory (symlinks are refused)".into()));
    }
    let ours = rustix::process::geteuid().as_raw();
    if meta.uid() != ours {
        return Err(insecure(format!("owned by uid {}, expected {ours}", meta.uid())));
    }
    if meta.mode() & 0o077 != 0 {
        return Err(insecure(format!("mode {:o} grants group/other access", meta.mode() & 0o777)));
    }
    Ok(())
}

/// Listening socket. The socket file is removed on drop.
pub struct SeqListener {
    fd: OwnedFd,
    path: PathBuf,
}

impl SeqListener {
    /// Binds `path` inside a private directory (created if missing). A stale socket
    /// file left by a dead server is replaced; a live one is an error.
    pub fn bind(path: &Path) -> Result<Self, TransportError> {
        let dir = path.parent().ok_or_else(|| io::Error::other("socket path has no parent"))?;
        ensure_private_dir(dir, true)?;
        match std::fs::symlink_metadata(path) {
            Ok(m) if m.file_type().is_socket() && m.uid() == rustix::process::geteuid().as_raw() => {
                if SeqPacket::connect(path).is_ok() {
                    return Err(io::Error::new(io::ErrorKind::AddrInUse, "a server is already listening").into());
                }
                std::fs::remove_file(path)?;
            }
            Ok(_) => return Err(io::Error::new(io::ErrorKind::AlreadyExists, "path exists and is not our socket").into()),
            Err(e) if e.kind() == io::ErrorKind::NotFound => {}
            Err(e) => return Err(e.into()),
        }
        let fd = net::socket_with(AddressFamily::UNIX, SocketType::SEQPACKET, SocketFlags::CLOEXEC, None)?;
        net::bind(&fd, &SocketAddrUnix::new(path)?)?;
        std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600))?;
        net::listen(&fd, 4)?;
        Ok(Self { fd, path: path.to_owned() })
    }

    pub fn accept(&self) -> Result<SeqPacket, TransportError> {
        loop {
            match net::accept_with(&self.fd, SocketFlags::CLOEXEC) {
                Err(Errno::INTR) => continue,
                r => return Ok(SeqPacket { fd: r? }),
            }
        }
    }

    pub fn path(&self) -> &Path {
        &self.path
    }
}

impl Drop for SeqListener {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.path);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::fd::AsFd;

    #[test]
    fn datagram_boundaries_and_fds() {
        let (a, b) = SeqPacket::pair().unwrap();
        let memfd = rustix::fs::memfd_create("t", rustix::fs::MemfdFlags::CLOEXEC).unwrap();
        a.send(b"one", &[]).unwrap();
        a.send(b"two", &[memfd.as_fd()]).unwrap();
        let p = b.recv().unwrap();
        assert_eq!((p.bytes.as_slice(), p.fds.len()), (&b"one"[..], 0));
        let p = b.recv().unwrap();
        assert_eq!((p.bytes.as_slice(), p.fds.len()), (&b"two"[..], 1));
    }

    #[test]
    fn oversize_and_too_many_fds_are_rejected() {
        let (a, b) = SeqPacket::pair().unwrap();
        assert!(matches!(a.send(&vec![b'x'; MAX_CONTROL_BYTES + 1], &[]), Err(TransportError::Oversize)));
        a.send_raw(&vec![b'x'; MAX_CONTROL_BYTES + 1], &[]).unwrap();
        assert!(matches!(b.recv(), Err(TransportError::Oversize)));
        // The connection stays usable after a rejected datagram.
        a.send(b"after", &[]).unwrap();
        assert_eq!(b.recv().unwrap().bytes, b"after");
        let fds: Vec<OwnedFd> = (0..MAX_FDS_PER_MESSAGE + 1)
            .map(|_| rustix::fs::memfd_create("t", rustix::fs::MemfdFlags::CLOEXEC).unwrap())
            .collect();
        let borrowed: Vec<_> = fds.iter().map(|f| f.as_fd()).collect();
        assert!(matches!(a.send(b"x", &borrowed), Err(TransportError::AncillaryTruncated)));

        // A hostile sender bypassing our encoder: the receiver reports truncation
        // and the descriptors that did arrive are closed.
        let many: Vec<OwnedFd> =
            (0..8).map(|_| rustix::fs::memfd_create("t", rustix::fs::MemfdFlags::CLOEXEC).unwrap()).collect();
        let borrowed: Vec<_> = many.iter().map(|f| f.as_fd()).collect();
        let mut space = [MaybeUninit::uninit(); rustix::cmsg_space!(ScmRights(8))];
        let mut control = SendAncillaryBuffer::new(&mut space);
        assert!(control.push(SendAncillaryMessage::ScmRights(&borrowed)));
        net::sendmsg(&a, &[IoSlice::new(b"x")], &mut control, SendFlags::empty()).unwrap();
        assert!(matches!(b.recv(), Err(TransportError::AncillaryTruncated)));
    }

    #[test]
    fn close_and_shutdown_end_recv() {
        let (a, b) = SeqPacket::pair().unwrap();
        drop(a);
        assert!(matches!(b.recv(), Err(TransportError::Closed)));
        let (a, b) = SeqPacket::pair().unwrap();
        let t = std::thread::spawn(move || matches!(b.recv(), Err(TransportError::Closed)));
        std::thread::sleep(Duration::from_millis(20));
        let _keep = &a;
        a.shutdown();
        assert!(t.join().unwrap());
    }

    #[test]
    fn read_timeout() {
        let (_a, b) = SeqPacket::pair().unwrap();
        b.set_read_timeout(Some(Duration::from_millis(30))).unwrap();
        assert!(matches!(b.recv(), Err(TransportError::TimedOut)));
    }

    #[test]
    fn private_dir_checks() {
        let base = std::env::temp_dir().join(format!("blob-frame-dir-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&base);
        std::fs::create_dir(&base).unwrap();
        let d = base.join("d");
        assert!(ensure_private_dir(&d, false).is_err());
        ensure_private_dir(&d, true).unwrap();
        std::fs::set_permissions(&d, std::fs::Permissions::from_mode(0o755)).unwrap();
        assert!(matches!(ensure_private_dir(&d, false), Err(TransportError::InsecureDir { .. })));
        std::fs::set_permissions(&d, std::fs::Permissions::from_mode(0o700)).unwrap();
        let link = base.join("link");
        std::os::unix::fs::symlink(&d, &link).unwrap();
        assert!(matches!(ensure_private_dir(&link, false), Err(TransportError::InsecureDir { .. })));

        let sock = d.join("s.sock");
        let l = SeqListener::bind(&sock).unwrap();
        assert!(SeqListener::bind(&sock).is_err(), "live socket must not be replaced");
        let c = SeqPacket::connect(&sock).unwrap();
        let s = l.accept().unwrap();
        c.require_same_uid().unwrap();
        s.require_same_uid().unwrap();
        drop(l);
        assert!(!sock.exists());
        std::fs::remove_dir_all(&base).unwrap();
    }
}
