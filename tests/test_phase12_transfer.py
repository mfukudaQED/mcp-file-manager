"""Regression tests for small binary transfers over existing MCP tools."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

from mcp_file_viewer.extension import register_file_viewer
from mcp_file_viewer.policy import (
    AccessDenied, FileChanged, FileLimitExceeded, FilePolicy, InvalidRange,
)
from mcp_file_viewer.transfer import BinaryTransfer, CHUNK_BYTES, MAX_TRANSFER_BYTES


class MCPStub:
    """Collect MCP tools using the same decorators as FastMCP."""

    def __init__(self) -> None:
        """Initialize a separate in-memory tool registry."""
        self.tools: dict = {}
        self.tool_meta: dict = {}

    def resource(self, uri, **kwargs):
        """Ignore UI resource registration while testing tools."""
        def register(func):
            """Accept one resource function."""
            return func
        return register

    def tool(self, name, **kwargs):
        """Capture registered tool callbacks for direct execution."""
        def register(func):
            """Save a callback by MCP tool name."""
            self.tools[name] = func
            self.tool_meta[name] = kwargs.get("meta", {})
            return func
        return register


@pytest.fixture
def workspace(tmp_path: Path):
    """Return a private approved root and an independent transfer service."""
    root = tmp_path / "approved"
    root.mkdir(mode=0o700)
    service = BinaryTransfer(FilePolicy((root,)), (root,))
    return root, service


def test_download_binary_roundtrip_and_revision(workspace):
    """Download byte-for-byte binary data, including invalid UTF-8 and NUL."""
    root, service = workspace
    payload = bytes(range(256)) * 20
    file = root / "result.cube"
    file.write_bytes(payload)
    info = service.download_info(str(file))
    assert info["size_bytes"] == len(payload)
    received = bytearray()
    offset = 0
    while True:
        chunk = service.download_chunk(str(file), offset, info["revision"])
        received.extend(base64.b64decode(chunk["content_base64"]))
        offset = chunk["next_offset"]
        if not chunk["has_more"]:
            break
    assert bytes(received) == payload
    file.write_bytes(b"changed")
    with pytest.raises(FileChanged):
        service.download_chunk(str(file), 0, info["revision"])


def test_download_boundaries_and_private_paths(workspace, tmp_path):
    """Reject oversized data, symlinks, credentials and paths outside roots."""
    root, service = workspace
    oversized = root / "huge.bin"
    oversized.write_bytes(b"x" * (MAX_TRANSFER_BYTES + 1))
    with pytest.raises(FileLimitExceeded):
        service.download_info(str(oversized))
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside")
    (root / "linked").symlink_to(outside)
    with pytest.raises(AccessDenied):
        service.download_info(str(root / "linked"))
    with pytest.raises(AccessDenied):
        service.download_info(str(outside))
    (root / "token.pem").write_text("no")
    with pytest.raises(AccessDenied):
        service.download_info(str(root / "token.pem"))


def test_create_only_upload_and_chunk_replay(workspace):
    """Commit an exact binary upload, never overwriting existing files."""
    root, service = workspace
    payload = bytes(range(256)) * 19
    digest = hashlib.sha256(payload).hexdigest()
    started = service.upload_start(str(root), "sample.bin", len(payload), digest)
    token = started["session_id"]
    first = payload[:CHUNK_BYTES]
    encoded = base64.b64encode(first).decode("ascii")
    assert service.upload_chunk(token, 0, encoded)["received_bytes"] == CHUNK_BYTES
    assert service.upload_chunk(token, 0, encoded)["replayed"] is True
    with pytest.raises(FileChanged):
        service.upload_chunk(token, 0, base64.b64encode(b"different").decode())
    rest = payload[CHUNK_BYTES:]
    service.upload_chunk(token, CHUNK_BYTES, base64.b64encode(rest).decode("ascii"))
    final = service.upload_finish(token)
    file = root / "sample.bin"
    assert file.read_bytes() == payload
    assert final["revision"] == "sha256:" + digest
    assert not list(root.glob(".mcpfm-upload-*"))
    with pytest.raises(FileChanged):
        service.upload_start(str(root), "sample.bin", len(payload), digest)


def test_upload_failures_leave_destination_unmodified(workspace):
    """Guard checksums, missing offsets, cancellation, and filename conflicts."""
    root, service = workspace
    file = root / "original.bin"
    file.write_bytes(b"existing")
    digest = hashlib.sha256(b"new").hexdigest()
    with pytest.raises(FileChanged):
        service.upload_start(str(root), "original.bin", 3, digest)
    with pytest.raises(AccessDenied):
        service.upload_start(str(root), "../unsafe", 3, digest)
    with pytest.raises(FileLimitExceeded):
        service.upload_start(str(root), "large", MAX_TRANSFER_BYTES + 1, digest)
    session = service.upload_start(str(root), "fresh.bin", 3, digest)["session_id"]
    with pytest.raises(InvalidRange):
        service.upload_chunk(session, 1, base64.b64encode(b"a").decode())
    with pytest.raises(InvalidRange):
        service.upload_chunk(session, 0, "bad===")
    with pytest.raises(FileChanged):
        service.upload_finish(session)
    assert service.upload_cancel(session)["cancelled"]
    assert not (root / "fresh.bin").exists()
    assert file.read_bytes() == b"existing"


def test_upload_wrong_checksum_and_precommit_collision(workspace):
    """Refuse a changed target or corrupt content before committing."""
    root, service = workspace
    session = service.upload_start(str(root), "new.dat", 3, "0" * 64)["session_id"]
    service.upload_chunk(session, 0, base64.b64encode(b"abc").decode())
    with pytest.raises(FileChanged, match="checksum"):
        service.upload_finish(session)
    service.upload_cancel(session)
    session = service.upload_start(str(root), "new.dat", 3, hashlib.sha256(b"abc").hexdigest())["session_id"]
    service.upload_chunk(session, 0, base64.b64encode(b"abc").decode())
    (root / "new.dat").write_bytes(b"important")
    with pytest.raises(FileChanged, match="Destination appeared"):
        service.upload_finish(session)
    service.upload_cancel(session)
    assert (root / "new.dat").read_bytes() == b"important"


def test_upload_requires_explicit_root(workspace, tmp_path):
    """Do not imply upload permission from the viewer's read access."""
    root, _ = workspace
    read_only = BinaryTransfer(FilePolicy((root,)))
    with pytest.raises(AccessDenied):
        read_only.upload_start(str(root), "x", 0, hashlib.sha256(b"").hexdigest())
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(ValueError):
        BinaryTransfer(FilePolicy((root,)), (other,))


