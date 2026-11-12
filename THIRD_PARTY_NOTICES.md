# Third-party license notices

MCP File Manager is licensed under the MIT License (see [LICENSE](LICENSE)).
The offline single-file UI bundles code from external projects. Their license
terms remain applicable to the respective components.

| Component | Bundled version | License | Upstream |
| --- | --- | --- | --- |
| PDF.js (`pdfjs-dist`) | 5.4.394 | Apache-2.0 | https://github.com/mozilla/pdf.js |
| KaTeX | 0.18.10 | MIT | https://github.com/KaTeX/KaTeX |
| MCP Apps SDK (`@modelcontextprotocol/ext-apps`) | 2.0.3 | MIT (package metadata; see upstream notices) | https://github.com/modelcontextprotocol/ext-apps |
| CodeMirror 6, Lezer and language modules | versions in `frontend/package-lock.json` | MIT | https://github.com/codemirror |
| `@replit/codemirror-vim` | 6.4.0 | MIT | https://github.com/replit/codemirror-vim |
| DOMPurify | 3.4.17 | MPL-2.0 OR Apache-2.0 | https://github.com/cure53/DOMPurify |
| Highlight.js | 11.11.1 | BSD-3-Clause | https://github.com/highlightjs/highlight.js |
| Marked | 16.4.1 | MIT | https://github.com/markedjs/marked |
| marked-katex-extension | 5.1.13 | MIT | https://github.com/UziTech/marked-katex-extension |

The complete Apache-2.0 license of the bundled PDF.js distribution is shipped
with the Python package at `src/mcp_file_viewer/ui/PDFJS_LICENSE.txt`.
See `frontend/package-lock.json` for the full dependency graph and versions.
Upstream copyright and license notices must be retained when redistributing
the third-party components.
