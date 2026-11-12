"""Regression tests for secure read-only raster-image previews."""

import base64
import json
import os
from pathlib import Path

import pytest

from mcp_file_viewer.image_preview import (
    IMAGE_CHUNK_BYTES, ImagePreview, UnsupportedImage,
)
from mcp_file_viewer.policy import (
    AccessDenied, FileChanged, FileLimitExceeded, FilePolicy, InvalidRange,
)
from mcp_file_viewer.extension import register_file_viewer, UI_URI, V26_UI_URI

# One-pixel PNG; image payloads are kept binary and never treated as UTF-8 text.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9YwLcy0AAAAASUVORK5CYII="
)


def test_read_only_image_info_and_chunk(tmp_path: Path):
    """Check format sniffing and exact base64 reconstruction."""
    path = tmp_path / "tiny.PNG"
    path.write_bytes(PNG)
    preview = ImagePreview(FilePolicy(roots=(tmp_path,)))
    info = preview.info(str(path))
    assert info["mime_type"] == "image/png"
    assert (info["width"], info["height"]) == (1, 1)
    assert info["size_bytes"] == len(PNG)
    assert info["chunk_bytes"] == IMAGE_CHUNK_BYTES
    assert info["revision"].startswith("imgstat:")
    chunk = preview.chunk(str(path), 0, info["revision"])
    assert chunk["has_more"] is False
    assert base64.b64decode(chunk["content_base64"]) == PNG
    assert chunk["next_offset"] == len(PNG)


def test_multi_chunk_and_strict_offsets(tmp_path: Path):
    """Read the image in revision-pinned chunks without full-file rehashing."""
    path = tmp_path / "large.png"
    content = PNG + b"x" * (IMAGE_CHUNK_BYTES * 2)
    path.write_bytes(content)
    preview = ImagePreview(FilePolicy(roots=(tmp_path,)))
    info = preview.info(str(path))
    offsets = [0, IMAGE_CHUNK_BYTES, 2 * IMAGE_CHUNK_BYTES]
    result = b"".join(
        base64.b64decode(preview.chunk(str(path), offset, info["revision"])["content_base64"])
        for offset in offsets
    )
    assert result == content
    with pytest.raises(InvalidRange):
        preview.chunk(str(path), 1, info["revision"])
    with pytest.raises(InvalidRange):
        preview.chunk(str(path), -1, info["revision"])
    with pytest.raises(InvalidRange):
        preview.chunk(str(path), True, info["revision"])


def test_changed_image_rejected(tmp_path: Path):
    """Invalidate a stale image revision before returning any new chunk."""
    path = tmp_path / "image.png"
    path.write_bytes(PNG)
    preview = ImagePreview(FilePolicy(roots=(tmp_path,)))
    old = preview.info(str(path))["revision"]
    path.write_bytes(PNG + b"updated")
    with pytest.raises(FileChanged):
        preview.chunk(str(path), 0, old)


def test_unsupported_and_private_paths(tmp_path: Path):
    """Reject disguised binaries, unsupported SVG, symlinks and private roots."""
    preview = ImagePreview(FilePolicy(roots=(tmp_path,)))
    fake = tmp_path / "fake.png"
    fake.write_bytes(b"<html>unexpected payload</html>")
    with pytest.raises(UnsupportedImage):
        preview.info(str(fake))
    svg = tmp_path / "vector.svg"
    svg.write_text("<svg/>", encoding="utf8")
    with pytest.raises(UnsupportedImage):
        preview.info(str(svg))
    private_dir = tmp_path / ".ssh"
    private_dir.mkdir()
    private = private_dir / "a.png"
    private.write_bytes(PNG)
    with pytest.raises(AccessDenied):
        preview.info(str(private))
    link = tmp_path / "link.png"
    link.symlink_to(private)
    with pytest.raises(AccessDenied):
        preview.info(str(link))


def test_decompression_bomb_guard_and_file_size_limit(tmp_path: Path):
    """Refuse impossible PNG dimensions and images exceeding the configured cap."""
    preview = ImagePreview(FilePolicy(roots=(tmp_path,), max_file_bytes=1024))
    huge_dimensions = (PNG[:16] + (65535).to_bytes(4, "big") +
                       (65535).to_bytes(4, "big") + PNG[24:])
    large_header = tmp_path / "dimensions.png"
    large_header.write_bytes(huge_dimensions)
    with pytest.raises(FileLimitExceeded):
        preview.info(str(large_header))
    oversize = tmp_path / "oversize.png"
    oversize.write_bytes(PNG + b"a" * 1024)
    with pytest.raises(FileLimitExceeded):
        preview.info(str(oversize))


class Stub:
    """Capture FastMCP registration without starting an HPC service."""

    def __init__(self):
        """Initialize tool and resource maps."""
        self.tools = {}
        self.tool_meta = {}
        self.resources = {}

    def resource(self, uri, **kwargs):
        """Register one UI resource."""
        def wrap(fn):
            """Retain the decorated handler."""
            self.resources[uri] = fn
            return fn
        return wrap

    def tool(self, name, **kwargs):
        """Register one MCP tool with its metadata."""
        def wrap(fn):
            """Retain tool callable."""
            self.tools[name] = fn
            self.tool_meta[name] = kwargs.get("meta", {})
            return fn
        return wrap


def test_image_tools_and_legacy_v26(tmp_path: Path):
    """Register image APIs as app-only and preserve previous v26 resources."""
    path = tmp_path / "image.png"
    path.write_bytes(PNG)
    mcp = Stub()
    register_file_viewer(mcp, roots=(tmp_path,))
    assert UI_URI == "ui://mcp-file-manager/v29/app.html"
    assert V26_UI_URI == "ui://mcp-file-manager/v26/app.html"
    assert "UI v26" in mcp.resources[V26_UI_URI]()
    assert "UI v29" in mcp.resources[UI_URI]()
    for name in ("file_manager_image_info", "file_manager_image_chunk"):
        assert mcp.tool_meta[name]["ui"]["visibility"] == ["app"]
    info = json.loads(mcp.tools["file_manager_image_info"](str(path)))
    assert info["mime_type"] == "image/png"
    chunk = json.loads(mcp.tools["file_manager_image_chunk"](str(path), 0, info["revision"]))
    assert base64.b64decode(chunk["content_base64"]) == PNG
    opened = json.loads(mcp.tools["file_viewer_open"](str(path)))
    assert opened["kind"] == "image"
    assert opened["ui_available"] is True
    large = tmp_path / "large.png"
    large.write_bytes(PNG + b"x" * IMAGE_CHUNK_BYTES)
    manifest = json.loads(mcp.tools["file_manager_image_info"](str(large)))
    block = json.loads(mcp.tools["file_manager_image_chunk"](str(large), 0, manifest["revision"]))
    assert len(base64.b64decode(block["content_base64"])) == IMAGE_CHUNK_BYTES
    assert block["has_more"] is True
