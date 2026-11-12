"""Bounded, read-only raster-image preview over authorized MCP file roots."""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
import struct

from .policy import (
    FileChanged, FileLimitExceeded, FilePolicy, FileViewerError, InvalidRange,
    ReadOnlyFileAccess,
)

IMAGE_CHUNK_BYTES = 24 * 1024
MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_IMAGE_PIXELS = 80_000_000
MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


class UnsupportedImage(FileViewerError):
    """Reject files that do not match a supported safe raster-image signature."""

    code = "unsupported_image"


def is_image_path(path: str) -> bool:
    """Recognize supported raster formats without treating SVG as safe."""
    return Path(path).suffix.lower() in MIME_TYPES


def _check_format(path: str, data: bytes) -> tuple[str, int | None, int | None]:
    """Match an extension to a magic signature and inspect inexpensive dimensions."""
    mime = MIME_TYPES.get(Path(path).suffix.lower())
    if mime is None:
        raise UnsupportedImage("Only PNG, JPEG, GIF, and WebP can be previewed")
    width = height = None
    if mime == "image/png":
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise UnsupportedImage("Invalid PNG signature or header")
        width, height = struct.unpack(">II", data[16:24])
    elif mime == "image/jpeg":
        if not data.startswith(b"\xff\xd8\xff"):
            raise UnsupportedImage("Invalid JPEG signature")
    elif mime == "image/gif":
        if len(data) < 10 or data[:6] not in (b"GIF87a", b"GIF89a"):
            raise UnsupportedImage("Invalid GIF signature")
        width, height = struct.unpack("<HH", data[6:10])
    elif mime == "image/webp":
        if len(data) < 16 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
            raise UnsupportedImage("Invalid WebP signature")
    if width is not None and height is not None:
        if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
            raise FileLimitExceeded("Image dimensions exceed the preview limit")
    return mime, width, height


def _signature(st: os.stat_result) -> tuple[int, int, int, int, int]:
    """Pin preview chunks to the same inode, size, and modification metadata."""
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns


class ImagePreview:
    """Serve allowlisted image bytes without a network listener or write access."""

    def __init__(self, policy: FilePolicy) -> None:
        """Apply existing safe no-follow traversal and file-size policy."""
        self.access = ReadOnlyFileAccess(policy)
        self.max_bytes = min(policy.max_file_bytes, MAX_IMAGE_BYTES)

    def _open_info(self, path: str) -> tuple[int, dict, tuple[int, int, int, int, int]]:
        """Open the image securely and return metadata pinned to one file revision."""
        if not is_image_path(path):
            raise UnsupportedImage("Only PNG, JPEG, GIF, and WebP can be previewed")
        fd, actual = self.access._open(path)
        try:
            before = os.fstat(fd)
            if before.st_size > self.max_bytes:
                raise FileLimitExceeded("Image exceeds the configured preview size limit")
            if before.st_size < 12:
                raise UnsupportedImage("Image is incomplete")
            prefix = os.pread(fd, 64, 0)
            mime, width, height = _check_format(str(actual), prefix)
            after = os.fstat(fd)
            if _signature(before) != _signature(after):
                raise FileChanged("Image changed while being inspected")
            raw = ":".join(str(n) for n in _signature(after)).encode("ascii")
            revision = "imgstat:" + hashlib.sha256(raw).hexdigest()
            metadata = {
                "path": str(actual), "revision": revision,
                "size_bytes": after.st_size,
                "mime_type": mime, "chunk_bytes": IMAGE_CHUNK_BYTES,
                "width": width, "height": height,
            }
            return fd, metadata, _signature(after)
        except Exception:
            os.close(fd)
            raise

    def info(self, path: str) -> dict:
        """Advertise the allowed image type, size, and revision without image content."""
        fd, metadata, _ = self._open_info(path)
        os.close(fd)
        return metadata

    def chunk(self, path: str, offset: int, revision: str) -> dict:
        """Read one Base64 block and reject invalid revisions and changed files."""
        if type(offset) is not int or offset < 0:
            raise InvalidRange("Image offset must be a nonnegative integer")
        if not isinstance(revision, str) or len(revision) != 72 or not revision.startswith("imgstat:"):
            raise InvalidRange("Invalid image revision")
        fd, metadata, original = self._open_info(path)
        try:
            if revision != metadata["revision"]:
                raise FileChanged("Image changed since metadata was requested")
            size = metadata["size_bytes"]
            if offset > size or (offset < size and offset % IMAGE_CHUNK_BYTES):
                raise InvalidRange("Image offset must align to a chunk boundary")
            content = os.pread(fd, min(IMAGE_CHUNK_BYTES, size - offset), offset)
            if _signature(os.fstat(fd)) != original or len(content) != min(IMAGE_CHUNK_BYTES, size - offset):
                raise FileChanged("Image changed while reading")
            next_offset = offset + len(content)
            return {
                "revision": revision, "offset": offset, "next_offset": next_offset,
                "size_bytes": size, "content_base64": base64.b64encode(content).decode("ascii"),
                "has_more": next_offset < size,
            }
        finally:
            os.close(fd)
