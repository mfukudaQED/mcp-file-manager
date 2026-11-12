# MCP File Manager — User Guide

This guide describes the **UI v29** file browser/editor inside ChatGPT MCP Apps. The Python package version is independent of the UI resource version. Operations are limited to paths authorized by your existing HPC-MCP connection.

## 1. Open a file or the File Browser

With the per-user HPC-MCP connection enabled, ask ChatGPT to open a permitted absolute file path with MCP File Manager, for example:

> Open /path/to/authorized/work/INPUT.inp with MCP File Manager.

The `file_viewer_open(path)` tool sends the path to the MCP App. The separate `file_manager_panel()` thread entrypoint can show an empty **HPC File Browser** panel in ChatGPT hosts that support it. The host decides whether an app opens inline, in a side tab, or fullscreen. UI v29 prefers a compact inline card; clicking Open requests fullscreen inside ChatGPT. The host can decline this request.

Plain filenames in arbitrary ChatGPT responses are not automatically clickable. ChatGPT-managed attachment/file-extension entrypoints do not grant access to arbitrary files on the HPC host.

If an old UI is shown after updating the package, restart **your existing** per-user HPC-MCP service using its normal administrator-free workflow, refresh the ChatGPT connection's tools/resources, and open a new File Manager UI. The new resource URI is `ui://mcp-file-manager/v29/app.html`; old v16–v28 resources remain addressable, with v24 preserving each host’s original bytes.

### Compact file launcher (UI v29)

In a chat, opening a file displays a compact card with its **filename**, server **sham/ohtaka**, file type and **開く** button. Press the button to request fullscreen **inside ChatGPT**, where the unchanged file viewer loads. Closing fullscreen returns to the compact card. On iPhone, the native **Open with HPC MCP** button may appear before the embedded app becomes visible; its text is controlled by ChatGPT and may not show the filename. The app's own card labels individual files. If the host does not support fullscreen, the card reports this instead of expanding inline.

### Read-only PNG/JPEG/GIF/WebP preview (UI v27)

Open an authorized absolute image file path or choose an image from File Explorer. The UI verifies its raster signature, assembles bounded revision-pinned chunks, and displays the result in a dedicated image pane. Click the image to toggle fitted/original size; use Reload to fetch changed images. Image tabs do not allow text search, editing, Git History, or Load more. SVG, PDF, TIFF, and remote Markdown images are not supported. The default file-size limit is 2 MiB, with an image-specific maximum of 4 MiB.

### Read-only PDF preview (UI v28)

Enter an authorized absolute path ending in `.pdf` or select the PDF from Explorer. The app renders the document offline using bundled PDF.js. Use **Previous**, **Next**, the page number field and **Go** to navigate; use **−**, **+**, and **Fit** to change zoom. **Text** extracts text from the current page for copying when available. Files remain read-only and PDF JavaScript/attachments/links are not executed. Existing default cap is 2 MiB (hard limit 8 MiB). Large, password-protected and damaged PDFs can be rejected. The page image is limited to four million pixels.

## 2. Layout and icons

The UI saves screen space by starting three regions collapsed:

- **File Explorer:** use the panel icon to show/hide the file tree and Markdown outline. Folder data is loaded on demand; choosing a file collapses Explorer automatically.
- **Status / diagnostics:** use the activity icon in the top-right header to show connection status, processing/latency measurements, and the connection benchmark.
- **File details:** use the information (ⓘ) icon in the file actions toolbar to show/hide the filename, full absolute path, file size, byte/line window and read/edit state.

Small SVG icons stand for common actions including Open (eye), Folder, Reload, log tail, search, Source/Preview, Edit (pencil), Save, Cancel, Unsaved Diff and Git History. **Move the pointer over an icon** or focus it using the keyboard to see its English tooltip, including when the action is disabled. The details displayed after expanding File details always correspond to the current file.

## 3. Browse, read and search

Enter an absolute path and choose Open (eye), or select files via Explorer. Source code, text files and input files use text/source rendering; Markdown can also use a rendered preview and outline. Tabs let you switch between up to five opened files. View mode automatically loads the first **1,000 lines** (or to end of file) through bounded requests. If more lines remain, click **Load more** for each subsequent portion; scrolling does **not** initiate any read. Viewer text search, bounded large-file reads, manual log-tail refresh and filename search are available without loading an entire large file into memory.

Changing files never writes to the remote filesystem unless you explicitly invoke an enabled save/restore operation.

