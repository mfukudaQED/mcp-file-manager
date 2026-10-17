"""Bounded, revision-checked editing of existing UTF-8 files."""
from __future__ import annotations

import errno
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import time

from .policy import DIRECTORY_FLAGS

from .policy import (
    AccessDenied, FileChanged, FileLimitExceeded, FilePolicy,
    InvalidRange, ReadOnlyFileAccess, UnsupportedText,
)

MAX_EDIT_BYTES = 64 * 1024
BACKUP_DIRECTORY = ".mcp-file-manager-backups"
BACKUP_REVISIONS = 3
_REVISION = re.compile(r"sha256:[0-9a-f]{64}\Z")


class FileEditor:
    """Edit small regular files beneath an explicitly authorized root."""

    def __init__(self, policy: FilePolicy):
        """Reuse the viewer's no-follow root traversal and file limits."""
        self.access = ReadOnlyFileAccess(policy)

    def read_chunk(self, path: str, offset: int = 0,
                   revision: str | None = None, max_chars: int = 7000) -> dict:
        """Return one bounded Unicode chunk from a revision-pinned snapshot."""
        if not isinstance(offset, int) or offset < 0:
            raise InvalidRange("Offset must be a nonnegative integer")
        if not isinstance(max_chars, int) or not 1 <= max_chars <= 7000:
            raise InvalidRange("max_chars must be between 1 and 7000")
        snap = self.access.read_text(path, revision)
        if snap.size_bytes > MAX_EDIT_BYTES:
            raise FileLimitExceeded("Editing is limited to 64 KiB UTF-8 files")
        if offset > len(snap.text):
            raise InvalidRange("Offset exceeds end of file")
        amount = min(max_chars, len(snap.text) - offset)
        result = {
            "path": snap.path, "revision": snap.revision,
            "size_bytes": snap.size_bytes, "total_chars": len(snap.text),
            "offset": offset, "content": "",
            "next_offset": offset, "has_more": False,
        }
        limit = self.access.policy.max_response_chars - 128
        while True:
            result["content"] = snap.text[offset:offset + amount]
            result["next_offset"] = offset + amount
            result["has_more"] = offset + amount < len(snap.text)
            if len(json.dumps(result, ensure_ascii=False, separators=(",", ":"))) <= limit:
                return result
            amount //= 2
            if amount < 1:
                raise FileLimitExceeded("Cannot fit text chunk in MCP response")

    @staticmethod
    def _assert_replaceable(fd: int, metadata: os.stat_result) -> None:
        """Refuse files whose filesystem metadata atomic replacement could lose."""
        if metadata.st_nlink != 1:
            raise AccessDenied("Hard-linked files cannot be edited safely")
        try:
            attributes = os.listxattr(fd)
        except OSError as exc:
            if exc.errno in (errno.ENOTSUP, errno.EOPNOTSUPP):
                attributes = []
            else:
                raise AccessDenied("Cannot inspect file extended attributes") from exc
        # Lustre exposes the file's storage layout as the virtual lustre.lov
        # attribute even on otherwise ordinary files. Replacing a small text
        # file creates a new inode and can assign a new layout, so do not
        # mistake this filesystem-managed attribute for an ACL or user xattr.
        # Continue to reject every other attribute, including POSIX ACLs.
        unexpected = set(attributes) - {"lustre.lov"}
        if unexpected:
            raise AccessDenied("Files with ACLs or extended attributes cannot be edited safely")

    @staticmethod
    def _backup(parent_fd: int, filename: str, original: bytes) -> str:
        """Persist a private copy before replacement, retaining three revisions."""
        try:
            os.mkdir(BACKUP_DIRECTORY, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        backup_fd = os.open(BACKUP_DIRECTORY, DIRECTORY_FLAGS, dir_fd=parent_fd)
        try:
            directory = os.fstat(backup_fd)
            if directory.st_uid != os.geteuid() or stat.S_IMODE(directory.st_mode) != 0o700:
                raise AccessDenied("Backup directory must be private (mode 0700)")
            prefix = hashlib.sha256(os.fsencode(filename)).hexdigest()[:24] + "-"
            backup_name = prefix + f"{time.time_ns():020d}-{secrets.token_hex(6)}.bak"
            backup_file_fd = os.open(
                backup_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600, dir_fd=backup_fd,
            )
            try:
                offset = 0
                while offset < len(original):
                    written = os.write(backup_file_fd, original[offset:])
                    if written <= 0:
                        raise OSError("Backup write returned no bytes")
                    offset += written
                os.fsync(backup_file_fd)
            except BaseException:
                os.unlink(backup_name, dir_fd=backup_fd)
                raise
            finally:
                os.close(backup_file_fd)
            try:
                os.fsync(backup_fd)
            except OSError:
                # Some HPC parallel filesystems do not support directory fsync.
                pass
            return BACKUP_DIRECTORY + "/" + backup_name
        finally:
            os.close(backup_fd)

    @staticmethod
    def _prune_backups(parent_fd: int, filename: str) -> None:
        """Limit successful-save backup retention without affecting the save result."""
        try:
            backup_fd = os.open(BACKUP_DIRECTORY, DIRECTORY_FLAGS, dir_fd=parent_fd)
            try:
                prefix = hashlib.sha256(os.fsencode(filename)).hexdigest()[:24] + "-"
                names = sorted(
                    name for name in os.listdir(backup_fd)
                    if name.startswith(prefix) and name.endswith(".bak")
                )
                for name in names[:-BACKUP_REVISIONS]:
                    info = os.stat(name, dir_fd=backup_fd, follow_symlinks=False)
                    if stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid():
                        os.unlink(name, dir_fd=backup_fd)
            finally:
                os.close(backup_fd)
        except OSError:
            # Cleanup can be retried on the next successful save.
            pass

    @staticmethod
    def _backup_prefix(filename: str) -> str:
        """Derive the private backup namespace for a single original filename."""
        return hashlib.sha256(os.fsencode(filename)).hexdigest()[:24] + "-"

    def _open_backup_folder(self, path: str) -> tuple[int, Path]:
        """Open a private backup folder only for a readable approved regular file."""
        target_fd, actual_path = self.access._open(path)
        try:
            target_stat = os.fstat(target_fd)
            if target_stat.st_uid != os.geteuid():
                raise AccessDenied("Backup access requires file ownership")
        finally:
            os.close(target_fd)
        parent_fd, _ = self.access._open(actual_path.parent, directory=True)
        try:
            backup_fd = os.open(BACKUP_DIRECTORY, DIRECTORY_FLAGS, dir_fd=parent_fd)
        except BaseException:
            os.close(parent_fd)
            raise
        os.close(parent_fd)
        stat_info = os.fstat(backup_fd)
        if stat_info.st_uid != os.geteuid() or stat.S_IMODE(stat_info.st_mode) != 0o700:
            os.close(backup_fd)
            raise AccessDenied("Backup directory must be private and user-owned")
        return backup_fd, actual_path

    def _read_backup_payload(self, path: str, backup_id: str) -> tuple[bytes, Path]:
        """Read a bounded private backup without following symlinks."""
        if not isinstance(backup_id, str) or len(backup_id) > 100:
            raise InvalidRange("Invalid backup identifier")
        backup_fd, actual_path = self._open_backup_folder(path)
        try:
            prefix = self._backup_prefix(actual_path.name)
            if not re.fullmatch(re.escape(prefix) + r"[0-9]{20}-[0-9a-f]{12}\.bak", backup_id):
                raise AccessDenied("Backup does not belong to the requested file")
            fd = os.open(backup_id, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=backup_fd)
            try:
                before = os.fstat(fd)
                if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                        or before.st_nlink != 1 or stat.S_IMODE(before.st_mode) != 0o600):
                    raise AccessDenied("Unsafe backup file metadata")
                if before.st_size > MAX_EDIT_BYTES:
                    raise FileLimitExceeded("Backup exceeds edit limit")
                payload = os.pread(fd, MAX_EDIT_BYTES + 1, 0)
                after = os.fstat(fd)
                signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
                if signature(before) != signature(after) or len(payload) != before.st_size:
                    raise FileChanged("Backup changed during read")
                if b"\x00" in payload:
                    raise UnsupportedText("Cannot restore a binary backup")
                try:
                    payload.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise UnsupportedText("Backup is not valid UTF-8") from exc
                return payload, actual_path
            finally:
                os.close(fd)
        finally:
            os.close(backup_fd)

    def list_backups(self, path: str) -> dict:
        """List up to three private restore points for an authorized file."""
        try:
            backup_fd, actual_path = self._open_backup_folder(path)
        except FileNotFoundError:
            # No backups yet is a normal state.
            fd, actual_path = self.access._open(path)
            os.close(fd)
            return {"path": str(actual_path), "backups": []}
        try:
            prefix = self._backup_prefix(actual_path.name)
            pattern = re.compile(re.escape(prefix) + r"[0-9]{20}-[0-9a-f]{12}\.bak\Z")
            names = sorted(
                (n for n in os.listdir(backup_fd) if pattern.fullmatch(n)), reverse=True
            )
            backups = []
            for name in names[:BACKUP_REVISIONS]:
                try:
                    metadata = os.stat(name, dir_fd=backup_fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid()
                        or stat.S_IMODE(metadata.st_mode) != 0o600
                        or metadata.st_nlink != 1 or metadata.st_size > MAX_EDIT_BYTES):
                    continue
                backups.append({
                    "id": name,
                    "size_bytes": metadata.st_size,
                    "saved_at_ns": int(name[len(prefix):len(prefix)+20]),
                })
            return {"path": str(actual_path), "backups": backups}
        finally:
            os.close(backup_fd)

    def read_backup(self, path: str, backup_id: str, offset: int = 0,
                    revision: str | None = None, max_chars: int = 5000) -> dict:
        """Read a UTF-8 backup in revision-pinned bounded chunks."""
        if type(offset) is not int or offset < 0 or type(max_chars) is not int or not 1 <= max_chars <= 5000:
            raise InvalidRange("Invalid backup text window")
        payload, actual_path = self._read_backup_payload(path, backup_id)
        current_revision = "sha256:" + hashlib.sha256(payload).hexdigest()
        if revision is not None and current_revision != revision:
            raise FileChanged("Backup changed; retry from the beginning")
        content = payload.decode("utf-8")
        if offset > len(content):
            raise InvalidRange("Backup offset exceeds file length")
        amount = min(max_chars, len(content)-offset)
        result = {
            "path": str(actual_path), "id": backup_id, "revision": current_revision,
            "total_chars": len(content), "offset": offset,
            "content": "", "next_offset": offset, "has_more": False,
        }
        limit = self.access.policy.max_response_chars - 128
        while True:
            result["content"] = content[offset:offset+amount]
            result["next_offset"] = offset+amount
            result["has_more"] = result["next_offset"] < len(content)
            if len(json.dumps(result, ensure_ascii=False, separators=(",", ":"))) <= limit:
                return result
            amount //= 2
            if amount < 1:
                raise FileLimitExceeded("Backup text cannot fit MCP response")

    def restore_backup(self, path: str, backup_id: str, expected_revision: str,
                       expected_backup_revision: str) -> dict:
        """Restore a selected revision via normal safe-save with a revision guard."""
        if not isinstance(expected_backup_revision, str) or not _REVISION.fullmatch(expected_backup_revision):
            raise InvalidRange("A valid backup revision is required")
        payload, actual_path = self._read_backup_payload(path, backup_id)
        revision = "sha256:" + hashlib.sha256(payload).hexdigest()
        if revision != expected_backup_revision:
            raise FileChanged("Backup changed after preview")
        result = self.save(str(actual_path), expected_revision, payload.decode("utf-8"))
        return {**result, "restored_backup_id": backup_id}

    def save(self, path: str, expected_revision: str, content: str) -> dict:
        """Atomically replace a file only when its original bytes still match."""
        if not isinstance(expected_revision, str) or not _REVISION.fullmatch(expected_revision):
            raise InvalidRange("A valid SHA-256 revision is required")
        if not isinstance(content, str) or "\x00" in content:
            raise UnsupportedText("Content must be UTF-8 text without NUL bytes")
        try:
            payload = content.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise UnsupportedText("Content contains invalid Unicode") from exc
        if len(payload) > MAX_EDIT_BYTES:
            raise FileLimitExceeded("Edited content exceeds 64 KiB")
        fd, actual_path = self.access._open(path)
        try:
            before = os.fstat(fd)
            if before.st_size > MAX_EDIT_BYTES:
                raise FileLimitExceeded("Editing is limited to 64 KiB UTF-8 files")
            if before.st_uid != os.geteuid() or not before.st_mode & stat.S_IWUSR:
                raise AccessDenied("Editing requires an owner-writable file")
            self._assert_replaceable(fd, before)
            original = os.pread(fd, MAX_EDIT_BYTES + 1, 0)
            after = os.fstat(fd)
            identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            if identity(before) != identity(after) or len(original) != before.st_size:
                raise FileChanged("File changed during revision check")
            if "sha256:" + hashlib.sha256(original).hexdigest() != expected_revision:
                raise FileChanged("File changed since it was opened; reload before saving")
            if b"\x00" in original:
                raise UnsupportedText("Cannot edit binary files")
            try:
                original.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise UnsupportedText("Cannot edit non-UTF-8 files") from exc

            if payload == original:
                return {"path": str(actual_path), "revision": expected_revision,
                        "size_bytes": len(payload), "changed": False}
            parent_fd, _ = self.access._open(actual_path.parent, directory=True)
            temp_name = ".mcp-file-manager-" + secrets.token_hex(12) + ".tmp"
            temp_fd = -1
            backup_relative = ""
            try:
                temp_fd = os.open(temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                                  os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
                if os.fstat(temp_fd).st_gid != before.st_gid:
                    os.fchown(temp_fd, -1, before.st_gid)
                os.fchmod(temp_fd, stat.S_IMODE(before.st_mode))
                position = 0
                while position < len(payload):
                    position += os.write(temp_fd, payload[position:])
                os.fsync(temp_fd)
                os.close(temp_fd)
                temp_fd = -1
                # Detect replacements and ordinary concurrent file changes.
                latest = os.stat(actual_path.name, dir_fd=parent_fd, follow_symlinks=False)
                if identity(latest) != identity(before) or identity(os.fstat(fd)) != identity(before):
                    raise FileChanged("File changed before commit; reload before saving")
                if os.pread(fd, MAX_EDIT_BYTES + 1, 0) != original:
                    raise FileChanged("File contents changed before commit")
                self._assert_replaceable(fd, latest)
                os.replace(temp_name, actual_path.name,
                           src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
                try:
                    os.fsync(parent_fd)
                except OSError:
                    # Some parallel filesystems do not support directory fsync.
                    pass
            finally:
                if temp_fd >= 0:
                    os.close(temp_fd)
                try:
                    os.unlink(temp_name, dir_fd=parent_fd)
                except FileNotFoundError:
                    pass
                os.close(parent_fd)
        finally:
            os.close(fd)
        return {
            "path": str(actual_path),
            "revision": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload), "changed": True,
        }
