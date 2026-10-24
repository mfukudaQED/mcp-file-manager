import { marked } from "marked";
import DOMPurify from "dompurify";
import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import cpp from "highlight.js/lib/languages/cpp";
import diff from "highlight.js/lib/languages/diff";
import fortran from "highlight.js/lib/languages/fortran";
import json from "highlight.js/lib/languages/json";
import markdown from "highlight.js/lib/languages/markdown";
import python from "highlight.js/lib/languages/python";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";

for (const [name, parser] of [
  ["bash", bash], ["cpp", cpp], ["diff", diff],
  ["fortran", fortran], ["json", json], ["markdown", markdown],
  ["python", python], ["xml", xml], ["yaml", yaml],
] as const) hljs.registerLanguage(name, parser);

const EXTENSIONS: Record<string, string> = {
  md:"markdown", markdown:"markdown", py:"python", pyw:"python",
  sh:"bash", bash:"bash", zsh:"bash", fish:"bash", slurm:"bash",
  f:"fortran", f90:"fortran", f95:"fortran", f03:"fortran", f08:"fortran",
  c:"cpp", cc:"cpp", cpp:"cpp", cxx:"cpp", h:"cpp", hpp:"cpp",
  json:"json", jsonl:"json", yaml:"yaml", yml:"yaml",
  xml:"xml", html:"xml", xhtml:"xml", svg:"xml",
  diff:"diff", patch:"diff",
};

export const MAX_HIGHLIGHT_CHARS = 80_000;
export const MAX_PREVIEW_CHARS = 400_000;
export const MAX_DOCUMENT_CHARS = 2_100_000;

export function languageFor(path: string): string | null {
  const name = path.split("/").pop()?.toLowerCase() ?? "";
  if (name === "makefile" || name === "dockerfile") return "bash";
  const ext = name.includes(".") ? name.split(".").pop() ?? "" : "";
  return EXTENSIONS[ext] ?? null;
}

function highlightInto(code: HTMLElement, content: string, language: string | null): boolean {
  if (content.length > MAX_HIGHLIGHT_CHARS || !language || !hljs.getLanguage(language)) {
    code.textContent = content;
    return false;
  }
  try {
    // highlight.js escapes untrusted code before adding span markup.
    const safeMarkup = hljs.highlight(content, { language, ignoreIllegals: true }).value;
    code.innerHTML = DOMPurify.sanitize(safeMarkup);
    return true;
  } catch {
    code.textContent = content;
    return false;
  }
}

export function renderSource(code: HTMLElement, path: string, content: string): boolean {
  return highlightInto(code, content, languageFor(path));
}

export function renderMarkdown(article: HTMLElement, content: string): void {
  article.replaceChildren();
  if (content.length > MAX_PREVIEW_CHARS) {
    const warning = document.createElement("p");
    warning.textContent = "Preview limit exceeded (" + MAX_PREVIEW_CHARS.toLocaleString() + " characters). Switch to source view.";
    article.append(warning);
    return;
  }

  const rendered = marked.parse(content, { async: false, gfm: true, breaks: false });
  const sanitized = DOMPurify.sanitize(rendered, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: [
      "script", "style", "iframe", "img", "svg", "math",
      "object", "embed", "link", "meta", "base",
      "form", "input", "button", "textarea", "select",
      "video", "audio", "source", "picture",
    ],
    FORBID_ATTR: ["style", "src", "srcset", "srcdoc"],
  });
  article.innerHTML = sanitized;

  for (const link of article.querySelectorAll<HTMLAnchorElement>("a[href]")) {
    // Links require an explicit user click. Never auto-fetch remote images.
    const href = link.getAttribute("href") ?? "";
    if (!/^(https?:|mailto:|#)/i.test(href)) {
      link.removeAttribute("href");
      continue;
    }
    link.target = "_blank";
    link.rel = "noopener noreferrer";
  }
  for (const code of article.querySelectorAll<HTMLElement>("pre code")) {
    const lang = /language-([a-z0-9_-]+)/i.exec(code.className)?.[1]?.toLowerCase() ?? null;
    const aliases: Record<string,string> = { c:"cpp", cxx:"cpp", shell:"bash", sh:"bash", f90:"fortran", html:"xml" };
    highlightInto(code, code.textContent ?? "", lang ? aliases[lang] ?? lang : null);
  }
}
