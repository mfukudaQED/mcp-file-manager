"""Compatibility wrapper for the established MCP File Viewer core."""

from __future__ import annotations

from mcp_file_viewer.extension import register_file_viewer


def register_file_manager(*args, **kwargs) -> None:
    """Register bounded file-manager tools without breaking legacy imports."""
    register_file_viewer(*args, **kwargs)
