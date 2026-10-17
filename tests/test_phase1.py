"""Regression tests for the Phase 1 file viewer core."""
from __future__ import annotations
import os
from pathlib import Path
import pytest
from mcp_file_viewer import FileViewer, FilePolicy, FileChanged
from mcp_file_viewer.policy import AccessDenied,FileLimitExceeded,UnsupportedText

@pytest.fixture
def viewer(tmp_path:Path)->FileViewer:
    """Return a read-only viewer with a temporary approved root."""
    return FileViewer(FilePolicy(roots=(tmp_path,),max_response_chars=120))

def test_chapter_and_pagination(viewer:FileViewer,tmp_path:Path)->None:
    """Ensure child headings are included and sections can be reconstructed."""
    p=tmp_path/"test.md"
    p.write_text("intro\n# Title\n## Same\naaaa\n### Child\nbbbb\n## Same\ncccc\n",encoding="utf-8")
    o=viewer.outline(str(p))
    assert [h["id"] for h in o["headings"]]==["h:2:1","h:3:2","h:5:3","h:7:2"]
    assert o["headings"][1]["end_line"]==6
    pieces=[];at=0
    while True:
        result=viewer.read_section(str(p),"h:3:2",o["revision"],at,max_chars=7)
        pieces.append(result["content"])
        if not result["has_more"]:break
        at=result["next_offset"]
    assert "".join(pieces)=="## Same\naaaa\n### Child\nbbbb\n"
    assert viewer.read_section(str(p),"preamble",o["revision"])["content"]=="intro\n"
    assert viewer.read_section(str(p),"document",o["revision"])["content"].startswith("intro\n")

def test_fences_and_setext(viewer:FileViewer,tmp_path:Path)->None:
    """Ignore heading-looking lines inside code and recognize Setext."""
    p=tmp_path/"a.md"
    p.write_text("~~~md\n# not a heading\n~~~\nHeading\n=======\n    # code\n## Actual\n",encoding="utf-8")
    assert [(h["title"],h["start_line"]) for h in viewer.outline(str(p))["headings"]]==[("Heading",4),("Actual",7)]

def test_revision_and_ranges(viewer:FileViewer,tmp_path:Path)->None:
    """Refuse stale section retrieval and reject invalid ranges."""
    p=tmp_path/"test.md";p.write_text("# A\na\n",encoding="utf-8")
    revision=viewer.outline(str(p))["revision"]
    p.write_text("# B\nb\n",encoding="utf-8")
    with pytest.raises(FileChanged):viewer.read_section(str(p),"h:1:1",revision)
    with pytest.raises(Exception):viewer.read_text(str(p),start_line=0)

def test_denied_paths(viewer:FileViewer,tmp_path:Path)->None:
    """Reject symlink escapes and credentials without reading their contents."""
    (tmp_path/".env").write_text("secret",encoding="utf-8")
    with pytest.raises(AccessDenied):viewer.info(str(tmp_path/".env"))
    outside=tmp_path.parent/"outsider-file.txt";outside.write_text("not allowed")
    (tmp_path/"link.txt").symlink_to(outside)
    with pytest.raises(AccessDenied):viewer.info(str(tmp_path/"link.txt"))

def test_binary_and_limits(viewer:FileViewer,tmp_path:Path)->None:
    """Refuse NUL-encoded files and oversize files."""
    p=tmp_path/"binary.dat";p.write_bytes(b"a\x00b")
    with pytest.raises(UnsupportedText):viewer.info(str(p))
    small=FileViewer(FilePolicy(roots=(tmp_path,),max_file_bytes=4))
    q=tmp_path/"big.log";q.write_text("longer than four bytes")
    with pytest.raises(FileLimitExceeded):small.info(str(q))

def test_directory(viewer:FileViewer,tmp_path:Path)->None:
    """Skip hidden entries while reporting visible normal files."""
    (tmp_path/"test.txt").write_text("x")
    assert "test.txt" in [x["name"] for x in viewer.list_files(str(tmp_path))["entries"]]
