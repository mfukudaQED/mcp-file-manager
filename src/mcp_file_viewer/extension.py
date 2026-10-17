"""Opt-in, read-only MCP tool registration for the file viewer."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, Callable

from .policy import (
    AccessDenied,
    FileChanged,
    FileLimitExceeded,
    FilePolicy,
    FileViewerError,
    InvalidRange,
    UnsupportedText,
)
from .viewer import FileViewer

# Bump the resource URI when shipping a new UI to avoid reusing cached host iframes.
UI_URI = "ui://mcp-file-manager/v15/app.html"
V14_UI_URI = "ui://mcp-file-manager/v14/app.html"
V13_UI_URI = "ui://mcp-file-manager/v13/app.html"
V12_UI_URI = "ui://mcp-file-manager/v12/app.html"
V11_UI_URI = "ui://mcp-file-manager/v11/app.html"
V10_UI_URI = "ui://mcp-file-manager/v10/app.html"
V9_UI_URI = "ui://mcp-file-manager/v9/app.html"
V8_UI_URI = "ui://mcp-file-manager/v8/app.html"
V7_UI_URI = "ui://mcp-file-manager/v7/app.html"
V6_UI_URI = "ui://mcp-file-manager/v6/app.html"
V5_UI_URI = "ui://mcp-file-manager/v5/app.html"
V4_UI_URI = "ui://mcp-file-manager/v4/app.html"
V3_UI_URI = "ui://mcp-file-manager/v3/app.html"
PREVIOUS_UI_URI = "ui://mcp-file-manager/v2/app.html"
LEGACY_UI_URI = "ui://mcp-file-manager/app.html"
UI_MIME = "text/html;profile=mcp-app"


def register_file_viewer(
    mcp: Any,
    *,
    roots: tuple[Path, ...],
    max_file_bytes: int = 2 * 1024 * 1024,
    enable_edit: bool = False,
    max_response_chars: int = 12_000,
) -> None:
    """Register bounded read-only viewer tools on an existing MCP server.

    A caller must supply its already-authorized filesystem roots.
    This module never registers write tools, commands, or a network listener.
    MCP outputs are JSON text to support clients that lose structured results.
    """
    limit = min(max_response_chars, 12_000)
    if limit < 128:
        raise ValueError("max_response_chars must be at least 128")
    policy = FilePolicy(
        roots=roots,
        max_file_bytes=min(max_file_bytes, 16 * 1024 * 1024),
        max_response_chars=limit,
        max_lines=1000,
        max_headings=2000,
    )
    viewer = FileViewer(policy)
    if enable_edit:
        from .editing import FileEditor
        from .git_history import GitHistory
        editor = FileEditor(policy)
        git_history = GitHistory(policy, editor)

    def encode(value: dict[str, Any]) -> str:
        """Convert a result to bounded, readable MCP text."""
        serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if len(serialized) > limit:
            return json.dumps(
                {
                    "error": {
                        "code": "response_too_large",
                        "message": "Request a smaller range or fewer entries.",
                    }
                }
            )
        return serialized

    def invoke(action: Callable[[], dict[str, Any]]) -> str:
        """Return safe and machine-readable errors without exposing internals."""
        try:
            return encode(action())
        except FileViewerError as exc:
            return encode({"error": {"code": exc.code, "message": str(exc)}})
        except FileNotFoundError:
            return encode({"error": {"code": "not_found", "message": "File not found."}})
        except PermissionError:
            return encode({"error": {"code": "permission_denied", "message": "Access denied."}})
        except (IsADirectoryError, NotADirectoryError, ValueError, OSError):
            return encode({"error": {"code": "invalid_request", "message": "Invalid file request."}})

    @mcp.resource(UI_URI, mime_type=UI_MIME, name="MCP File Manager (UI v15)")
    @mcp.resource(V14_UI_URI, mime_type=UI_MIME, name="MCP File Manager (UI v14 URI)")
    @mcp.resource(V13_UI_URI, mime_type=UI_MIME, name="MCP File Manager (UI v13 URI)")
    @mcp.resource(V12_UI_URI, mime_type=UI_MIME, name="MCP File Manager (UI v12 URI)")
    @mcp.resource(V11_UI_URI, mime_type=UI_MIME, name="MCP File Manager (UI v11 URI)")
    @mcp.resource(V10_UI_URI, mime_type=UI_MIME, name="MCP File Manager (UI v10 URI)")
    @mcp.resource(V9_UI_URI, mime_type=UI_MIME, name="MCP File Manager (UI v9 URI)")
    @mcp.resource(V8_UI_URI, mime_type=UI_MIME, name="MCP File Manager (UI v8 URI)")
    @mcp.resource(LEGACY_UI_URI, mime_type=UI_MIME, name="MCP File Manager (legacy URI)")
    @mcp.resource(PREVIOUS_UI_URI, mime_type=UI_MIME, name="MCP File Manager (UI v2 URI)")
    @mcp.resource(V3_UI_URI, mime_type=UI_MIME, name="MCP File Manager (UI v3 URI)")
    @mcp.resource(V4_UI_URI, mime_type=UI_MIME, name="MCP File Manager (UI v4 URI)")
    @mcp.resource(V5_UI_URI, mime_type=UI_MIME, name="MCP File Manager (UI v5 URI)")
    @mcp.resource(V6_UI_URI, mime_type=UI_MIME, name="MCP File Manager (UI v6 URI)")
    @mcp.resource(V7_UI_URI, mime_type=UI_MIME, name="MCP File Manager (UI v7 URI)")
    def file_manager_ui() -> str:
        """Expose the self-contained, read-only MCP Apps UI resource."""
        return files("mcp_file_viewer").joinpath("ui/app.html").read_text(encoding="utf-8")

    @mcp.tool(name="file_viewer_open", meta={"ui": {"resourceUri": UI_URI}})
    def file_viewer_open(path: str) -> str:
        """Open authorized text metadata; UI registration is a separate phase."""
        def action() -> dict[str, Any]:
            result = viewer.info(path)
            result["kind"] = "markdown" if path.lower().endswith(".md") else "text"
            result["ui_available"] = True
            return result

        return invoke(action)

    @mcp.tool(name="file_manager_open_fast")
    def file_manager_open_fast(path: str) -> str:
        """Return bounded file metadata, first text and Markdown headings at once."""
        return invoke(lambda: viewer.open_fast(path))

    @mcp.tool(name="file_viewer_list")
    def file_viewer_list(path: str, limit: int = 50) -> str:
        """List up to 100 entries in one authorized directory."""
        return invoke(lambda: viewer.list_files(path, limit=min(limit, 100)))

    @mcp.tool(name="file_manager_search_names")
    def file_manager_search_names(path: str, query: str, limit: int = 40) -> str:
        """Bounded filename search in one authorized directory, with no recursion."""
        return invoke(lambda: viewer.search_names(path, query, limit))

    @mcp.tool(name="file_manager_tail")
    def file_manager_tail(path: str, max_bytes: int = 4096, max_lines: int = 80) -> str:
        """Read a capped suffix of a large text log without scanning the whole file."""
        return invoke(lambda: viewer.tail_text(path, max_bytes, max_lines))

    @mcp.tool(name="file_manager_diagnose")
    def file_manager_diagnose(path: str) -> str:
        """Classify explicit SCF/error/warning/timing markers in a capped log suffix."""
        return invoke(lambda: viewer.diagnose_log(path))

    @mcp.tool(name="file_manager_log_status")
    def file_manager_log_status(path: str) -> str:
        """Inspect one log without reading its contents."""
        return invoke(lambda: viewer.log_status(path))

    @mcp.tool(name="file_manager_log_window")
    def file_manager_log_window(path: str, direction: str = "tail",
                                offset: int = 0, max_bytes: int = 4096) -> str:
        """Read a bounded UTF-8 byte window of an authorized regular file."""
        return invoke(lambda: viewer.log_window(path, direction, offset, max_bytes))

    @mcp.tool(name="file_viewer_info")
    def file_viewer_info(path: str) -> str:
        """Report text size, lines, and revision for an authorized file."""
        return invoke(lambda: viewer.info(path))

    @mcp.tool(name="file_viewer_read_text")
    def file_viewer_read_text(
        path: str, start_line: int = 1, max_lines: int = 100, revision: str | None = None
    ) -> str:
        """Read a bounded UTF-8 line range, optionally pinned to a revision."""
        return invoke(lambda: viewer.read_text(path, start_line, min(max_lines, 100), revision))

    @mcp.tool(name="file_viewer_outline")
    def file_viewer_outline(path: str) -> str:
        """Extract Markdown headings, line ranges, and revision."""
        return invoke(lambda: viewer.outline(path))

    @mcp.tool(name="file_viewer_read_section")
    def file_viewer_read_section(
        path: str, section_id: str, revision: str,
        offset: int = 0, max_chars: int = 5000,
    ) -> str:
        """Read one Markdown section with revision and continuation offset."""
        return invoke(
            lambda: viewer.read_section(path, section_id, revision, offset, min(max_chars, 5000))
        )

    if enable_edit:
        @mcp.tool(name="file_manager_edit_read")
        def file_manager_edit_read(
            path: str, offset: int = 0,
            revision: str | None = None, max_chars: int = 7000,
        ) -> str:
            """Read a bounded chunk of an editable file, pinned to one revision."""
            return invoke(lambda: editor.read_chunk(path, offset, revision, max_chars))

        @mcp.tool(name="file_manager_git_history")
        def file_manager_git_history(path: str) -> str:
            """Show recent Git commits for an authorized tracked file."""
            return invoke(lambda: git_history.history(path))

        @mcp.tool(name="file_manager_git_read")
        def file_manager_git_read(
            path: str, commit: str, offset: int = 0,
            revision: str | None = None, max_chars: int = 5000,
        ) -> str:
            """Read a bounded revision-pinned historical Git file."""
            return invoke(lambda: git_history.read(path, commit, offset, revision, max_chars))

        @mcp.tool(name="file_manager_git_restore")
        def file_manager_git_restore(
            path: str, commit: str,
            expected_revision: str, expected_git_revision: str,
        ) -> str:
            """Restore a Git file revision through safe atomic editing."""
            return invoke(lambda: git_history.restore(
                path, commit, expected_revision, expected_git_revision))

        @mcp.tool(name="file_manager_edit_save")
        def file_manager_edit_save(path: str, expected_revision: str, content: str) -> str:
            """Save existing UTF-8 text with a required original SHA-256 revision."""
            return invoke(lambda: editor.save(path, expected_revision, content))
