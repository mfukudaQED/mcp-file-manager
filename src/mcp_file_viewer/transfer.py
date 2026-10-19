"""Small, bounded binary transfers over the existing authenticated MCP connection.

This is a functional prototype, not a high-throughput transport. No HTTP listener,
shell command, shared temporary directory, or automatic overwrite is involved.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hashlib
from functools import wraps
import os
from pathlib import Path
import re
import secrets
import stat
import threading
import time

from .policy import (
    AccessDenied, FileChanged, FileLimitExceeded, FilePolicy, InvalidRange,
    ReadOnlyFileAccess,
)

MAX_TRANSFER_BYTES = 64 * 1024
CHUNK_BYTES = 4096
SESSION_IDLE_SECONDS = 600
_STAGE_PREFIX = ".mcpfm-upload-"
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_WRITE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
_READ_WRITE_FLAGS = os.O_RDWR | os.O_NOFOLLOW


def _serialized(method):
    """Hold the per-service lock throughout an upload state transition."""
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        """Call one upload method atomically against concurrent MCP calls."""
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


@dataclass
class _Upload:
    """A single in-process upload, pinned to its original directory inode."""

    token: str
    directory: str
    filename: str
    stage: str
    parent_fd: int
    parent_identity: tuple[int, int]
    stage_identity: tuple[int, int]
    size: int
    sha256: str
    received: int
    last_activity: float


class BinaryTransfer:
    """Provide revision-pinned small downloads and opt-in create-only uploads."""

    def __init__(self, policy: FilePolicy, upload_roots: tuple[Path, ...] = ()):
        """Reapply authorized root restrictions to every file operation."""
        self.access = ReadOnlyFileAccess(policy)
        self.max_transfer_bytes = min(MAX_TRANSFER_BYTES, policy.max_file_bytes)
        self.upload_roots = tuple(Path(p).expanduser().resolve(strict=True) for p in upload_roots)
        for root in self.upload_roots:
            if not root.is_dir() or not any(
                root == allowed or root.is_relative_to(allowed) for allowed in policy.roots
            ):
                raise ValueError("Upload root must be a subdirectory of an approved root")
        self._session: _Upload | None = None
        self._lock = threading.RLock()

    @staticmethod
    def _identity(info: os.stat_result) -> tuple[int, int]:
        """Identify a directory or staging file without following symlinks."""
        return info.st_dev, info.st_ino

    @staticmethod
    def _signature(info: os.stat_result) -> tuple[int, ...]:
        """Detect concurrent changes during bounded reads."""
        return (
            info.st_dev, info.st_ino, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns,
        )

    def _snapshot(self, path: str) -> tuple[str, bytes]:
        """Read at most 64 KiB from an authorized regular file and hash it."""
        fd, _ = self.access._open(path)
        try:
            before = os.fstat(fd)
            if before.st_size > self.max_transfer_bytes:
                raise FileLimitExceeded("Source exceeds the configured transfer limit")
            payload = os.pread(fd, self.max_transfer_bytes + 1, 0)
            after = os.fstat(fd)
            if (self._signature(before) != self._signature(after)
                    or len(payload) != after.st_size):
                raise FileChanged("Source changed during download")
        finally:
            os.close(fd)
        return "sha256:" + hashlib.sha256(payload).hexdigest(), payload

    def download_info(self, path: str) -> dict:
        """Return metadata for a stable binary-safe small source snapshot."""
        revision, payload = self._snapshot(path)
        return {
            "path": path, "size_bytes": len(payload), "revision": revision,
            "chunk_bytes": CHUNK_BYTES, "has_more": bool(payload),
        }

    def download_chunk(self, path: str, offset: int, revision: str) -> dict:
        """Return one Base64 chunk only when the original revision still matches."""
        if type(offset) is not int or offset < 0:
            raise InvalidRange("Offset must be a nonnegative integer")
        if not isinstance(revision, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", revision):
            raise InvalidRange("Invalid download revision")
        current, payload = self._snapshot(path)
        if current != revision:
            raise FileChanged("Source file changed; restart the transfer")
        if offset > len(payload):
            raise InvalidRange("Offset exceeds file size")
        chunk = payload[offset:offset + CHUNK_BYTES]
        return {
            "offset": offset, "next_offset": offset + len(chunk),
            "size_bytes": len(payload), "revision": revision,
            "content_base64": base64.b64encode(chunk).decode("ascii"),
            "has_more": offset + len(chunk) < len(payload),
        }

    def _discard(self) -> None:
        """Best-effort remove a staging file and close its directory handle."""
        session = self._session
        self._session = None
        if session is None:
            return
        try:
            os.unlink(session.stage, dir_fd=session.parent_fd)
        except FileNotFoundError:
            pass
        finally:
            os.close(session.parent_fd)

    def _expire(self) -> None:
        """Reclaim an idle session on the next transfer operation."""
        if (self._session is not None and
                time.monotonic() - self._session.last_activity > SESSION_IDLE_SECONDS):
            self._discard()

    def _current(self, session_id: str) -> _Upload:
        """Validate the opaque session ID and its pinned authorized directory."""
        self._expire()
        s = self._session
        if s is None or not isinstance(session_id, str) or not secrets.compare_digest(s.token, session_id):
            raise AccessDenied("Unknown or expired upload session")
        current_fd, _ = self.access._open(s.directory, directory=True)
        try:
            if self._identity(os.fstat(current_fd)) != s.parent_identity:
                raise FileChanged("Upload directory was replaced")
        finally:
            os.close(current_fd)
        s.last_activity = time.monotonic()
        return s

    @staticmethod
    def _filename(name: str) -> None:
        """Reject paths, hidden names, and forbidden credential-like names."""
        if (not isinstance(name, str) or len(name) > 200
                or not name or name in (".", "..") or name.startswith(".")
                or any(c in name for c in ("/", "\\", "\x00", "\r", "\n"))
                or ReadOnlyFileAccess._blocked((name,))):
            raise AccessDenied("Unsafe upload filename")

    @_serialized
    def upload_start(self, directory: str, filename: str, size_bytes: int, sha256: str) -> dict:
        """Prepare one create-only transfer inside an explicitly allowed upload root."""
        self._expire()
        if not self.upload_roots:
            raise AccessDenied("File uploads are disabled")
        if self._session is not None:
            raise FileLimitExceeded("Another upload is in progress")
        self._filename(filename)
        if type(size_bytes) is not int or not 0 <= size_bytes <= self.max_transfer_bytes:
            raise FileLimitExceeded("Upload size exceeds the configured transfer limit")
        if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
            raise InvalidRange("Expected SHA-256 must contain 64 lowercase hex digits")

        fd, actual = self.access._open(directory, directory=True)
        try:
            if not any(actual == root or actual.is_relative_to(root)
                       for root in self.upload_roots):
                raise AccessDenied("Destination is outside explicit upload roots")
            metadata = os.fstat(fd)
            if metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022:
                raise AccessDenied("Upload destination must be user-owned and not group/world-writable")
            try:
                os.stat(filename, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise FileChanged("Destination filename already exists")
            token = secrets.token_hex(16)
            stage = _STAGE_PREFIX + token + ".part"
            stage_fd = os.open(stage, _WRITE_FLAGS, 0o600, dir_fd=fd)
            try:
                stage_identity = self._identity(os.fstat(stage_fd))
            finally:
                os.close(stage_fd)
            self._session = _Upload(
                token, str(actual), filename, stage, fd, self._identity(metadata),
                stage_identity, size_bytes, sha256, 0, time.monotonic(),
            )
            return {"session_id": token, "received_bytes": 0, "size_bytes": size_bytes,
                    "chunk_bytes": CHUNK_BYTES}
        except Exception:
            os.close(fd)
            raise

    @_serialized
    def upload_chunk(self, session_id: str, offset: int, content_base64: str) -> dict:
        """Write one bounded chunk, accepting only identical replayed data."""
        s = self._current(session_id)
        if type(offset) is not int or offset < 0:
            raise InvalidRange("Invalid upload offset")
        if not isinstance(content_base64, str) or len(content_base64) > 5500:
            raise FileLimitExceeded("Upload chunk exceeds transfer limit")
        try:
            payload = base64.b64decode(content_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise InvalidRange("Invalid Base64 upload chunk") from exc
        if not payload or len(payload) > CHUNK_BYTES or offset + len(payload) > s.size:
            raise FileLimitExceeded("Upload chunk is empty or exceeds declared size")
        file_fd = os.open(s.stage, _READ_WRITE_FLAGS, dir_fd=s.parent_fd)
        try:
            st = os.fstat(file_fd)
            if (self._identity(st) != s.stage_identity or st.st_nlink != 1 or
                    not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()):
                raise FileChanged("Upload staging file was replaced")
            if offset < s.received:
                if offset + len(payload) > s.received or os.pread(file_fd, len(payload), offset) != payload:
                    raise FileChanged("Conflicting upload replay")
                return {"session_id": s.token, "received_bytes": s.received, "replayed": True}
            if offset != s.received or st.st_size != s.received:
                raise InvalidRange("Upload chunks must be sequential")
            written = os.pwrite(file_fd, payload, offset)
            if written != len(payload):
                raise OSError("Short upload write")
            s.received += written
            return {"session_id": s.token, "received_bytes": s.received, "replayed": False}
        finally:
            os.close(file_fd)

    @_serialized
    def upload_finish(self, session_id: str) -> dict:
        """Verify size and SHA-256 before atomically creating the destination."""
        s = self._current(session_id)
        if s.received != s.size:
            raise FileChanged("Upload is incomplete")
        file_fd = os.open(s.stage, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=s.parent_fd)
        try:
            before = os.fstat(file_fd)
            if self._identity(before) != s.stage_identity or before.st_nlink != 1:
                raise FileChanged("Upload staging file changed")
            if before.st_size != s.size:
                raise FileChanged("Upload staging size differs")
            payload = os.pread(file_fd, self.max_transfer_bytes + 1, 0)
            after = os.fstat(file_fd)
            if self._signature(before) != self._signature(after):
                raise FileChanged("Upload staging file changed during verification")
            if hashlib.sha256(payload).hexdigest() != s.sha256:
                raise FileChanged("Upload checksum mismatch")
            os.fsync(file_fd)
        finally:
            os.close(file_fd)
        try:
            os.link(s.stage, s.filename, src_dir_fd=s.parent_fd,
                    dst_dir_fd=s.parent_fd, follow_symlinks=False)
        except FileExistsError as exc:
            raise FileChanged("Destination appeared before commit; no overwrite") from exc
        result = {"path": str(Path(s.directory) / s.filename),
                  "size_bytes": s.size, "revision": "sha256:" + s.sha256}
        self._discard()
        return result

    @_serialized
    def upload_cancel(self, session_id: str) -> dict:
        """Cancel the caller's live upload and remove its temporary file."""
        self._current(session_id)
        self._discard()
        return {"cancelled": True}
