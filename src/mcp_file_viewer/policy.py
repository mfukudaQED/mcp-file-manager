"""Read-only, bounded file access restricted to approved directory roots."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat

DENIED_COMPONENTS = frozenset({
    ".ssh", ".gnupg", ".aws", ".kube", ".config", ".local", ".git",
    ".env", ".netrc", ".npmrc", ".credentials", "credentials",
    "id_rsa", "id_ed25519", "id_ecdsa",
})
DENIED_SUFFIXES = (".pem", ".p12", ".pfx", ".key")
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


class FileViewerError(Exception):
    """Base exception for file-viewer API errors."""

    code = "file_viewer_error"


class AccessDenied(FileViewerError):
    """An unauthorized path or unsafe filesystem entry was requested."""

    code = "permission_denied"


class FileLimitExceeded(FileViewerError):
    """A request exceeds a resource limit."""

    code = "limit_exceeded"


class FileChanged(FileViewerError):
    """The file revision differs from the caller's expected revision."""

    code = "file_changed"


class UnsupportedText(FileViewerError):
    """The requested file is not supported as UTF-8 text."""

    code = "unsupported_text"


class InvalidRange(FileViewerError):
    """A line, section, or character range is invalid."""

    code = "invalid_range"


@dataclass(frozen=True)
class FilePolicy:
    """Define authorized roots and conservative file-reading limits."""

    roots: tuple[Path, ...]
    max_file_bytes: int = 2 * 1024 * 1024
    max_response_chars: int = 12_000
    max_lines: int = 1_000
    max_headings: int = 2_000

    def __post_init__(self) -> None:
        """Canonicalize existing roots and reject unsafe settings."""
        if not self.roots:
            raise ValueError("At least one approved root is required")
        canonical = tuple(Path(root).expanduser().resolve(strict=True) for root in self.roots)
        if any(not root.is_dir() for root in canonical):
            raise ValueError("All approved roots must be directories")
        if not (1 <= self.max_file_bytes <= 16 * 1024 * 1024):
            raise ValueError("max_file_bytes must be between 1 and 16 MiB")
        if not (1 <= self.max_response_chars <= 100_000):
            raise ValueError("Invalid max_response_chars")
        if not (1 <= self.max_lines <= 10_000):
            raise ValueError("Invalid max_lines")
        if not (1 <= self.max_headings <= 100_000):
            raise ValueError("Invalid max_headings")
        object.__setattr__(self, "roots", canonical)


@dataclass(frozen=True)
class TextSnapshot:
    """A consistent bounded UTF-8 file snapshot and its content hash."""

    path: str
    revision: str
    size_bytes: int
    mtime_ns: int
    text: str
    lines: tuple[str, ...]

    @property
    def total_lines(self) -> int:
        """Return logical line count, including the final nonempty line."""
        return len(self.lines)


