"""Regression coverage for UI v22 first-1000-lines and bounded paging."""
from __future__ import annotations

import json
from pathlib import Path

from mcp_file_viewer.extension import register_file_viewer
from mcp_file_viewer.policy import FilePolicy
from mcp_file_viewer.viewer import FileViewer


class Registry:
    """Capture MCP handlers without starting a service."""

    def __init__(self) -> None:
        """Initialize an empty tool registry."""
        self.tools: dict = {}

    def resource(self, *args, **kwargs):
        """Accept an inert MCP resource decorator."""
        return lambda func: func

    def tool(self, name, **kwargs):
        """Keep the registered callable for a direct test."""
        def register(func):
            self.tools[name] = func
            return func
        return register


def test_first_thousand_lines_and_contiguous_pages(tmp_path: Path) -> None:
    """First thousand lines should be available with no truncated/duplicate page."""
    path = tmp_path / "output.log"
    lines = [f"row{i:04d}\n" for i in range(2500)]
    path.write_text("".join(lines), encoding="utf-8")
    stub = Registry()
    register_file_viewer(stub, roots=(tmp_path,))
    first = json.loads(stub.tools["file_manager_open_fast"](str(path)))
    assert first["start_line"] == 1
    assert first["next_line"] == 1001
    assert first["content"] == "".join(lines[:1000])
    more = json.loads(stub.tools["file_viewer_read_text"](
        str(path), first["next_line"], 1000, first["revision"]
    ))
    assert more["start_line"] == 1001
    assert more["next_line"] == 2001
    assert more["content"] == "".join(lines[1000:2000])
    final = json.loads(stub.tools["file_viewer_read_text"](
        str(path), more["next_line"], 1000, first["revision"]
    ))
    assert final["has_more"] is False
    assert first["content"] + more["content"] + final["content"] == "".join(lines)


def test_page_escapes_stay_within_json_response_limit(tmp_path: Path) -> None:
    """Escaping tabs and quotes must not make a bounded page fail serialization."""
    path = tmp_path / "escaped.log"
    path.write_text(('\t"quoted"\n' * 100), encoding="utf-8")
    budget = 512
    viewer = FileViewer(FilePolicy(roots=(tmp_path,), max_response_chars=budget))
    page = viewer.read_text(str(path), 1, 100)
    encoded = json.dumps(page, ensure_ascii=False, separators=(",", ":"))
    assert len(encoded) <= budget
    assert page["next_line"] > 1
    assert page["has_more"] is True
