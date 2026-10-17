"""High-level bounded and revision-aware read-only text viewing APIs."""
from __future__ import annotations
from pathlib import Path
from .policy import ReadOnlyFileAccess, FilePolicy, FileChanged, InvalidRange
from .readers.markdown import headings

class FileViewer:
    """Provide directory, line-range, outline and section operations."""
    def __init__(self, policy: FilePolicy):
        """Initialize with explicit approved roots and limits."""
        self.access = ReadOnlyFileAccess(policy)

    def list_files(self, path: str, limit: int = 100) -> dict:
        """List permitted direct children of an approved directory."""
        return self.access.list_directory(path,limit)

    def search_names(self, path: str, query: str, limit: int = 40) -> dict:
        """Find bounded name matches among direct children only."""
        return self.access.search_names(path, query, limit=limit)

    def tail_text(self, path: str, max_bytes: int = 4096, max_lines: int = 80) -> dict:
        """Read a bounded suffix without loading the complete file."""
        return self.access.tail_text(path, max_bytes=max_bytes, max_lines=max_lines)

    def diagnose_log(self, path: str) -> dict:
        """Diagnose only a bounded suffix; do not read the full log."""
        from .log_diagnostics import analyze_suffix
        excerpt = self.access.log_window(path, direction="tail", max_bytes=8192)
        summary = analyze_suffix(
            excerpt["content"], start_byte=excerpt["start_byte"],
            end_byte=excerpt["end_byte"], file_size=excerpt["size_bytes"],
            revision=excerpt["revision"],
        )
        return {"path": excerpt["path"], **summary}

    def log_status(self, path: str) -> dict:
        return self.access.log_status(path)

    def log_window(self, path: str, direction: str = "tail", offset: int = 0,
                   max_bytes: int = 4096) -> dict:
        return self.access.log_window(path, direction=direction, offset=offset, max_bytes=max_bytes)

    def open_fast(self, path: str, *, max_initial_lines: int = 70,
                  max_content_chars: int = 4000, max_preview_headings: int = 30) -> dict:
        """Return first content, metadata and a bounded Markdown outline in one read.

        This intentionally avoids directory listing and multiple MCP round trips.
        Follow-up line and full-outline tools remain available.
        """
        import json
        from time import perf_counter

        started_at = perf_counter()
        snap = self.access.read_text(path)
        kind = "markdown" if snap.path.lower().endswith(".md") else "text"
        selected: list[str] = []
        used = 0
        for line in snap.lines[:max_initial_lines]:
            if len(line) > max_content_chars and not selected:
                raise InvalidRange("First line exceeds preview limit; use log window")
            if used + len(line) > max_content_chars:
                break
            selected.append(line)
            used += len(line)
        outline: list[dict] = []
        headings_truncated = False
        if kind == "markdown":
            try:
                items = headings(snap.lines, self.access.policy.max_headings)
                headings_truncated = len(items) > max_preview_headings
                outline = [
                    {"id": item.id, "title": item.title[:120],
                     "level": item.level, "start_line": item.start_line}
                    for item in items[:max_preview_headings]
                ]
            except ValueError:
                headings_truncated = True
        result = {
            "path": snap.path,
            "revision": snap.revision,
            "size_bytes": snap.size_bytes,
            "total_lines": snap.total_lines,
            "kind": kind,
            "content": "".join(selected),
            "start_line": 1,
            "next_line": 1 + len(selected),
            "has_more": len(selected) < snap.total_lines,
            "headings": outline,
            "headings_truncated": headings_truncated,
        }
        # Keep below the MCP response cap even for headings with long titles.
        # Reserve a small margin for server_elapsed_ms before budgeting payload.
        budget = self.access.policy.max_response_chars - 64
        while len(json.dumps(result, ensure_ascii=False, separators=(",", ":"))) > budget:
            if result["headings"]:
                result["headings"].pop()
                result["headings_truncated"] = True
            elif selected:
                selected.pop()
                result["content"] = "".join(selected)
                result["next_line"] = 1 + len(selected)
                result["has_more"] = len(selected) < snap.total_lines
            else:
                raise InvalidRange("Metadata exceeds the configured response cap")
        result["server_elapsed_ms"] = round((perf_counter() - started_at) * 1000, 3)
        return result

    def info(self, path: str) -> dict:
        """Return bounded text metadata and content revision."""
        snap=self.access.read_text(path)
        return dict(path=snap.path, revision=snap.revision, size_bytes=snap.size_bytes,total_lines=snap.total_lines)

    def read_text(self, path: str, start_line: int=1, max_lines: int=200, revision: str|None=None) -> dict:
        """Read a bounded range of complete lines from a consistent snapshot."""
        p=self.access.policy
        if start_line<1 or not 1<=max_lines<=p.max_lines:
            raise InvalidRange("Invalid line range")
        snap=self.access.read_text(path,revision)
        selected=[]
        used=0
        for line in snap.lines[start_line-1:start_line-1+max_lines]:
            if len(line)>p.max_response_chars:
                if not selected:
                    raise InvalidRange("One line exceeds response limit")
                break
            if used+len(line)>p.max_response_chars:break
            selected.append(line);used+=len(line)
        return dict(path=snap.path,revision=snap.revision,total_lines=snap.total_lines,start_line=start_line,
                    content="".join(selected),next_line=start_line+len(selected),has_more=start_line+len(selected)<=snap.total_lines)

    def outline(self, path: str) -> dict:
        """Extract a structured hierarchy of Markdown headings."""
        snap=self.access.read_text(path)
        items=headings(snap.lines,self.access.policy.max_headings)
        return dict(path=snap.path,revision=snap.revision,total_lines=snap.total_lines,
                    headings=[vars(item) for item in items])

    def read_section(self,path: str,section_id: str,revision: str,offset: int=0,max_chars:int=8000)->dict:
        """Return a stable chapter in bounded chunks with continuation metadata."""
        p=self.access.policy
        if offset<0 or max_chars<1:
            raise InvalidRange("Invalid character range")
        max_chars=min(max_chars,p.max_response_chars)
        snap=self.access.read_text(path,revision)
        items=headings(snap.lines,p.max_headings)
        if section_id=="document":
            first,last=1,snap.total_lines
        elif section_id=="preamble":
            first,last=1,(items[0].start_line-1 if items else snap.total_lines)
        else:
            section=next((item for item in items if item.id==section_id),None)
            if section is None:
                raise InvalidRange("Unknown section id")
            first,last=section.start_line,section.end_line
        contents="".join(snap.lines[first-1:last])
        if offset>len(contents):raise InvalidRange("Offset beyond section")
        end=min(len(contents),offset+max_chars)
        if end<len(contents):
            newline=contents.rfind("\n",offset,end)
            if newline>=offset:end=newline+1
        if end==offset and offset<len(contents):end=min(len(contents),offset+max_chars)
        return dict(path=snap.path,revision=snap.revision,section_id=section_id,start_line=first,end_line=last,
                    content=contents[offset:end],offset=offset,next_offset=end,has_more=end<len(contents))
