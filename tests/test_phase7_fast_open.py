"""Fast-open must preserve revision, paging and read-only policy."""
from pathlib import Path

import pytest
from mcp_file_viewer.policy import FilePolicy, FileViewerError
from mcp_file_viewer.viewer import FileViewer


def test_fast_open_markdown_single_response(tmp_path: Path):
    file = tmp_path / "notes.md"
    file.write_text("# Overview\nHello\n## Methods\nWorld\n", encoding="utf8")
    v = FileViewer(FilePolicy(roots=(tmp_path,)))
    result = v.open_fast(str(file))
    assert result["content"] == file.read_text()
    assert result["kind"] == "markdown"
    assert result["total_lines"] == 4
    assert result["revision"] == v.info(str(file))["revision"]
    assert isinstance(result["server_elapsed_ms"], float)
    assert result["server_elapsed_ms"] >= 0
    assert [x["title"] for x in result["headings"]] == ["Overview", "Methods"]
    assert not result["has_more"]


def test_fast_open_paging_and_bounded_response(tmp_path: Path):
    file = tmp_path / "run.out"
    file.write_text("x" * 90 + "\n" + "abc\n" * 400, encoding="utf8")
    v = FileViewer(FilePolicy(roots=(tmp_path,), max_response_chars=800))
    first = v.open_fast(str(file))
    assert first["kind"] == "text" and first["has_more"]
    assert first["next_line"] > 1
    assert first["content"].startswith("x" * 90)
    assert v.read_text(str(file), start_line=first["next_line"], revision=first["revision"])["content"].startswith("abc")


def test_fast_open_limits_and_no_follow(tmp_path: Path):
    v = FileViewer(FilePolicy(roots=(tmp_path,)))
    with pytest.raises(FileViewerError):
        v.open_fast("/etc/passwd")
    f = tmp_path / "linked.md"
    f.symlink_to("/etc/passwd")
    with pytest.raises(FileViewerError):
        v.open_fast(str(f))


def test_fast_open_bounded_headings(tmp_path: Path):
    f = tmp_path / "lots.md"
    f.write_text("".join(f"## Header {i}\n" for i in range(50)), encoding="utf8")
    v = FileViewer(FilePolicy(roots=(tmp_path,)))
    item = v.open_fast(str(f))
    assert item["headings_truncated"] is True
    assert len(item["headings"]) == 30