def test_registration_opt_in_and_mcp_json(workspace):
    """Keep all binary tools disabled by default and verify JSON tool contracts."""
    root, _ = workspace
    disabled = MCPStub()
    register_file_viewer(disabled, roots=(root,))
    assert not any("upload_" in name or "download_chunk" in name or
                   name == "file_manager_transfer_info" for name in disabled.tools)
    enabled = MCPStub()
    register_file_viewer(
        enabled, roots=(root,), enable_download=True,
        enable_upload=True, upload_roots=(root,),
    )
    file = root / "input.bin"
    file.write_bytes(b"\x00\xff\x10")
    info = json.loads(enabled.tools["file_manager_transfer_info"](str(file)))
    chunk = json.loads(enabled.tools["file_manager_download_chunk"](
        str(file), 0, info["revision"],
    ))
    assert base64.b64decode(chunk["content_base64"]) == file.read_bytes()
    for name in (
        "file_manager_transfer_capabilities", "file_manager_transfer_info",
        "file_manager_download_chunk", "file_manager_upload_start",
        "file_manager_upload_chunk", "file_manager_upload_finish",
        "file_manager_upload_cancel",
    ):
        assert enabled.tool_meta[name]["ui"]["visibility"] == ["app"]
    start = json.loads(enabled.tools["file_manager_upload_start"](
        str(root), "uploaded.bin", 3, hashlib.sha256(b"new").hexdigest(),
    ))
    session = start["session_id"]
    result = json.loads(enabled.tools["file_manager_upload_chunk"](
        session, 0, base64.b64encode(b"new").decode(),
    ))
    assert result["received_bytes"] == 3
    assert "revision" in json.loads(enabled.tools["file_manager_upload_finish"](session))
    assert (root / "uploaded.bin").read_bytes() == b"new"
