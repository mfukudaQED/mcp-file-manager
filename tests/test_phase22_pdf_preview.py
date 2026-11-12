"""Regression coverage for bounded PDF previews and preserved MCP resources."""

import base64
import json
from pathlib import Path

import pytest

from mcp_file_viewer.extension import (
    UI_URI, V28_UI_URI, V27_UI_URI, V26_UI_URI, register_file_viewer,
)
from mcp_file_viewer.pdf_preview import PDFPreview, PDF_CHUNK_BYTES, UnsupportedPDF
from mcp_file_viewer.policy import (
    AccessDenied, FileChanged, FileLimitExceeded, FilePolicy, InvalidRange,
)

HEADER = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


def test_pdf_header_and_chunk_roundtrip(tmp_path: Path):
    """Read metadata and reconstruct PDF bytes from an allowed file."""
    pdf = tmp_path / "sample.PDF"
    pdf.write_bytes(HEADER)
    reader = PDFPreview(FilePolicy(roots=(tmp_path,)))
    info = reader.info(str(pdf))
    assert info["mime_type"] == "application/pdf"
    assert info["revision"].startswith("pdfstat:")
    assert info["size_bytes"] == len(HEADER)
    assert info["chunk_bytes"] == PDF_CHUNK_BYTES
    part = reader.chunk(str(pdf), 0, info["revision"])
    assert base64.b64decode(part["content_base64"]) == HEADER
    assert part["has_more"] is False


def test_multi_chunk_pdf_and_alignment(tmp_path: Path):
    """Enforce bounded per-request reads and valid offsets."""
    pdf = tmp_path / "long.pdf"
    payload = HEADER + b"x" * (PDF_CHUNK_BYTES * 2)
    pdf.write_bytes(payload)
    reader = PDFPreview(FilePolicy(roots=(tmp_path,)))
    info = reader.info(str(pdf))
    assert b"".join(
        base64.b64decode(reader.chunk(str(pdf), off, info["revision"])["content_base64"])
        for off in (0, PDF_CHUNK_BYTES, 2 * PDF_CHUNK_BYTES)
    ) == payload
    for bad in (-1, True, 1, len(payload) + 1):
        with pytest.raises(InvalidRange):
            reader.chunk(str(pdf), bad, info["revision"])


def test_pdf_change_is_detected(tmp_path: Path):
    """Reject a change between a manifest and a binary chunk."""
    pdf = tmp_path / "changed.pdf"
    pdf.write_bytes(HEADER)
    reader = PDFPreview(FilePolicy(roots=(tmp_path,)))
    original = reader.info(str(pdf))["revision"]
    pdf.write_bytes(HEADER + b"changed")
    with pytest.raises(FileChanged):
        reader.chunk(str(pdf), 0, original)


def test_pdf_rejections(tmp_path: Path):
    """Reject forged extensions, unsafe paths, and oversized documents."""
    reader = PDFPreview(FilePolicy(roots=(tmp_path,), max_file_bytes=1024))
    invalid = tmp_path / "fake.pdf"
    invalid.write_bytes(b"<html>not a pdf</html>")
    with pytest.raises(UnsupportedPDF):
        reader.info(str(invalid))
    invalid_ext = tmp_path / "fake.txt"
    invalid_ext.write_bytes(HEADER)
    with pytest.raises(UnsupportedPDF):
        reader.info(str(invalid_ext))
    oversize = tmp_path / "large.pdf"
    oversize.write_bytes(HEADER + b"x" * 1024)
    with pytest.raises(FileLimitExceeded):
        reader.info(str(oversize))
    hidden = tmp_path / ".ssh"
    hidden.mkdir()
    secret = hidden / "secret.pdf"
    secret.write_bytes(HEADER)
    with pytest.raises(AccessDenied):
        reader.info(str(secret))
    link = tmp_path / "link.pdf"
    link.symlink_to(secret)
    with pytest.raises(AccessDenied):
        reader.info(str(link))


class Stub:
    """Capture MCP tool and resource registration in memory."""

    def __init__(self):
        """Initialize captured resources and metadata."""
        self.tools = {}
        self.meta = {}
        self.resources = {}

    def tool(self, name, **kwargs):
        """Record a decorated MCP tool."""
        def wrap(fn):
            """Save the callable and metadata."""
            self.tools[name] = fn
            self.meta[name] = kwargs.get("meta", {})
            return fn
        return wrap

    def resource(self, uri, **kwargs):
        """Record a decorated UI resource."""
        def wrap(fn):
            """Save a resource provider."""
            self.resources[uri] = fn
            return fn
        return wrap


def test_pdf_mcp_and_v27_compatibility(tmp_path: Path):
    """Expose only read-only PDF tools and retain immutable UI v27."""
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(HEADER)
    mcp = Stub()
    register_file_viewer(mcp, roots=(tmp_path,))
    assert UI_URI == "ui://mcp-file-manager/v29/app.html"
    assert V28_UI_URI == "ui://mcp-file-manager/v28/app.html"
    assert V27_UI_URI == "ui://mcp-file-manager/v27/app.html"
    assert V26_UI_URI == "ui://mcp-file-manager/v26/app.html"
    assert "UI v29" in mcp.resources[UI_URI]()
    assert "UI v28" in mcp.resources[V28_UI_URI]()
    assert "UI v27" in mcp.resources[V27_UI_URI]()
    for name in ("file_manager_pdf_info", "file_manager_pdf_chunk"):
        assert mcp.meta[name]["ui"]["visibility"] == ["app"]
    info = json.loads(mcp.tools["file_manager_pdf_info"](str(pdf)))
    assert info["mime_type"] == "application/pdf"
    chunk = json.loads(mcp.tools["file_manager_pdf_chunk"](str(pdf), 0, info["revision"]))
    assert base64.b64decode(chunk["content_base64"]) == HEADER
    assert json.loads(mcp.tools["file_viewer_open"](str(pdf)))["kind"] == "pdf"
