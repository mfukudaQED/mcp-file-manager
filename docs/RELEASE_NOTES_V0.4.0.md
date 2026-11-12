# MCP File Manager v0.4.0 — Release Notes

Release date: 2026-11-12

Python package: **0.4.0** · Default MCP Apps UI: **v29**

## Summary

This minor release unifies the sham and ohtaka implementations and adds **compact file launch cards**, **offline PDF viewing**, **raster image viewing**, and **offline Markdown math rendering**. The MCP App remains a user-owned extension of HPC-MCP, without a separate HTTP service.

## Highlights

- **UI v29: compact launcher.** In ChatGPT inline mode, each file has a filename, host label, file type, and **Open** control. A user click requests `fullscreen` through the MCP Apps display-mode API. On closing fullscreen, the compact card returns where the host supports this transition.
- **iPhone experience.** A single `file_viewer_open(path)` call opens one requested file. The ChatGPT-native launch button's wording is host-controlled; the filename appears in the app's own card when it is rendered.
- **UI v28: offline PDF preview.** Bundled PDF.js supports multipage navigation, direct page selection, zoom, fit-to-width, and current-page text extraction. PDF content is retrieved using revision-pinned bounded chunks. No CDN or PDF JavaScript execution.
- **UI v27: image preview.** Read-only PNG/JPEG/GIF/WebP viewing with fit/original-size switching and bounded revision-pinned transfer.
- **Markdown & math.** Embedded KaTeX and native MathML for inline and display TeX, with mobile-friendly overflow handling.
- **Unified source.** Identical UI templates for sham and ohtaka. Host-specific Tabby and WinSCP profile names are selected safely when serving the resource.
- **Existing features retained.** CodeMirror editor with explicit write authorization, unsaved Diff, Git History, syntax highlighting, filename search, bounded logs, and automatically loading the first 1,000 text lines. Further reads use **Load more** only (no scroll-triggered load).

## Compatibility

- Current UI URI: `ui://mcp-file-manager/v29/app.html`.
- Older MCP Apps resources, including the original v24 variants and unchanged v27/v28 preview resources, remain available.
- The Python package version and embedded UI version are independent.
- Upgrade in the **same Python environment** as HPC-MCP; restart only the existing user-owned connection and refresh ChatGPT's connected app resources. No changes to Slurm, Intel oneAPI, host firewall, or system-wide settings.
- Paths remain restricted to the existing HPC-MCP authorized roots. File edits require explicit opt-in; transfer permissions are unchanged.

## Verification

- **sham:** 80 Python regression tests passed. TypeScript check, compact-launch test, offline math, raster image, PDF tests, and single-file Vite build passed.
- **ohtaka:** 72 Python tests passed, one skipped. Three stdio test files requiring unavailable SDK dependencies were excluded. The v29 HTML bundle matched sham byte-for-byte.
- **ChatGPT clients:** User confirmed desktop UI v29 works, and an iPhone single-file open succeeded. Native iOS launcher labels and some fullscreen/return behavior are controlled by the host rather than the MCP App.
- The v28 HTML remains byte-identical. UI v29 SHA-256: `8f815af73425caa63a89cab50672c424e8a42c809fdc0ff821ce9977ae5bd514`.

## Known limitations

- iOS ChatGPT may show its native **Open with HPC MCP** button before rendering the filename-bearing in-app card. The MCP App cannot guarantee a custom native button label.
- Whether fullscreen is offered, granted, and dismissed is ultimately controlled by the ChatGPT host. The app handles refusal without silently expanding the inline viewer.
- Remote SVG, TIFF, large unsupported PDFs, and PDF embedded scripts are not processed as executable viewer content.

## Documentation

See [User Guide](USER_GUIDE.md), [Installation](INSTALLATION.md), [Raster Image Preview](IMAGE_PREVIEW_V27_JA.md), [PDF Preview](PDF_PREVIEW_V28_JA.md), [Compact Launcher](COMPACT_LAUNCH_V29_JA.md), and [Third-party notices](../THIRD_PARTY_NOTICES.md).

This release is source-only. No user-owned HPC service configurations, Slurm jobs, or allowlists are bundled or changed.
