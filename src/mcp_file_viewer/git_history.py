"""Read-only Git history for authorized files, with opt-in revision-safe restore."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from .editing import FileEditor, MAX_EDIT_BYTES
from .policy import (
    AccessDenied, FileChanged, FileLimitExceeded, FilePolicy,
    FileViewerError, InvalidRange, UnsupportedText,
)

_COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


class GitHistory:
    """Connect a bounded file viewer to Git, without staging or committing."""

    def __init__(self, policy: FilePolicy, editor: FileEditor):
        self.editor = editor
        self.max_response_chars = policy.max_response_chars

    @staticmethod
    def _run(cwd: Path, *args: str, limit: int = 70000) -> tuple[int, bytes]:
        # Git must not inherit caller-selected repository or execution settings.
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update({
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_PAGER": "cat",
        })
        try:
            proc = subprocess.run(
                ["git", "-C", str(cwd), *args],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise FileViewerError("Git is unavailable or timed out") from exc
        if len(proc.stdout) > limit:
            raise FileLimitExceeded("Git output exceeds the allowed limit")
        return proc.returncode, proc.stdout

    def _file(self, path: str) -> tuple[Path | None, str | None, Path]:
        fd, actual_path = self.editor.access._open(path)
        os.close(fd)
        result, output = self._run(actual_path.parent, "rev-parse", "--show-toplevel", limit=8192)
        if result:
            return None, None, actual_path
        repo_root = Path(os.fsdecode(output).strip())
        if not repo_root.is_absolute():
            raise FileViewerError("Invalid Git worktree root")
        try:
            relative = actual_path.relative_to(repo_root).as_posix()
        except ValueError as exc:
            raise AccessDenied("Git root does not contain the requested file") from exc
        code, _ = self._run(repo_root, "ls-files", "--error-unmatch", "--", relative)
        if code:
            return None, None, actual_path
        return repo_root, relative, actual_path

    def history(self, path: str) -> dict:
        """List committed history for one tracked file, not other repository paths."""
        repo_root, relative, actual_path = self._file(path)
        if repo_root is None:
            return {"path": str(actual_path), "managed": False, "commits": []}
        code, output = self._run(repo_root, "log", "--max-count=20",
                                 "--format=%H%x09%aI%x09%s", "--", relative)
        if code:
            raise FileViewerError("Unable to list file history")
        commits = []
        for raw_line in output.decode("utf-8", "replace").splitlines():
            parts = raw_line.split("\t", 2)
            if len(parts) != 3 or not _COMMIT.fullmatch(parts[0]):
                continue
            commits.append({
                "id": parts[0], "date": parts[1][:48], "subject": parts[2][:180],
            })
        return {"path": str(actual_path), "managed": True, "commits": commits}

    def _committed_text(self, path: str, commit: str) -> tuple[str, Path]:
        if not isinstance(commit, str) or not _COMMIT.fullmatch(commit):
            raise InvalidRange("A full Git commit identifier is required")
        repo_root, relative, actual_path = self._file(path)
        if repo_root is None:
            raise AccessDenied("File is not tracked in a Git repository")
        # A commit:path selector cannot escape the authorized file. Git does not
        # run textconv, smudge filters or checkout hooks for cat-file blobs.
        code, output = self._run(
            repo_root, "rev-parse", "--verify", f"{commit}:{relative}", limit=256)
        if code:
            raise FileViewerError("The selected commit does not contain this file")
        blob = output.decode("ascii", "replace").strip()
        if not _COMMIT.fullmatch(blob):
            raise FileViewerError("Invalid Git object identifier")
        code, size_bytes = self._run(repo_root, "cat-file", "-s", blob, limit=64)
        if code or not size_bytes.strip().isdigit():
            raise FileViewerError("Unable to inspect Git blob")
        if int(size_bytes) > MAX_EDIT_BYTES:
            raise FileLimitExceeded("Historical file exceeds 64 KiB")
        code, payload = self._run(repo_root, "cat-file", "blob", blob, limit=MAX_EDIT_BYTES)
        if code:
            raise FileViewerError("Unable to read the selected Git revision")
        if b"\x00" in payload:
            raise UnsupportedText("Cannot preview a binary Git revision")
        try:
            return payload.decode("utf-8"), actual_path
        except UnicodeDecodeError as exc:
            raise UnsupportedText("Git revision is not UTF-8 text") from exc

    def read(self, path: str, commit: str, offset: int = 0,
             revision: str | None = None, max_chars: int = 5000) -> dict:
        """Return one bounded chunk of a specific committed file revision."""
        if type(offset) is not int or offset < 0 or type(max_chars) is not int or not 1 <= max_chars <= 5000:
            raise InvalidRange("Invalid Git text range")
        content, actual_path = self._committed_text(path, commit)
        current_revision = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
        if revision is not None and current_revision != revision:
            raise FileChanged("Committed file revision differs from preview")
        if offset > len(content):
            raise InvalidRange("Offset exceeds committed file length")
        amount = min(max_chars, len(content) - offset)
        result = {
            "path": str(actual_path), "commit": commit, "revision": current_revision,
            "total_chars": len(content), "offset": offset, "content": "",
            "next_offset": offset, "has_more": False,
        }
        limit = self.max_response_chars - 128
        while True:
            result["content"] = content[offset:offset + amount]
            result["next_offset"] = offset + amount
            result["has_more"] = result["next_offset"] < len(content)
            if len(json.dumps(result, ensure_ascii=False, separators=(",", ":"))) <= limit:
                return result
            amount //= 2
            if amount < 1:
                raise FileLimitExceeded("Git history chunk cannot fit MCP response")

    def restore(self, path: str, commit: str, expected_revision: str,
                expected_git_revision: str) -> dict:
        """Write a committed revision through revision-checked atomic save."""
        if not isinstance(expected_git_revision, str) or not re.fullmatch(
                r"sha256:[0-9a-f]{64}", expected_git_revision):
            raise InvalidRange("A previewed Git file revision is required")
        content, actual_path = self._committed_text(path, commit)
        if "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest() != expected_git_revision:
            raise FileChanged("Git file content changed after preview")
        result = self.editor.save(str(actual_path), expected_revision, content)
        return {**result, "restored_commit": commit}
