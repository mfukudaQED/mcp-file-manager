# MCP File Manager v0.2.0 — Release Notes

Release date: 2026-10-19

## Summary

v0.2.0 updates the independently installed Python package to ship the current **MCP Apps UI v21** and retain individually versioned UI resources v16–v20. Package version `0.2.0` and UI version `v21` are separate identifiers.

## Features

- Authorized browsing of remote HPC files, text/code views, Markdown preview, bounded reads and search.
- Opt-in CodeMirror text editing with SHA-256 revision checks, Unsaved Diff and Git commit-history comparison/restore.
- Copy-only controls for absolute Linux paths, registered Tabby profile URIs and WinSCP SFTP directory URIs. A manual-copy fallback is shown when the host blocks clipboard access.
- Compact inline SVG icons with mouse and keyboard tooltips.
- Explorer, Status/diagnostics and file-details sections start collapsed, with explicit controls to expand them.
- Dedicated `ui://mcp-file-manager/v21/app.html` resource, with earlier v16–v20 HTML bytes preserved for compatibility.

## Scope and safeguards

- Requires an existing authorized HPC-MCP server/connection; no separate HTTP listener or elevated privileges.
- Read-only mode is the default. Editing requires explicit HPC-MCP and File Manager opt-in.
- Experimental bounded transfer backend code is present but transfer registrations require separate opt-in. **Upload/Download controls are not available in UI v21**, and browser-host file transfer is not announced as supported.
- The UI does not commit, tag or push Git changes automatically.
- No Slurm, Intel oneAPI, or systemd configuration changes are part of this release.

## Verification

- Python regression and MCP resource tests: 61 passed. Frontend Node tests: 22 passed. TypeScript checks and the Vite single-file build passed.
- UI v21's collapsible file information was confirmed in ChatGPT by the user.
- Independent resource versioning preserves v16–v20.
- Browser-specific clipboard and external URI handler behavior depends on the ChatGPT host and local desktop software.
- A separate wheel-packaging attempt could not complete on sham: the existing HPC-MCP virtual environment lacks the required setuptools build backend. Source/package metadata and tests were verified; no wheel artifact is claimed.

## Deployment

Install or update in the **same Python environment as HPC-MCP**, then refresh its existing service and ChatGPT MCP connection under the user's permitted procedure.

For Git releases, apply the annotated `v0.2.0` tag to the package-version commit. `ui-v21` is a separate UI-version tag on the earlier UI implementation commit. Pushing the branch and release tag is performed manually by the repository owner over their configured SSH remote.
