"""Integration tests for the opt-in file viewer MCP registration."""

from __future__ import annotations

import json
import asyncio
from pathlib import Path

import pytest

pytest.importorskip("mcp")
pytest.importorskip("hpc_mcp")

from hpc_mcp.config import Settings
from hpc_mcp.server import build_server


def _server(root: Path, *, enabled: bool):
    """Build an isolated in-memory MCP server bound to a temporary root."""
    return build_server(
        Settings(
            roots=(root,),
            scheduler_type="none",
            enable_file_viewer=enabled,
        )
    )


def _names(server) -> set[str]:
    """Return names of locally registered MCP tools."""
    return {tool.name for tool in server._tool_manager.list_tools()}


def _invoke(server, name: str, **kwargs: object) -> dict:
    """Invoke an MCP tool via the SDK tool manager and decode its JSON text."""
    data = asyncio.run(server._tool_manager.call_tool(name, kwargs))
    assert isinstance(data, str)
    return json.loads(data)


def test_opt_in_only(tmp_path: Path) -> None:
    """Preserve the existing tool registry when the extension is disabled."""
    disabled = _server(tmp_path, enabled=False)
    enabled = _server(tmp_path, enabled=True)
    expected = {
        "file_viewer_open",
        "file_manager_panel",
        "file_manager_open_fast",
        "file_viewer_list",
        "file_viewer_info",
        "file_viewer_read_text",
        "file_viewer_outline",
        "file_viewer_read_section",
        "file_manager_search_names",
        "file_manager_tail",
        "file_manager_log_status",
        "file_manager_log_window",
        "file_manager_diagnose",
    }
    assert not (_names(disabled) & expected)
    assert _names(enabled) - _names(disabled) == expected
    assert _names(disabled) == _names(enabled) - expected


def test_read_open_outline_and_section(tmp_path: Path) -> None:
    """Return readable JSON for common read-only file operations."""
    doc = tmp_path / "sample.md"
    doc.write_text("# Heading\nHello!\n", encoding="utf-8")
    server = _server(tmp_path, enabled=True)
    panel = _invoke(server, "file_manager_panel")
    assert panel == {"ui_available": True, "entrypoint": "thread"}
    info = _invoke(server, "file_viewer_open", path=str(doc))
    assert info["kind"] == "markdown"
    assert info["ui_available"] is True
    assert info["total_lines"] == 2
    outline = _invoke(server, "file_viewer_outline", path=str(doc))
    assert outline["headings"][0]["title"] == "Heading"
    section = _invoke(
        server, "file_viewer_read_section", path=str(doc),
        section_id=outline["headings"][0]["id"], revision=outline["revision"]
    )
    assert section["content"] == "# Heading\nHello!\n"
    read = _invoke(server, "file_viewer_read_text", path=str(doc))
    assert read["content"] == section["content"]
    entries = _invoke(server, "file_viewer_list", path=str(tmp_path))
    assert "sample.md" in {item["name"] for item in entries["entries"]}


def test_denied_and_missing_paths(tmp_path: Path) -> None:
    """Deny access outside configured roots and handle missing files."""
    server = _server(tmp_path, enabled=True)
    outside = _invoke(server, "file_viewer_info", path="/etc/passwd")
    assert outside["error"]["code"] == "permission_denied"
    missing = _invoke(server, "file_viewer_info", path=str(tmp_path / "missing"))
    assert missing["error"]["code"] == "not_found"


def test_stale_revision(tmp_path: Path) -> None:
    """Reject a stale revision rather than returning new file contents."""
    doc = tmp_path / "test.md"
    doc.write_text("# Original\n", encoding="utf-8")
    server = _server(tmp_path, enabled=True)
    info = _invoke(server, "file_viewer_info", path=str(doc))
    doc.write_text("# Changed\n", encoding="utf-8")
    result = _invoke(
        server, "file_viewer_read_text",
        path=str(doc), revision=info["revision"]
    )
    assert result["error"]["code"] == "file_changed"


def test_result_bounded(tmp_path: Path) -> None:
    """Return a small error rather than an oversized MCP tool response."""
    doc = tmp_path / "big.md"
    doc.write_text("a" * 14000, encoding="utf-8")
    server = _server(tmp_path, enabled=True)
    result = _invoke(server, "file_viewer_read_text", path=str(doc))
    assert result["error"]["code"] in ("invalid_range", "response_too_large")
