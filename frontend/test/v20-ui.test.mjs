import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const source = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");

test("copy buttons use distinct inline SVG symbols with short labels", () => {
  for (const [id,icon,name] of [
    ["copy-path", "file-copy", "Path"],
    ["copy-tabby", "square-terminal", "Tabby"],
    ["copy-winscp", "folders", "WinSCP"],
  ]) {
    const re = new RegExp('<button[^>]+id="' + id + '"[^>]*>([\\s\\S]*?)</button>');
    const button = html.match(re);
    assert.ok(button, id);
    assert.match(button[1], new RegExp('href="#icon-' + icon + '"'));
    assert.match(button[1], new RegExp("<span>" + name + "</span>"));
    assert.match(button[0], /aria-label="Copy/);
  }
});

test("other static action buttons use SVG only and retain accessibility names", () => {
  for (const id of ["explorer-toggle", "open", "folder", "refresh", "tail",
                     "history", "edit", "save", "bench", "up", "status-toggle"]) {
    const match = html.match(new RegExp('<button[^>]+id="' + id +
      '"[^>]*>([\\s\\S]*?)</button>'));
    assert.ok(match, id);
    assert.match(match[1], /<svg class="icon"/);
    assert.doesNotMatch(match[1], /[A-Za-z]{4,}(?![^<]*>)/);
    assert.match(match[0], /aria-label="/);
    assert.match(match[0], /title="/);
  }
  assert.doesNotMatch(source, /toggle\.textContent = open/);
});

test("status and metrics are collapsed by default and can be toggled", () => {
  assert.match(html, /id="status-panel" class="status-panel" hidden/);
  assert.match(html, /id="status-toggle"[^>]+aria-expanded="false"/);
  assert.match(source, /panel\.hidden = !expanded/);
  assert.match(source, /button\.setAttribute\("aria-expanded", String\(expanded\)\)/);
  assert.match(source, /flashCopiedIcon/);
  assert.doesNotMatch(html, /id="transfer-download"|id="transfer-upload"/);
});
