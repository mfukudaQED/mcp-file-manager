# MCP File Manager — Installation and Operations

## Overview

MCP File Manager is an optional Python extension of an already authenticated **HPC-MCP** process. It does not open a new HTTP listener, install a new SSH tunnel, require administrator privileges or modify scheduler/compiler configuration.

Requirements: Python 3.10+ in the same environment as HPC-MCP, an MCP Apps-capable ChatGPT connection, and Git for commit-history features. Node.js/npm are needed only when rebuilding the frontend.

## Install from source

From an authorized user-owned working directory:

~~~sh
/path/to/hpc-mcp/.venv/bin/python -m pip install -e /path/to/mcp-file-manager
~~~

Adjust both paths to your environment. For a non-editable installation, omit `-e`. Prebuilt MCP Apps HTML resources are packaged as `src/mcp_file_viewer/ui/*.html`. The current UI is **v21** (`app_v21.html`); `app.html` is the immutable legacy v16 bundle.

### Enable in HPC-MCP

Merge these values into your **existing private** `~/.config/hpc-mcp/config.toml` (avoid duplicate TOML tables):

~~~toml
[filesystem]
roots = ["/path/to/authorized/work"]

[permissions]
enable_writes = false

[extensions.file_manager]
enabled = true
enable_edit = false
~~~

This is the recommended **read-only** configuration. File Manager inherits the existing HPC-MCP filesystem roots; do not widen these roots merely for convenience.

To enable editing, explicitly opt in to both controls:

~~~toml
[permissions]
enable_writes = true

[extensions.file_manager]
enabled = true
enable_edit = true
~~~

These snippets represent *changes to the existing sections*, not additional duplicate sections. `permissions.enable_writes = true` may also enable other mutation tools subject to their own policies; review the entire HPC-MCP configuration first. The Git History extension invokes its own limited Git subprocess; it does not depend on adding `git` to the generic execute-command allowlist.

### Restart and reconnect

Restart **only the existing per-user service** through your site's permitted workflow, e.g. where a systemd user manager is already configured:

~~~sh
systemctl --user restart hpc-mcp-tunnel.service
systemctl --user is-active hpc-mcp-tunnel.service
~~~

For cron-managed deployments, use the existing HPC-MCP-provided user-level watchdog operations rather than altering unrelated crontab entries. Do not assume the MCP generic command allowlist permits `systemctl`; use an authorized user terminal if it does not.

Refresh or reconnect the ChatGPT plugin's tools/resources, then open a file using `file_viewer_open(path)`. The current resource is:

~~~text
ui://mcp-file-manager/v21/app.html
~~~

Legacy v16–v20 resources are **separately registered and unchanged**. The compatibility URIs older than v16 use the original `app.html` bundle; they are not aliases to the newest version.

The independent `file_manager_panel()` thread entrypoint opens an empty file-browser pane in hosts supporting it. The main file-opening tool and panel tool share the current v21 resource. ChatGPT controls final display placement.

## Verify the installation

Use a disposable file **under an authorized user-owned directory**; avoid production research files for restore tests.

1. Open a file and check Explorer, text/Markdown and File details (ⓘ); both Explorer and file details start collapsed.
2. Check SVG icon tooltips with the pointer or keyboard, plus Status/diagnostics (activity icon).
3. Check Path, Tabby and WinSCP copy controls. If clipboard permission is denied, verify the manual `Ctrl+C` fallback.
4. If edit access is enabled, test Edit → Unsaved Diff → Save → Reload, and stale-revision rejection.
5. On a disposable tracked Git file, test Git History → Compare → Restore, including a stale-file conflict. Test Vim mode if required.

The UI has **no Download/Upload controls**. The separately opt-in transfer prototype is disabled by default. Backend tests alone are not evidence that browser-host file saving or upload works.

## Rebuild the UI (developers)

Run in the project checkout, without using shared cluster `/tmp`:

~~~sh
cd frontend
npm ci
npm run check
node --test test/*.test.mjs
npm run build
cp dist/index.html ../src/mcp_file_viewer/ui/app_v21.html
~~~

The current frontend package has no `npm test` script, so invoke Node's built-in test runner directly. Rebuilding v21 is allowed as long as its resource contract is unchanged. **Never overwrite `src/mcp_file_viewer/ui/app.html` or a published older `app_vNN.html` bundle**. For a future changed UI, choose a new vNN URI and new HTML filename together in `src/mcp_file_viewer/extension.py`, and extend compatibility tests. Refresh the server after deployment.

Python integration tests require the MCP Python SDK and pytest in the test environment:

~~~sh
mkdir -p .test-run
/path/to/hpc-mcp/.venv/bin/python -m pytest -q tests/ --basetemp=.test-run/pytest
~~~

### Release and Git checks

On a shared HPC login node, use the repository-local \`.test-run/pytest\` base for pytest
temporary fixtures instead of the shared system \`/tmp\`. This directory is
Git-ignored and can be cleaned after a successful test run.

Before creating a public commit:

- Review staged changes for credentials, local configuration, machine-specific internal reports and personal email addresses.
- Run the Python suite, frontend TypeScript/Node tests, build and `git diff --cached --check`.
- Verify all legacy `app*.html` resource hashes remain unchanged when creating a new UI version.
- Use your approved Git identity (e.g. a GitHub noreply email), and perform commit, tag and push only as separate explicit actions.

## Security and boundaries

Only configured roots are accessible under the current unprivileged Linux account. Editing is limited to existing owner-writable UTF-8 files up to 64 KiB, revision-checked atomic replacement and policy checks. ACLs, hardlinks and unexpected extended attributes may block editing; replacing inodes can change Lustre stripe layout. Git History covers committed revisions, not automatic backups. Upload/download, new-file creation, rename/move/delete and an independent HTTP gateway are not supported by the v21 UI.

See [User Guide](USER_GUIDE.md) and the [historical v0.1.0 release-candidate verification](RELEASE_CANDIDATE_2026-10-18.md).
