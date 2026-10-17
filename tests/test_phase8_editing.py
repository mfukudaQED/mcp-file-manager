"""Exercise safe edit reads, saves, conflicts, and authorization."""
from pathlib import Path
import os
import pytest

from mcp_file_viewer.editing import FileEditor, MAX_EDIT_BYTES
from mcp_file_viewer.policy import FilePolicy, FileChanged, AccessDenied, FileLimitExceeded, InvalidRange

@pytest.fixture
def sandbox(tmp_path: Path):
    """Return editor with a private authorized directory."""
    root = tmp_path / "approved"
    root.mkdir()
    return root, FileEditor(FilePolicy(roots=(root,)))

def test_save_and_conflict(sandbox):
    """Confirm a new revision is returned and stale saves fail."""
    root, editor = sandbox
    path = root / "sample.md"
    path.write_text("First\n", encoding="utf-8")
    old = editor.read_chunk(str(path))
    saved = editor.save(str(path), old["revision"], "Second\n")
    assert saved["changed"] and saved["revision"] != old["revision"]
    assert path.read_text() == "Second\n"
    with pytest.raises(FileChanged):
        editor.save(str(path), old["revision"], "Stale\n")

def test_chunks_and_noop(sandbox):
    """Round-trip Unicode text through revision-pinned chunks."""
    root, editor = sandbox
    path = root / "sample.f90"
    original = "αβ\n" * 3000
    path.write_text(original, encoding="utf-8")
    chunks = []
    pos = 0
    rev = None
    while True:
        response = editor.read_chunk(str(path), pos, rev, 1200)
        rev = response["revision"]
        chunks.append(response["content"])
        pos = response["next_offset"]
        if not response["has_more"]:
            break
    assert "".join(chunks) == original
    assert editor.save(str(path), rev, original)["changed"] is False

def test_restrictions(sandbox, tmp_path):
    """Reject non-regular files, excessive content and unauthorized locations."""
    root, editor = sandbox
    path = root / "test.txt"
    path.write_text("abc")
    revision = editor.read_chunk(str(path))["revision"]
    with pytest.raises(FileLimitExceeded):
        editor.save(str(path), revision, "x" * (MAX_EDIT_BYTES + 1))
    with pytest.raises(InvalidRange):
        editor.save(str(path), "invalid", "data")
    external = tmp_path / "outside.txt"
    external.write_text("external")
    with pytest.raises(AccessDenied):
        editor.read_chunk(str(external))
    link = root / "link.txt"
    link.symlink_to(external)
    with pytest.raises(AccessDenied):
        editor.read_chunk(str(link))

def test_permission_requirement(sandbox):
    """Reject owner non-writable targets without modifying them."""
    root, editor = sandbox
    path = root / "ro.txt"
    path.write_text("untouched")
    rev = editor.read_chunk(str(path))["revision"]
    path.chmod(0o444)
    with pytest.raises(AccessDenied):
        editor.save(str(path), rev, "changed")
    assert path.read_text() == "untouched"
