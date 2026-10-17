"""Git history tests with controlled command outputs (no git executable needed)."""
import hashlib
from pathlib import Path
import pytest
from mcp_file_viewer.editing import FileEditor
from mcp_file_viewer.git_history import GitHistory
from mcp_file_viewer.policy import FilePolicy, FileChanged, AccessDenied

COMMIT = "a" * 40
BLOB = "b" * 40

@pytest.fixture
def git_case(tmp_path, monkeypatch):
    target = tmp_path / "sample.txt"
    target.write_text("working")
    editor = FileEditor(FilePolicy(roots=(tmp_path,)))
    history = GitHistory(FilePolicy(roots=(tmp_path,)), editor)
    calls = []
    def fake_run(cwd, *args, limit=70000):
        calls.append(args)
        if args[0] == "rev-parse" and args[1] == "--show-toplevel":
            return 0, str(tmp_path).encode() + b"\n"
        if args[0] == "ls-files":
            return 0, b""
        if args[0] == "log":
            return 0, (COMMIT + "\t2026-10-17T22:00:00+09:00\tSample commit\n").encode()
        if args[0] == "rev-parse":
            return 0, (BLOB + "\n").encode()
        if args[0] == "cat-file" and args[1] == "-s":
            return 0, b"8\n"
        if args[0] == "cat-file" and args[1] == "blob":
            return 0, b"original"
        return 1, b""
    monkeypatch.setattr(history, "_run", fake_run)
    return target, editor, history, calls

def test_history_preview_restore(git_case):
    target, editor, history, calls = git_case
    result = history.history(str(target))
    assert result["managed"] and result["commits"][0]["id"] == COMMIT
    preview = history.read(str(target), COMMIT)
    assert preview["content"] == "original"
    current = editor.read_chunk(str(target))["revision"]
    saved = history.restore(str(target), COMMIT, current, preview["revision"])
    assert saved["restored_commit"] == COMMIT
    assert target.read_text() == "original"
    assert not (target.parent / ".mcp-file-manager-backups").exists()
    assert not any(a[0] in ("commit","push","add","checkout") for a in calls)

def test_restore_stale_revision(git_case):
    target, editor, history, _ = git_case
    stale = editor.read_chunk(str(target))["revision"]
    target.write_text("changed")
    preview = history.read(str(target), COMMIT)
    with pytest.raises(FileChanged):
        history.restore(str(target), COMMIT, stale, preview["revision"])
    assert target.read_text() == "changed"

def test_rejects_unrelated_commit_or_path(git_case):
    target, editor, history, _ = git_case
    with pytest.raises(Exception):
        history.read(str(target), "HEAD")
    with pytest.raises(Exception):
        history.read(str(target), "a" * 40 + ":../secrets")

def test_untracked_file_edit_remains_allowed(git_case, monkeypatch):
    target, editor, history, _ = git_case
    real = history._run
    def fake(cwd,*args,limit=70000):
        if args[0] == "ls-files":
            return 1, b""
        return real(cwd,*args,limit=limit)
    monkeypatch.setattr(history, "_run", fake)
    assert history.history(str(target))["managed"] is False
    with pytest.raises(AccessDenied):
        history.read(str(target), COMMIT)
    result = editor.save(str(target), editor.read_chunk(str(target))["revision"], "new")
    assert result["changed"]


def test_lustre_layout_attribute_is_allowed_but_acl_is_rejected(tmp_path, monkeypatch):
    """Allow Lustre's virtual layout metadata without weakening ACL checks."""
    import os

    target = tmp_path / "layout.txt"
    target.write_text("before")
    editor = FileEditor(FilePolicy(roots=(tmp_path,)))
    monkeypatch.setattr(os, "listxattr", lambda fd: ["lustre.lov"])
    old = editor.read_chunk(str(target))["revision"]
    assert editor.save(str(target), old, "after")["changed"]
    assert target.read_text() == "after"
    monkeypatch.setattr(os, "listxattr", lambda fd: ["lustre.lov", "system.posix_acl_access"])
    with pytest.raises(AccessDenied):
        editor.save(str(target), editor.read_chunk(str(target))["revision"], "blocked")
    assert target.read_text() == "after"
