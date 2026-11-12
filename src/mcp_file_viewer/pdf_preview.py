"""Bounded, read-only PDF transport for authorized MCP File Manager paths."""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from .policy import (
    FileChanged, FileLimitExceeded, FilePolicy, FileViewerError, InvalidRange,
    ReadOnlyFileAccess,
)

PDF_CHUNK_BYTES = 24 * 1024
MAX_PDF_BYTES = 8 * 1024 * 1024


class UnsupportedPDF(FileViewerError):
    """Reject files that are not ordinary PDF documents."""

    code = "unsupported_pdf"


def is_pdf_path(path: str) -> bool:
    """Recognize a PDF path by suffix, before checking its binary signature."""
    return Path(path).suffix.lower() == ".pdf"


def _signature(info: os.stat_result) -> tuple[int, int, int, int, int]:
    """Capture a file identity and change-detection metadata."""
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


class PDFPreview:
    """Serve PDF bytes through revision-pinned, read-only MCP chunks."""

    def __init__(self, policy: FilePolicy) -> None:
        """Reuse the existing root and file-size restrictions."""
        self.access = ReadOnlyFileAccess(policy)
        self.max_bytes = min(MAX_PDF_BYTES, policy.max_file_bytes)

    def _open_info(self, path: str) -> tuple[int, dict, tuple[int, int, int, int, int]]:
        """Verify PDF magic bytes using the existing no-follow file traversal."""
        if not is_pdf_path(path):
            raise UnsupportedPDF("Only PDF files can be previewed")
        fd, actual = self.access._open(path)
        try:
            before = os.fstat(fd)
            if before.st_size > self.max_bytes:
                raise FileLimitExceeded("PDF exceeds the configured preview size limit")
            if before.st_size < 16 or os.pread(fd, 5, 0) != b"%PDF-":
                raise UnsupportedPDF("Invalid or incomplete PDF header")
            after = os.fstat(fd)
            if _signature(before) != _signature(after):
                raise FileChanged("PDF changed while being inspected")
            metadata_signature = ":".join(str(x) for x in _signature(after)).encode("ascii")
            return (
                fd,
                {
                    "path": str(actual),
                    "mime_type": "application/pdf",
                    "size_bytes": after.st_size,
                    "revision": "pdfstat:" + hashlib.sha256(metadata_signature).hexdigest(),
                    "chunk_bytes": PDF_CHUNK_BYTES,
                },
                _signature(after),
            )
        except Exception:
            os.close(fd)
            raise

    def info(self, path: str) -> dict:
        """Return size and revision before any binary transfer."""
        fd, info, _ = self._open_info(path)
        os.close(fd)
        return info

    def chunk(self, path: str, offset: int, revision: str) -> dict:
        """Return one Base64 chunk only when the original PDF is unchanged."""
        if type(offset) is not int or offset < 0:
            raise InvalidRange("PDF offset must be a nonnegative integer")
        if (
            not isinstance(revision, str)
            or len(revision) != 72
            or not revision.startswith("pdfstat:")
            or any(c not in "0123456789abcdef" for c in revision[8:])
        ):
            raise InvalidRange("Invalid PDF revision")
        fd, info, signature = self._open_info(path)
        try:
            if revision != info["revision"]:
                raise FileChanged("PDF changed since the requested revision")
            size = info["size_bytes"]
            if offset > size or (offset < size and offset % PDF_CHUNK_BYTES):
                raise InvalidRange("PDF offset must align to a chunk boundary")
            count = min(PDF_CHUNK_BYTES, size - offset)
            payload = os.pread(fd, count, offset)
            if _signature(os.fstat(fd)) != signature or len(payload) != count:
                raise FileChanged("PDF changed during the requested read")
            next_offset = offset + len(payload)
            return {
                "revision": revision,
                "offset": offset,
                "next_offset": next_offset,
                "size_bytes": size,
                "content_base64": base64.b64encode(payload).decode("ascii"),
                "has_more": next_offset < size,
            }
        finally:
            os.close(fd)
