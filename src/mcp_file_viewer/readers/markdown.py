"""Dependency-free Markdown heading index for the Phase 1 baseline."""
from __future__ import annotations
from dataclasses import dataclass
import re

ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*)|[ \t]*)$")
SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
FENCE_CLOSE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")

@dataclass(frozen=True)
class Heading:
    """One structurally indexed section."""
    id: str
    title: str
    level: int
    start_line: int
    end_line: int
    parent_id: str | None


def headings(lines: tuple[str, ...], max_headings: int = 2000) -> list[Heading]:
    """Index ATX and Setext headings while skipping fenced and indented code."""
    raw: list[tuple[int,int,str]] = []
    fence: tuple[str,int] | None = None
    prev_line = ""
    prev_number = 0
    prev_eligible = False
    for number, original in enumerate(lines, 1):
        line = original.rstrip("\r\n")
        if fence:
            close = FENCE_CLOSE.match(line)
            if close and close.group(1)[0] == fence[0] and len(close.group(1)) >= fence[1]:
                fence = None
            prev_eligible = False
            continue
        opener = FENCE_OPEN.match(line)
        if opener and (opener.group(1)[0] != "`" or "`" not in opener.group(2)):
            fence = (opener.group(1)[0],len(opener.group(1)))
            prev_eligible = False
            continue
        if line.startswith(("    ","\t")):
            prev_eligible = False
            continue
        atx = ATX.match(line)
        if atx:
            title = re.sub(r"[ \t]+#+[ \t]*$", "", atx.group(2) or "").strip()
            raw.append((number,len(atx.group(1)),title))
            prev_eligible = False
        else:
            under = SETEXT.match(line)
            if under and prev_eligible:
                raw.append((prev_number,1 if under.group(1)[0]=="=" else 2,prev_line.strip()))
                prev_eligible = False
            else:
                prev_eligible = bool(line.strip()) and not line.lstrip().startswith((">","- ","* ","+ ","#","|","<"))
                prev_line = line
                prev_number = number
        if len(raw) > max_headings:
            raise ValueError("Heading count exceeds configured limit")
    result: list[Heading] = []
    stack: list[tuple[int,str]] = []
    for i,(line,level,title) in enumerate(raw):
        while stack and stack[-1][0]>=level:
            stack.pop()
        parent=stack[-1][1] if stack else None
        end=next((s-1 for s,l,_ in raw[i+1:] if l<=level),len(lines))
        item=Heading(f"h:{line}:{level}",title,level,line,end,parent)
        result.append(item)
        stack.append((level,item.id))
    return result