class ReadOnlyFileAccess:
    """Open files relative to approved roots using no-follow directory handles."""

    def __init__(self, policy: FilePolicy):
        """Bind filesystem access to a previously validated policy."""
        self.policy = policy

    @staticmethod
    def _blocked(parts: tuple[str, ...]) -> bool:
        """Exclude credentials and private configuration paths."""
        for part in parts:
            lowered = part.lower()
            if lowered in DENIED_COMPONENTS or lowered.startswith(".env."):
                return True
            if lowered.endswith(DENIED_SUFFIXES):
                return True
        return False

    def _location(self, path: str | Path) -> tuple[Path, tuple[str, ...]]:
        """Map a requested absolute path to one approved canonical root."""
        if not path or "\x00" in str(path):
            raise ValueError("Invalid file path")
        raw = Path(path).expanduser()
        if not raw.is_absolute():
            raise ValueError("An absolute file path is required")
        if self._blocked(raw.parts):
            raise AccessDenied("Credential or private configuration path")
        canonical = raw.resolve(strict=False)
        if self._blocked(canonical.parts):
            raise AccessDenied("Credential or private configuration path")
        for root in sorted(self.policy.roots, key=lambda x: len(x.parts), reverse=True):
            if canonical == root or canonical.is_relative_to(root):
                return root, canonical.relative_to(root).parts
        raise AccessDenied("File is outside approved roots")

    def _open(self, path: str | Path, directory: bool = False) -> tuple[int, Path]:
        """Securely traverse from a root without following descendant symlinks."""
        root, parts = self._location(path)
        fd = os.open(root, DIRECTORY_FLAGS)
        current = root
        try:
            if not parts and not directory:
                raise IsADirectoryError(str(root))
            for i, part in enumerate(parts):
                is_directory = directory or i < len(parts) - 1
                flags = DIRECTORY_FLAGS if is_directory else FILE_FLAGS
                next_fd = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = next_fd
                current = current / part
            mode = os.fstat(fd).st_mode
            if directory and not stat.S_ISDIR(mode):
                raise NotADirectoryError(str(current))
            if not directory and not stat.S_ISREG(mode):
                raise AccessDenied("Only regular files can be opened")
            return fd, current
        except Exception:
            os.close(fd)
            raise

    def read_text(self, path: str | Path, expected_revision: str | None = None) -> TextSnapshot:
        """Read a stable bounded file once and verify its optional revision."""
        fd, actual_path = self._open(path)
        try:
            before = os.fstat(fd)
            if before.st_size > self.policy.max_file_bytes:
                raise FileLimitExceeded("File exceeds max_file_bytes")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                payload = stream.read(self.policy.max_file_bytes + 1)
            after = os.fstat(fd)
            if len(payload) > self.policy.max_file_bytes:
                raise FileLimitExceeded("File grew beyond max_file_bytes")
            signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            if signature(before) != signature(after) or len(payload) != after.st_size:
                raise FileChanged("File changed while being read")
        finally:
            os.close(fd)
        if b"\x00" in payload:
            raise UnsupportedText("Binary file contains NUL bytes")
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UnsupportedText("File is not valid UTF-8") from exc
        revision = "sha256:" + hashlib.sha256(payload).hexdigest()
        if expected_revision is not None and expected_revision != revision:
            raise FileChanged("File changed since the requested revision")
        return TextSnapshot(
            path=str(actual_path), revision=revision,
            size_bytes=len(payload), mtime_ns=after.st_mtime_ns,
            text=text, lines=tuple(text.splitlines(keepends=True)),
        )

    def list_directory(self, path: str | Path, limit: int = 100) -> dict:
        """List direct directory entries without reading their contents."""
        if not 1 <= limit <= 200:
            raise InvalidRange("limit must be between 1 and 200")
        fd, actual_path = self._open(path, directory=True)
        try:
            names = sorted(os.listdir(fd))
            entries = []
            for name in names:
                if name.startswith(".") or self._blocked((name,)):
                    continue
                try:
                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                except (FileNotFoundError, PermissionError):
                    continue
                if stat.S_ISDIR(info.st_mode):
                    kind = "directory"
                elif stat.S_ISREG(info.st_mode):
                    kind = "file"
                else:
                    continue
                entries.append({"name": name, "type": kind})
                if len(entries) > limit:
                    break
        finally:
            os.close(fd)
        return {
            "path": str(actual_path),
            "entries": entries[:limit],
            "truncated": len(entries) > limit,
        }


    def search_names(self, path: str | Path, query: str, limit: int = 40,
                     max_scanned: int = 2000) -> dict:
        """Search direct child names only; bound the number of directory entries inspected.

        No recursion and no file content reads. The results are not claimed exhaustive
        if either the directory scan or result cap is reached.
        """
        if not isinstance(query, str) or not 1 <= len(query) <= 128:
            raise InvalidRange("Search query must contain 1 to 128 characters")
        if any(c in query for c in ("/", "\\\\", "\\x00", "\\n", "\\r")):
            raise InvalidRange("Search query contains a forbidden character")
        if not isinstance(limit, int) or not 1 <= limit <= 60:
            raise InvalidRange("limit must be between 1 and 60")
        if not isinstance(max_scanned, int) or not 1 <= max_scanned <= 2000:
            raise InvalidRange("max_scanned must be between 1 and 2000")
        fd, actual_path = self._open(path, directory=True)
        try:
            matches = []
            inspected = 0
            scan_limited = False
            key = query.casefold()
            with os.scandir(fd) as entries:
                for entry in entries:
                    if inspected >= max_scanned:
                        scan_limited = True
                        break
                    inspected += 1
                    name = entry.name
                    if name.startswith(".") or self._blocked((name,)) or key not in name.casefold():
                        continue
                    try:
                        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    except (FileNotFoundError, PermissionError, OSError):
                        continue
                    if stat.S_ISDIR(info.st_mode):
                        kind = "directory"
                    elif stat.S_ISREG(info.st_mode):
                        kind = "file"
                    else:
                        continue
                    matches.append({"name": name, "type": kind})
            matches.sort(key=lambda item: item["name"].casefold())
            limited = len(matches) > limit
            return {
                "path": str(actual_path), "query": query,
                "entries": matches[:limit],
                "inspected_entries": inspected,
                "scan_limited": scan_limited,
                "truncated": limited or scan_limited,
            }
        finally:
            os.close(fd)

    def tail_text(self, path: str | Path, max_bytes: int = 4096,
                  max_lines: int = 80) -> dict:
        """Read only an explicitly bounded suffix, even for very large log files.

        Revision is a metadata fingerprint (not a full content hash); intended for
        viewing actively appended logs. No periodic polling or unrestricted scans.
        """
        if not isinstance(max_bytes, int) or not 256 <= max_bytes <= 8192:
            raise InvalidRange("max_bytes must be between 256 and 8192")
        if not isinstance(max_lines, int) or not 1 <= max_lines <= 150:
            raise InvalidRange("max_lines must be between 1 and 150")
        read_limit = min(max_bytes, max(256, self.policy.max_response_chars // 2))
        fd, actual_path = self._open(path)
        try:
            before = os.fstat(fd)
            size = before.st_size
            start = max(0, size - read_limit)
            payload = os.pread(fd, min(read_limit, size), start)
            after = os.fstat(fd)
            def signature(info):
                return (info.st_dev, info.st_ino, info.st_size,
                        info.st_mtime_ns, info.st_ctime_ns)
            if signature(before) != signature(after):
                raise FileChanged("Log file changed during suffix read")
        finally:
            os.close(fd)
        if b"\\x00" in payload:
            raise UnsupportedText("Binary data found in log suffix")
        trimmed = False
        if start:
            i = payload.find(b"\\n")
            if i >= 0 and i + 1 < len(payload):
                start += i + 1
                payload = payload[i + 1:]
                trimmed = True
            else:
                # The entire bounded window could be part of one very long line.
                trimmed = True
                for offset in range(min(4, len(payload))):
                    try:
                        payload[offset:].decode("utf-8")
                        start += offset
                        payload = payload[offset:]
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise UnsupportedText("Log suffix is not valid UTF-8")
        try:
            decoded = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UnsupportedText("Log suffix is not valid UTF-8") from exc
        lines = decoded.splitlines(keepends=True)
        if len(lines) > max_lines:
            lines = lines[-max_lines:]
            trimmed = True
        content = "".join(lines)
        metadata = (str(after.st_dev) + ":" + str(after.st_ino) + ":" +
                    str(after.st_size) + ":" + str(after.st_mtime_ns)).encode("ascii")
        return {
            "path": str(actual_path),
            "revision": "stat-sha256:" + hashlib.sha256(metadata).hexdigest(),
            "size_bytes": size,
            "mtime_ns": after.st_mtime_ns,
            "content": content,
            "display_lines": len(lines),
            "start_byte": start,
            "end_byte": size,
            "has_earlier": start > 0 or trimmed,
            "partial_window": trimmed,
        }

    @staticmethod
    def _log_metadata(info: os.stat_result) -> dict:
        """A metadata-only revision and stable file identity, no content scan."""
        identity = (str(info.st_dev) + ":" + str(info.st_ino)).encode("ascii")
        signature = (identity + b":" + str(info.st_size).encode("ascii") +
                     b":" + str(info.st_mtime_ns).encode("ascii") +
                     b":" + str(info.st_ctime_ns).encode("ascii"))
        return {
            "identity": hashlib.sha256(identity).hexdigest(),
            "revision": "stat-sha256:" + hashlib.sha256(signature).hexdigest(),
            "size_bytes": info.st_size,
            "mtime_ns": info.st_mtime_ns,
        }

    def log_status(self, path: str | Path) -> dict:
        """Stat one authorized regular file without reading any file contents."""
        fd, actual_path = self._open(path)
        try:
            info = os.fstat(fd)
            result = self._log_metadata(info)
        finally:
            os.close(fd)
        return {"path": str(actual_path), **result}

    def log_window(self, path: str | Path, *, direction: str = "tail",
                   offset: int = 0, max_bytes: int = 4096) -> dict:
        """Read a small UTF-8 byte window of a potentially huge regular file.

        The returned [start_byte,end_byte) boundaries are at UTF-8 character
        boundaries so consecutive before/after calls do not skip or duplicate
        bytes. No line counting, filesystem polling, or content hashing.
        """
        if direction not in ("tail", "before", "after"):
            raise InvalidRange("direction must be tail, before or after")
        if not isinstance(max_bytes, int) or not 256 <= max_bytes <= 8192:
            raise InvalidRange("max_bytes must be between 256 and 8192")
        if not isinstance(offset, int) or offset < 0:
            raise InvalidRange("offset must be a nonnegative byte offset")
        fd, actual_path = self._open(path)
        try:
            before = os.fstat(fd)
            size = before.st_size
            if direction != "tail" and offset > size:
                raise FileChanged("Log has been truncated since the previous request")
            if direction == "tail":
                low, high = max(0, size - max_bytes), size
            elif direction == "before":
                high = offset
                low = max(0, high - max_bytes)
            else:
                low = offset
                high = min(size, low + max_bytes)
            # For mid-file positions, align UTF-8 boundaries to the preceding
            # code point. The extra read is at most 3 bytes per endpoint.
            def boundary(value: int) -> int:
                if value <= 0 or value >= size:
                    return value
                prefix = os.pread(fd, 4, value)
                if not prefix or prefix[0] & 0xc0 != 0x80:
                    return value
                for previous in range(1, 4):
                    if value < previous:
                        break
                    byte = os.pread(fd, 1, value - previous)
                    if byte and byte[0] & 0xc0 != 0x80:
                        return value - previous
                raise UnsupportedText("UTF-8 character boundary cannot be found")

            low = boundary(low)
            high = boundary(high)
            payload = os.pread(fd, high - low, low)
            after = os.fstat(fd)
            identity = lambda v: (v.st_dev, v.st_ino, v.st_size, v.st_mtime_ns, v.st_ctime_ns)
            if identity(before) != identity(after) or len(payload) != high - low:
                raise FileChanged("Log changed during window read")
        finally:
            os.close(fd)
        if b"\\x00" in payload:
            raise UnsupportedText("Binary data found in log window")
        try:
            content = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UnsupportedText("Log window is not valid UTF-8") from exc
        return {
            "path": str(actual_path), **self._log_metadata(after),
            "direction": direction,
            "content": content,
            "start_byte": low, "end_byte": high,
            "has_earlier": low > 0, "has_later": high < size,
        }
