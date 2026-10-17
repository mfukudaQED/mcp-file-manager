# MCP File Manager: release-candidate verification

Date: 2026-10-18

## Scope

This release candidate covers browsing and editing small text files through ChatGPT MCP Apps. It does not promise binary transfer, mass file operations or an independent Web UI.

## Completed tests

- `npm run check` and `npm run build`: pass.
- Frontend Node tests: 6 pass.
- Python reader/editor/Git regressions: 33 pass.
- Real Git and Lustre temporary repository: history, committed preview, save, stale-save rejection, stale-restore rejection, legitimate restore and read-after-restore all pass.
- Running MCP service: history listing and committed file reading work.
- Filesystem blocker resolved in source: the virtual `lustre.lov` attribute is not treated as a user ACL; other xattrs, including `system.posix_acl_access`, remain blocked.
- The source-only live integration used a separate disposable Git worktree; no research files were changed.

## Remaining publication gates

1. Refresh/restart the user's existing HPC-MCP service so it loads the patched Python editor.
2. Call the live MCP `file_manager_edit_save` and `file_manager_git_restore` on a **disposable** Git file; confirm Save -> read -> Compare -> Restore -> read.
3. Open UI v15 in the ChatGPT host; verify Edit, Diff, Save, Cancel, Git History, Compare, Restore, stale conflict and Vim bindings by click/keyboard. Check browser and mobile only if claiming mobile support.
4. Review custom Lustre striping risk: inode replacement may change layout. Require source/control-only use and warn users not to edit custom-striped files.
5. Perform the final README/release metadata review and decide a public Git repository and version tag.

## Constraints

The MCP service is not automatically restarted or reconnected as part of this report. No tag or remote publish was performed.
