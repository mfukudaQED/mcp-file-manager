# MCP File Manager

MCP File Manager is a lightweight file browser and text editor for remote HPC systems, embedded in ChatGPT with **MCP Apps**. It is an optional extension to an existing per-user [HPC-MCP](https://github.com/mfukudaQED/hpc-mcp) server; it does **not** require another HTTP server, a new SSH tunnel, or administrator privileges.

**Release status:** v0.1.0 candidate (2026-10-18). The core functions have passed automated and live-MCP tests, and the UI v15 workflow was user-tested in ChatGPT. See [release verification](docs/RELEASE_CANDIDATE_2026-10-18.md). No public push or GitHub release has been performed.

## Features

- Browse files and directories within an explicitly authorized filesystem root.
- View text, source code, calculation input and Markdown documents; preview Markdown headings and rendered content.
- Search within text files, navigate tabs and load bounded portions of large log files.
- Edit existing small UTF-8 files with **CodeMirror 6**, syntax highlighting, search/replace, undo/redo and optional Vim keybindings.
- Review unsaved changes with **Diff**, then save explicitly with SHA-256 revision checks.
- Compare a tracked file with its Git commit history and restore a selected committed version after confirmation.
- Use the existing authenticated HPC-MCP connection from ChatGPT; file access remains constrained by the server's allowed roots.

**No automatic Git commit or backup is created when saving.** To make changes recoverable through History, commit the file yourself using Git.

## Quick start

Prerequisites: an operating per-user HPC-MCP server with a ChatGPT MCP Apps connection, Python **3.10+**, and Git for the optional history feature. The frontend is prebuilt in the Python package; **Node.js is only required for rebuilding it**.

1. Install this package in the *same Python environment* used to run HPC-MCP:

   ```sh
   /path/to/hpc-mcp/.venv/bin/python -m pip install -e /path/to/mcp-file-manager
   ```

2. In `~/.config/hpc-mcp/config.toml`, use an authorized filesystem root and enable the extension:

   ```toml
   [filesystem]
   roots = ["/path/to/authorized/work"]

   [extensions.file_manager]
   enabled = true
   enable_edit = false

   [permissions]
   enable_writes = false
   ```

   This is **read-only mode**, the recommended default. For editing, set **both** `permissions.enable_writes = true` and `extensions.file_manager.enable_edit = true` only after reviewing the write access permitted by HPC-MCP. The filesystem roots also constrain other HPC-MCP tools; use narrow roots appropriate for your account. Editing remains opt-in for the entire configured root set, not a separate File Manager-only edit-root list.

3. Restart your **existing per-user HPC-MCP service or Tunnel**, using its configured systemd-user or cron watchdog backend. In ChatGPT, refresh the connected plugin's tools/resources.

4. Ask ChatGPT: **“Open `/path/to/authorized/work/README.md` with MCP File Manager.”** The current UI resource is `ui://mcp-file-manager/v15/app.html`.

For a complete walkthrough, see **[User Guide](docs/USER_GUIDE.md)**. For source installation, frontend rebuilding and troubleshooting, see **[Installation](docs/INSTALLATION.md)**.

## Typical editing workflow

Open a file, choose **Edit**, make changes, select **Diff** to review them, then **Save**. **Cancel** discards unsaved edits after confirmation. The editor can use standard shortcuts (`Ctrl/Cmd+S`) or Vim mode.

For a file already tracked by Git, open **History**, choose a commit's **Compare** action, review the full diff, then choose **Restore this commit** if needed. Restoration modifies the working file, **not** Git history, and is guarded by the file revision you previewed.

## Security and limits

- Edits are limited to **existing, owned, owner-writable regular UTF-8 files of at most 64 KiB**. Large files can still be viewed in bounded sections.
- Symlink traversal outside authorized roots, edits to hard-linked files, ACL-bearing files and files with non-Lustre extended attributes are rejected.
- Lustre's virtual `lustre.lov` attribute is permitted. However, atomic inode replacement **can change a file's Lustre striping/layout**, so avoid the editor for files requiring a custom layout.
- Every save checks the original SHA-256 revision and uses atomic replacement. It cannot eliminate every race with an *uncooperative concurrent writer* on a shared filesystem.
- Git history works only for files already tracked and committed. Restoring a commit does not automatically back up uncommitted changes. Diff/History and editing are limited to small text files.
- Upload/download, creating files, moving/renaming/deleting files, binary editing, independent web hosting and PQViewer integration are **not included** in v0.1.0.
- The old `.mcp-file-manager-backups` folders, if any, are not automatically used or deleted.

## Development and tests

```sh
python3 -m pip install -e .
python3 -m pytest -q tests/

cd frontend
npm ci
npm run check
npm run build
cp dist/index.html ../src/mcp_file_viewer/ui/app.html
```

The Python integration tests require the MCP Python SDK in the test environment (as installed in HPC-MCP). The standalone core is usable without its UI/host adapter. Consult [Installation](docs/INSTALLATION.md) for host setup and deployment checks.

**License:** not yet selected. Review and add a license before publication to GitHub. Do not assume an open-source grant until a license is specified.
