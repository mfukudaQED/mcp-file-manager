"""Bounded filename lookup and large-file tail tests."""
from pathlib import Path
from mcp_file_viewer.policy import FilePolicy, FileViewerError
from mcp_file_viewer.viewer import FileViewer
import pytest

def test_filename_search(tmp_path: Path):
    for n in ["job-a.log", "job-b.log", "other.txt", ".hidden.log"]:
        (tmp_path/n).write_text("x")
    v = FileViewer(FilePolicy(roots=(tmp_path,)))
    r = v.search_names(str(tmp_path), "job", limit=1)
    assert len(r["entries"]) == 1 and r["truncated"] is True
    assert r["inspected_entries"] >= 3
    assert not any(x["name"].startswith(".") for x in r["entries"])

def test_tail_beyond_full_read_limit(tmp_path: Path):
    p = tmp_path/"large.log"
    p.write_bytes(b"data\n" * (3 * 1024 * 1024 // 5) + b"TAIL_SENTINEL\n")
    v = FileViewer(FilePolicy(roots=(tmp_path,), max_file_bytes=1024))
    with pytest.raises(FileViewerError):
        v.info(str(p))
    data = v.tail_text(str(p), max_bytes=2048, max_lines=10)
    assert data["content"].endswith("TAIL_SENTINEL\n")
    assert data["has_earlier"] and data["size_bytes"] > 2_000_000
    assert len(data["content"].encode()) <= 2048

def test_denied_tail(tmp_path: Path):
    v = FileViewer(FilePolicy(roots=(tmp_path,)))
    with pytest.raises(FileViewerError):
        v.tail_text("/etc/passwd")

def test_invalid_limits(tmp_path: Path):
    v = FileViewer(FilePolicy(roots=(tmp_path,)))
    with pytest.raises(FileViewerError):
        v.search_names(str(tmp_path), "x", limit=1000)
    with pytest.raises(FileViewerError):
        v.tail_text(str(tmp_path/"missing"), max_bytes=100000)
