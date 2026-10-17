"""Safe-save behavior without new private backups."""
from pathlib import Path
import pytest
from mcp_file_viewer.editing import FileEditor, BACKUP_DIRECTORY
from mcp_file_viewer.policy import AccessDenied, FileChanged, FilePolicy

@pytest.fixture
def workspace(tmp_path):
    directory = tmp_path / "approved"
    directory.mkdir()
    return directory, FileEditor(FilePolicy(roots=(directory,)))

def test_save_without_new_backups(workspace):
    directory, editor = workspace
    target = directory / "sample.txt"
    target.write_text("old")
    result = editor.save(str(target), editor.read_chunk(str(target))["revision"], "new")
    assert result["changed"] and "backup_path" not in result
    assert target.read_text() == "new"
    assert not (directory / BACKUP_DIRECTORY).exists()

def test_legacy_backups_are_preserved(workspace):
    directory, editor = workspace
    legacy = directory / BACKUP_DIRECTORY
    legacy.mkdir(mode=0o700)
    past = legacy / "old.bak"
    past.write_text("original")
    target = directory / "sample.txt"
    target.write_text("old")
    editor.save(str(target), editor.read_chunk(str(target))["revision"], "new")
    assert past.read_text() == "original"

def test_stale_edit_does_not_overwrite(workspace):
    directory, editor = workspace
    target = directory / "sample.txt"
    target.write_text("old")
    revision = editor.read_chunk(str(target))["revision"]
    target.write_text("changed elsewhere")
    with pytest.raises(FileChanged):
        editor.save(str(target), revision, "stale")
    assert target.read_text() == "changed elsewhere"

def test_hardlinks_denied(workspace):
    directory, editor = workspace
    target = directory / "sample.txt"
    target.write_text("linked")
    (directory / "linked.txt").hardlink_to(target)
    with pytest.raises(AccessDenied):
        editor.save(str(target), editor.read_chunk(str(target))["revision"], "broken")
