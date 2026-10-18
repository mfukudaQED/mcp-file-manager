# MCP File Manager — Installation and Operations

## Overview

MCP File Manager is a Python package loaded as an optional extension of an existing **HPC-MCP** process. That process is the trusted boundary for roots, authentication and tool calls. File Manager does not start a separate server or publicly accessible listener.

Requirements:

- Python 3.10+ in the same environment as HPC-MCP
- Existing per-user HPC-MCP deployment and a connected MCP Apps-capable ChatGPT host
- Git available on the host for commit-history features
- Node.js/npm **only if rebuilding** the packaged UI

Installation must be performed under the ordinary HPC user account; administrator privileges are not needed.

## Install from source

Clone or copy this package to a working directory, then install it into the HPC-MCP interpreter:

```sh
/path/to/hpc-mcp/.venv/bin/python -m pip install -e /path/to/mcp-file-manager
```

Replace both example paths with your actual locations. For a non-editable package installation, omit `-e`. A prebuilt single-file UI is included in `src/mcp_file_viewer/ui/app.html` as package data.

### Enable in HPC-MCP

Edit the existing private `~/.config/hpc-mcp/config.toml`. The relevant configuration keys are:

```toml
[filesystem]
roots = ["/path/to/authorized/work"]

[permissions]
enable_writes = false

[extensions.file_manager]
enabled = true
enable_edit = false
```

This enables read-only browsing. To use the CodeMirror editor, explicitly opt in to the HPC-MCP write capability **and** File Manager's edit capability:

```toml
[permissions]
enable_writes = true

[extensions.file_manager]
enabled = true
enable_edit = true
```

Merge the snippets into their existing TOML sections; **do not duplicate a TOML table**. The configured `[filesystem].roots` apply across HPC-MCP, so keep them as narrow as appropriate. `enable_writes=true` may also permit other HPC-MCP mutation tools under their respective policies. Review the complete HPC-MCP configuration before enabling editing.

No `git` command needs to be permitted through the generic `execute_command` allowlist for the Git history extension to read/restore tracked files: the File Manager backend invokes a limited Git subprocess independently.

### Restart and reconnect

Use whichever existing backend manages your per-user HPC-MCP Tunnel:

- **systemd user service:** restart the relevant user service with `systemctl --user restart hpc-mcp-tunnel.service` when the user manager is available.
- **cron watchdog:** use the HPC-MCP-provided `deploy/cron_watchdog.py stop` and `start` actions from an authorized user shell; these affect the user-owned Tunnel only. Do not modify unrelated crontab entries.

Reopening ChatGPT after the host reconnects may be necessary. Refresh the connected plugin tools and open the current UI URI:

```text
ui://mcp-file-manager/v16/app.html
```

The compatibility aliases for older UI URIs exist for legacy clients but load the current bundled application. Prefer v16.

### Conversation-panel integration

The `file_manager_panel` tool declares
`_meta["openai/ui"]["entrypoints"] = [{"type": "thread"}]` in addition to
the standard MCP Apps UI resource. The panel tool has no arguments. The separate `file_viewer_open(path)` tool
continues to open specific remote files as an inline MCP App; the user may also
navigate to a file inside the conversation panel. Refresh the MCP plugin after restarting the
server for the new entrypoint to be discovered.

This enables the **thread panel where the host supports it**, not universal
interception of Markdown links or filename text in messages. Display and
focus behavior are controlled by the ChatGPT host.

## Test the installation

Before opening production project files, create a small, disposable test file **within an authorized root**. Ask ChatGPT to open it with MCP File Manager. Check:

1. File listing, text and Markdown rendering
2. Editor Edit -> Diff -> Save -> Reload
3. Stale-revision rejection after a concurrent test change
4. For a Git-committed test file: History -> Compare -> Restore
5. In Vim mode: enter INSERT, edit and return to NORMAL

Do not use research input files for destructive restore testing.

## Rebuild the UI (developers only)

```sh
cd frontend
npm ci
npm run check
npm run build
cp dist/index.html ../src/mcp_file_viewer/ui/app.html
```

Restart the service and refresh the connected UI resource after changing the packaged HTML. If changing the UI protocol/asset, bump its resource version in `src/mcp_file_viewer/extension.py` to avoid a host cache retaining old content.

For the Python test suite, install pytest and the MCP Python SDK in the testing interpreter:

```sh
python3 -m pytest -q tests
```

Some integration tests import the MCP SDK; if it is missing, use the environment that runs HPC-MCP.

## Security and limitations

- Only explicit roots are available; no escalation beyond the current Linux user.
- Small UTF-8 regular files only for editing, with 64 KiB maximum, ownership checks, stale-revision protection and atomic replacement.
- Files with POSIX ACLs or user/system xattrs other than Lustre's virtual `lustre.lov` are rejected. Atomic replacement can change Lustre stripe settings on edited files.
- Git History is limited to 20 commits and committed file previews to 64 KiB; it is not an automatic backup.
- Upload/download, new-file creation, rename/move/delete and a standalone HTTP gateway are not yet supported.
- The project is distributed under the MIT License; see [LICENSE](../LICENSE).

See [User Guide](USER_GUIDE.md) for UI instructions and the [release-candidate verification history](RELEASE_CANDIDATE_2026-10-18.md) for the earlier test record.
