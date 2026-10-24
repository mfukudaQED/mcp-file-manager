# MCP File Manager v0.3.0 — Release Notes

Release date: 2026-10-24

## Summary

This minor release ships **MCP Apps UI v23** with an improved View-mode
reading workflow. The first **1,000 lines** (or the full file if shorter)
are loaded automatically using bounded, revision-pinned MCP requests.
Additional content is loaded **only after clicking Load more**, not
when scrolling to the bottom. This behavior was tested in the ChatGPT
host and confirmed by the user.

The Python package version (`0.3.0`) and embedded UI version (`v23`)
are independent.

## Changes since v0.2.0

- Preload at least the first 1,000 lines when opening a text/source file
  or returning to an eligible file tab, without repeated button clicks.
- Retain the **Load more** button for explicit, bounded continuation.
  Disable scroll-triggered requests, which were inconvenient in ChatGPT's
  embedded viewer.
- Increase the server-side open-fast and line-read capacities while
  honoring response-size limits. The line reader accounts for serialized
  JSON escaping and metadata when enforcing the response budget.
- Preserve the viewer's scroll position when appending content, keep
  revision checks between pages, and prevent stale asynchronous reads
  from switching the active file.
- Retain safe rendering limits and switch overly large Markdown previews
  to Source view.
- Publish `ui://mcp-file-manager/v23/app.html` while preserving the
  existing v16–v22 UI resources as separate bundles. UI v22's
  scroll-loading experiment remains available as an older resource
  but is **not** the default.
- Refresh the README, user guide, installation instructions, and
  automated regression coverage.

## Verification

- **63/63 Python** regression tests passed, including bounded,
  revision-pinned reads and UI resource compatibility.
- **24/24 frontend Node** tests passed, including initial preload
  and the absence of scroll-triggered reading.
- TypeScript checks and Vite's single-file build passed.
- On sham, the MCP connection served a 1,309-line source file:
  initial reads reached line 1,093, then the next request returned
  lines 1,094–1,309 and correctly reached EOF.
- The user confirmed the button-only continuation works in ChatGPT.
  Host behavior and connection refresh requirements may vary by client.

## Compatibility, safeguards and deployment

- Existing v16–v22 UI bundle files are retained, without overwriting
  published versions. No modification to unrelated HPC-MCP, Slurm,
  Intel oneAPI, or systemd configuration is necessary.
- Filesystem access continues to use HPC-MCP's authorized roots;
  edit/transfer permissions remain opt-in. This release does **not**
  add browser Upload or Download buttons.
- Upgrade the package in the **same Python environment** as HPC-MCP,
  restart the existing per-user service through the host's established
  procedure, and refresh the ChatGPT connection's resources.
- Release tag: **`v0.3.0`** on the package-version commit. The GitHub
  Release page can use this document as its release notes.