**Math formulas in Markdown Preview (UI v28):** write inline TeX as `$\zeta$` and block equations between `$$` delimiter lines. The bundled KaTeX renderer produces native MathML; there are no CDN requests or remote fonts. Display equations are horizontally scrollable on narrow iPhone screens. Switch to Source to see or edit the original TeX.

## 4. Copy paths and desktop application URLs

The copy controls are **text-copy actions**, not launch or file-transfer operations:

| Control | Text copied | Intended desktop use |
| --- | --- | --- |
| **Path** (file-copy icon) | Selected absolute Linux path | Paste into a terminal or another program |
| **Tabby** (terminal icon) | `tabby://profile?profileName=...` | Use a **saved Tabby profile** matching the editable profile name (initially `sham` on sham, `ohtaka` on ohtaka) |
| **WinSCP** (folders icon) | `winscp-sftp://SITE/absolute/directory/` | Use a saved WinSCP site or host matching the editable name (initially `sham` on sham, `ohtaka` on ohtaka) |

WinSCP receives the **containing directory** when the selected path is an opened file, with a trailing slash to avoid triggering a file download. Values are encoded; credentials are never embedded. Confirm that the site/profile names match those installed locally.

ChatGPT or its embedded app sandbox can block custom URI launching and clipboard permissions. On Windows, a copied URI can be pasted into **Win+R** if the corresponding application is registered for that URI scheme. When the clipboard write is blocked, the UI shows a selected text field for manual **Ctrl+C** copying. It does not claim an automatic copy succeeded when the clipboard API reports failure. WinSCP URL scheme registration is performed in WinSCP itself, not by File Manager.

## 5. Edit and save

Editing must be explicitly enabled in the HPC-MCP configuration. It is restricted to **existing, owned, owner-writable UTF-8 regular files of at most 64 KiB**, subject to the filesystem metadata restrictions in the README.

1. Open the file, then choose the **Edit** pencil icon.
2. Change the text in CodeMirror; the UI indicates unsaved changes.
3. Inspect **Unsaved Diff**, which compares the edited buffer to its original content.
4. Choose **Save** (or `Ctrl/Cmd+S`) to request an atomic, SHA-256 revision-checked update.
5. Confirm the success status or reopen the file to inspect the saved result.

**Cancel** discards pending edits after a confirmation dialog. Undo/redo only change the in-browser editing buffer, not a completed filesystem save. Select **Vim** from the Keymap selector to use Vim editing controls (e.g. `i` for INSERT and `Esc` for NORMAL).

## 6. Git History and restore

On an already tracked and committed file:

1. Open **Git History**.
2. Choose **Compare** for a commit and review the diff with the current working copy.
3. Use **Restore this commit** only after reviewing the version and confirming the action.

Restoration changes the working file but not the Git commit history. Preview and restore are pinned to revisions to avoid overwriting unanticipated concurrent changes. **Save/Restore do not run `git add`, `git commit` or `git push`**. Manage commits separately if Git history is to serve as a recovery mechanism.

## 7. Common issues

| Symptom | Explanation / action |
| --- | --- |
| File access refused | Check the configured allowed roots and file permissions |
| Edit/Save disabled | Editing is not authorized or file size, ownership, format or metadata restrictions apply |
| `file_changed` | The on-disk revision changed; reopen before deciding what to save |
| Empty History | The file is not Git-tracked or has no commits |
| Older UI shown | Refresh the ChatGPT MCP connection after reloading the HPC-MCP service |
| Clipboard API denied | Use the selectable manual-copy field and `Ctrl+C` |
| Tabby/WinSCP link does not open from ChatGPT | Copy the URI and open it through the registered desktop URL handler |
| Operations seem slow | ChatGPT/MCP Tunnel latency and shared filesystem I/O can dominate local processing time |

## 8. Limits

The current UI does not offer Upload/Download buttons, binary editing, new-file creation, moving/renaming/deleting files, or job submission. An experimental transfer backend exists in the source but is **disabled by default**, and live host file transfer is not claimed as supported. The application is not a substitute for off-cluster backups. Changes to systemd, Slurm and compiler/MPI environment settings are outside File Manager's normal operation.

See [Installation](INSTALLATION.md), [copy-control details](COPY_ACTIONS_V19_JA.md), [SVG/Status behavior](SVG_STATUS_V20_JA.md), and [File details behavior](FILE_DETAILS_V21_JA.md).
