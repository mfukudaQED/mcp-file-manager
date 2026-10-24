# MCP File Manager

MCP File Manager is a lightweight file browser and text editor for remote HPC systems, embedded in ChatGPT with **MCP Apps**. It is an optional extension to an existing per-user [HPC-MCP](https://github.com/mfukudaQED/hpc-mcp) server; it does **not** require another HTTP server, a new SSH tunnel, or administrator privileges.

**Version:** package `0.3.0`; current MCP Apps UI **v23** (deploy with a service restart and connector refresh). Package and UI version numbers are independent. See the [v0.3.0 release notes](docs/RELEASE_NOTES_V0.3.0.md) for changes and verification; the [v0.2.0 release notes](docs/RELEASE_NOTES_V0.2.0.md) describe the preceding release.

## Features

- Browse files and directories within an explicitly authorized filesystem root.
- View text, source code, calculation input and Markdown documents; preview Markdown headings and rendered content.
- Search within text files, navigate tabs and load bounded portions of large log files.
- In **View** mode, automatically read the first **1,000 lines** (or to EOF). To read beyond that, click **Load more**; scrolling never starts another read. Each page is revision-pinned and bounded.
- Edit existing small UTF-8 files with **CodeMirror 6**, syntax highlighting, search/replace, undo/redo and optional Vim keybindings.
- Review unsaved changes with **Diff**, then save explicitly with SHA-256 revision checks.
- Compare a tracked file with its Git commit history and restore a selected committed version after confirmation.
- Copy an absolute Linux path, a saved **Tabby** profile URI, or a **WinSCP SFTP** directory URI. These actions copy text; they do not launch desktop applications from ChatGPT.
- Use compact SVG icon controls with mouse/keyboard tooltips. The Explorer, Status/diagnostics and file-details header start collapsed.
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

4. Ask ChatGPT: **“Open `/path/to/authorized/work/README.md` with MCP File Manager.”** The current source targets UI v23 and retains separate unchanged v16/v17/v18/v19/v20/v21/v22 resources. UI v21 additionally collapses the file title, full path and metadata by default; open them through the File details (info) icon. Copy actions, SVG icon tooltips and the collapsed Status/diagnostics panel are retained. UI v23 keeps the initial 1,000-line preloading but restores button-only continuation in View mode. Download/Upload buttons remain removed.

For a complete walkthrough, see **[User Guide](docs/USER_GUIDE.md)**. For source installation, frontend rebuilding and troubleshooting, see **[Installation](docs/INSTALLATION.md)**.

## Open in a conversation side panel

MCP File Manager advertises an OpenAI **thread entrypoint** on the
`file_manager_panel` tool. In hosts that support conversation panels, this lets
you open the app beside the current chat, even before choosing a file.

From the chat, ask ChatGPT to **open an authorized absolute path with MCP
File Manager** (for example,
`/path/to/authorized/work/README.md`). The existing `file_viewer_open`
tool sends that file path to the UI, which opens the selected file.

**Important platform limitation:** MCP tools cannot make arbitrary plain
filename text (`README.md`) in every existing ChatGPT answer into a native
click target. A reply can instead contain a specifically authored action
link/control that sends an open-file request with the correct absolute path.
The ChatGPT host controls whether a newly invoked app appears inline, in the
conversation panel, or in another supported display surface. We do not
register a generic file-extension handler: those handlers receive
host-owned file resources, not paths to files on a remote HPC cluster.

The UI resource declares `preferredDisplayMode: "fullscreen"` and keeps
`inline` available. ChatGPT can honor the preference on initial render,
but the host may still show the inline app. In that case, select **Open app
in tab** on the rendered app to move it into the right-hand tab.

## Layout, tooltips and local clipboard actions

The **File Explorer** starts collapsed so the viewer/editor uses the full width.
Use the panel icon to show or hide the file tree and Markdown outline; selecting a
file returns to the full-width viewer. Folder listings are fetched on demand.

The **Status/diagnostics** panel and the **file details** header (name, absolute
path, size and read-range metadata) also start collapsed. Open either with its
icon in the toolbar. Hover over an SVG icon, or focus it with the keyboard, to
read its function.

The Path, Tabby and WinSCP copy buttons prepare text for use **on your own
computer**. Tabby uses a saved profile name; WinSCP uses a saved site or host
and targets the currently selected file's parent directory. Some ChatGPT hosts
deny clipboard access: in that case the UI displays selectable text for manual
copying. Windows `Win+R` can open a registered application URI after pasting.
A `tabby://` link **inside** ChatGPT may be blocked; no direct-app launch is
promised. See the [User Guide](docs/USER_GUIDE.md) for details.

## Typical editing workflow

Open a file, choose **Edit**, make changes, select **Diff** to review them, then **Save**. **Cancel** discards unsaved edits after confirmation. The editor can use standard shortcuts (`Ctrl/Cmd+S`) or Vim mode.

For a file already tracked by Git, open **Git History**, choose a commit's **Compare** action, review the full diff, then choose **Restore this commit** if needed. Restoration modifies the working file, **not** Git history, and is guarded by the file revision you previewed.

## Security and limits

- Edits are limited to **existing, owned, owner-writable regular UTF-8 files of at most 64 KiB**. Large files can still be viewed in bounded sections.
- Symlink traversal outside authorized roots, edits to hard-linked files, ACL-bearing files and files with non-Lustre extended attributes are rejected.
- Lustre's virtual `lustre.lov` attribute is permitted. However, atomic inode replacement **can change a file's Lustre striping/layout**, so avoid the editor for files requiring a custom layout.
- Every save checks the original SHA-256 revision and uses atomic replacement. It cannot eliminate every race with an *uncooperative concurrent writer* on a shared filesystem.
- Git history works only for files already tracked and committed. Restoring a commit does not automatically back up uncommitted changes. Diff/History and editing are limited to small text files.
- Upload/download UI controls, creating files, moving/renaming/deleting files, binary editing, independent web hosting and PQViewer integration are **not included** in this release. Experimental transfer code is separate, disabled by default and not a user-ready file-transfer feature.
- The old `.mcp-file-manager-backups` folders, if any, are not automatically used or deleted.

## Transfer prototype (disabled)

The source contains an experimental bounded binary-transfer backend with
separate opt-in download/upload registrations. Both remain disabled by
default; **UI v23 does not expose Upload or Download**. Do not treat the
presence of backend tests as a supported host-level transfer workflow.
Enabling transfers needs a separate explicit configuration/security review.

The v18 Tabby deep-link experiment was superseded by v19's copy-only
controls, and v20–v22 retain those controls. See
[copy operations](docs/COPY_ACTIONS_V19_JA.md),
[SVG controls and diagnostics](docs/SVG_STATUS_V20_JA.md), and
[collapsible file details](docs/FILE_DETAILS_V21_JA.md).

## Development and tests

```sh
python3 -m pip install -e .
mkdir -p .test-run
python3 -m pytest -q tests/ --basetemp=.test-run/pytest

cd frontend
npm ci
npm run check
npm run build
cp dist/index.html ../src/mcp_file_viewer/ui/app_v23.html
```

When releasing a **new UI version**, change the resource URI and HTML
filename together. Never overwrite `ui/app.html` (the immutable v16 bundle)
or any prior `app_v*.html`. Run frontend Node tests as well as the Python
suite before committing.

The Python integration tests require the MCP Python SDK in the test environment
(as installed in HPC-MCP). The standalone core is usable without its UI/host adapter. Consult [Installation](docs/INSTALLATION.md) for host setup and deployment checks.

**License:** MIT. See [LICENSE](LICENSE).
