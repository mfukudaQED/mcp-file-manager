"""Conservative diagnostics from a small, already bounded log excerpt.

Never infer job success, global absence of errors or elapsed time from missing
markers. Only claim the presence of explicit markers within the scanned suffix.
"""

from __future__ import annotations

import re

MAX_EVIDENCE = 8
MAX_EVIDENCE_CHARS = 220

_FAILURE = (
    re.compile(r"\bSCF\s+(?:run\s+)?(?:NOT\s+converged|failed|did\s+not\s+converge)\b", re.I),
    re.compile(r"\bconvergence\s+(?:has\s+)?NOT\s+(?:been\s+)?achieved\b", re.I),
    re.compile(r"\bSCF\s+convergence\s+NOT\s+achieved\b", re.I),
    re.compile(r"\b(?:too\s+many\s+SCF\s+iterations|SCF\s+iterations\s+exceeded)\b", re.I),
    re.compile(r"\bmaximum\s+number\s+of\s+SCF\s+iterations\b", re.I),
)
_SUCCESS = (
    re.compile(r"\bSCF\s+(?:run\s+)?converged(?:\s+in\b)?", re.I),
    re.compile(r"\bconvergence\s+has\s+been\s+achieved\b", re.I),
    re.compile(r"\bSCF\s+convergence\s+(?:achieved|reached|criterion\s+satisfied)\b", re.I),
    re.compile(r"\baborting\s+loop\s+because\s+EDIFF\s+is\s+reached\b", re.I),
)
_ERROR = (
    re.compile(r"^\s*(?:\*{1,3}\s*)?(?:FATAL(?:\s+ERROR)?|ERROR|ABORT(?:ED)?|EXCEPTION)\s*[:!*\s]", re.I),
    re.compile(r"^\s*(?:Traceback \(most recent call last\):|slurmstepd: error:)", re.I),
    re.compile(r"\b(?:MPI_Abort|segmentation fault|SIGSEGV|out of memory|oom[- ]kill(?:ed)?)\b", re.I),
    re.compile(r"\b(?:PROGRAM STOPPED IN|APPLICATION TERMINATED WITH THE EXIT STRING)\b", re.I),
)
_WARNING = (
    re.compile(r"^\s*(?:\*{1,3}\s*)?WARN(?:ING)?\s*[:!*\s]", re.I),
    re.compile(r"^\s*WARNING\b", re.I),
)
_TIMING = (
    re.compile(r"^\s*(?:CP2K\|\s*)?Total\s+(?:wall\s+)?time\s*(?:\[s\])?\s*[:= ]", re.I),
    re.compile(r"^\s*(?:Total\s+CPU\s+time\s+used|Elapsed\s+\(wall\s+clock\)\s+time|WALLTIME)\s*[:= ]", re.I),
    re.compile(r"^\s*Total\s+time\s*[:=]\s*[0-9]", re.I),
)

def _category(line: str) -> str | None:
    if any(p.search(line) for p in _FAILURE):
        return "scf_not_converged"
    if any(p.search(line) for p in _SUCCESS):
        return "scf_converged"
    if any(p.search(line) for p in _ERROR):
        return "error"
    if any(p.search(line) for p in _WARNING):
        return "warning"
    if any(p.search(line) for p in _TIMING):
        return "timing"
    return None

def analyze_suffix(content: str, *, start_byte: int, end_byte: int,
                   file_size: int, revision: str) -> dict:
    """Extract bounded evidence from a UTF-8 suffix of one log snapshot."""
    if not isinstance(content, str) or len(content.encode("utf-8")) > 8300:
        raise ValueError("Diagnostic input must be a bounded UTF-8 suffix")
    if not (0 <= start_byte <= end_byte <= file_size):
        raise ValueError("Invalid diagnostic byte range")
    lines = content.splitlines()
    skipped_prefix = bool(start_byte > 0)
    if skipped_prefix and lines:
        # The first line may be only a suffix of a larger line.
        lines = lines[1:]
    counts = {"scf_converged": 0, "scf_not_converged": 0, "error": 0,
              "warning": 0, "timing": 0}
    latest_scf: tuple[str, str] | None = None
    evidence: list[dict] = []
    for line in lines:
        kind = _category(line)
        if kind is None:
            continue
        counts[kind] += 1
        if kind == "scf_not_converged" and any(pattern.search(line) for pattern in _ERROR):
            counts["error"] += 1
        clean = line.strip().replace("\t", " ")
        if kind.startswith("scf_"):
            latest_scf = (kind, clean[:MAX_EVIDENCE_CHARS])
        evidence.append({"kind": kind, "text": clean[:MAX_EVIDENCE_CHARS]})
    # Choose the most recent entries, but keep at least the latest SCF
    # evidence in a separate field when other warnings dominate the tail.
    scf_status = ({
        "scf_converged": "converged",
        "scf_not_converged": "not_converged",
    }.get(latest_scf[0]) if latest_scf else "unknown")
    return {
        "scope": "tail_excerpt_only",
        "scf_status": scf_status,
        "scf_evidence": latest_scf[1] if latest_scf else None,
        "counts_in_excerpt": counts,
        "evidence": evidence[-MAX_EVIDENCE:],
        "start_byte": start_byte,
        "end_byte": end_byte,
        "file_size": file_size,
        "revision": revision,
        "partial_log": bool(start_byte > 0 or end_byte < file_size),
        "skipped_partial_first_line": skipped_prefix,
        "interpretation": "Indicators only; no claim of full-log coverage or job success.",
    }
