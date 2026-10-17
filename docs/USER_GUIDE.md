# MCP File Manager — User Guide

This guide describes UI v15 in ChatGPT. File Manager accesses only paths allowed by its configured HPC-MCP connection. All screenshots, file names and example paths are illustrative.

## 1. Open the File Manager

After an administrator-free per-user HPC-MCP installation and connection refresh, ask ChatGPT to open a particular permitted file, for example:

> Open /path/to/authorized/work/INPUT.inp with MCP File Manager.

The file list and viewer appear as an MCP App when the ChatGPT host supports it. The registered UI is **v15**. Select a file to read its text, or navigate to another directory in the file browser. Opening a file is a read operation, not an edit.

If the UI does not appear, check that the plugin is connected, refresh the tools, reopen the resource, and confirm that the selected file resides within an authorized root. Ordinary MCP read tools remain usable without the UI.

## 2. Browse and read

- Browse the file tree and use the filename search to locate a file in the currently authorized directory.
- Open multiple tabs and switch between them.
- Source code and input files appear as text/code; Markdown documents can be read using their outline and preview.
- Text searching is available in the viewer; the editor provides its own search/replace controls.
- For large logs, use bounded viewing or the tail feature and manually refresh when required.

Large files are not loaded into the editor automatically. Bounded reads are deliberate to limit memory and shared-filesystem I/O.

## 3. Edit and save

Editing must be enabled in the HPC-MCP configuration. It applies only to **existing UTF-8 files no larger than 64 KiB**. If the controls are unavailable, verify write authorization, file ownership, size and metadata restrictions.

1. Open a file and choose **Edit**.
2. Type your changes. The UI displays an **Unsaved changes** marker.
3. Use **Diff** to compare the original contents with your edited buffer. This Diff is different from the Git commit-history comparison.
4. Choose **Save** (or press `Ctrl/Cmd+S`) to send the change to HPC-MCP.
5. Check the success notification and reopen the file if you want to verify the saved contents.

**Cancel** discards edits after the confirmation prompt. The UI also asks before navigating away from unsaved changes. **Undo** and **Redo** affect the in-browser editor buffer; they do not undo a previously completed save on the HPC filesystem.

### Vim mode

Select **Vim** in the keymap selector and then click **Edit**. Press `i` to enter INSERT mode and `Esc` for NORMAL mode. The editor implements common Vim keybindings and a `:w` mapping. Switch to **Standard** to use ordinary editor bindings.

## 4. Git history, Compare and Restore

Git operations work on a file already tracked and committed in a Git repository. A non-Git file can still be edited, but its History panel explains that no Git history is available.

1. Open a tracked text file and choose **History**.
2. Select **Compare** beside a commit to inspect the committed version against the current working file.
3. If restoration is desired, choose **Restore this commit** in the preview and confirm the warning.
4. The file is replaced with that committed version and the viewer reloads it.

The preview and restore operations verify committed content and the current working-file revision. If another process edits the file in the meantime, the requested restore is rejected rather than silently overwriting it.

**Important:** Save does not run `git add` or `git commit`. Git can only recover versions that were previously committed. Before relying on History as a rollback mechanism, maintain commits using your normal Git workflow. Restoration does not stage, commit, reset or push anything.

## 5. Common problems

| Symptom | Explanation / suggested action |
| --- | --- |
| Cannot access path | The file is outside configured roots or blocked by the access policy. Choose an approved path. |
| Edit or Save unavailable | Editing is disabled, the file is too large, non-UTF-8, not owner-writable, hard-linked or metadata-protected. |
| `file_changed` during Save | Someone or something modified the file after it was opened. Reopen and compare changes before retrying. |
| Empty History | The file is not Git tracked or no commit exists for it. Commit a version manually. |
| Restore rejected | The preview or current file revision changed. Reopen History and compare again. |
| Old UI appears | Refresh ChatGPT's connected tools and reopen UI v15 after the server restarts. |
| Operations feel slow | The main latency can include ChatGPT/MCP Tunnel round trips and shared filesystem I/O; local server-side processing may be much shorter. |

## 6. Current boundaries

The v0.1.0 release candidate is intended for reviewing and editing small text, source and input files in HPC environments. It does **not** currently transfer PC files, edit binaries, create new files, rename/move/delete files or launch a job. It is not a substitute for version control or an off-cluster backup.
