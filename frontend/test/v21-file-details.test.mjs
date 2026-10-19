import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const source = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");

test("document header defaults collapsed with an info icon in toolbar", () => {
  assert.match(html, /class="doc-head" id="file-details" hidden/);
  const button = html.match(/<button[^>]*id="file-details-toggle"[^>]*>[\s\S]*?<\/button>/);
  assert.ok(button);
  assert.match(button[0], /class="icon-btn"/);
  assert.match(button[0], /aria-controls="file-details" aria-expanded="false"/);
  assert.match(button[0], /aria-label="Show file details"/);
  assert.match(button[0], /href="#icon-info"/);
  for (const id of ["filename", "fullpath", "meta"]) {
    assert.match(html, new RegExp('id="' + id + '"'));
  }
});

test("disclosure toggles visibility and stays available when the file changes", () => {
  assert.match(source, /function setFileDetailsOpen\(open: boolean\)/);
  assert.match(source, /details\.hidden = !open/);
  assert.match(source, /toggle\.setAttribute\("aria-expanded", String\(open\)\)/);
  assert.match(source, /toggle\.setAttribute\("aria-label", label\)/);
  assert.match(source, /setFileDetailsOpen\(el\("file-details"\)\.hidden\)/);
  assert.match(source, /el\("filename"\)\.textContent = opened\.path/);
  assert.match(source, /el\("fullpath"\)\.textContent = opened\.path/);
  assert.match(source, /el\("meta"\)\.textContent =/);
});

test("new disclosure shares tooltip and retains old collapsed status", () => {
  assert.match(html, /id="icon-info"/);
  assert.match(html, /id="icon-tooltip" role="tooltip" hidden/);
  assert.match(html, /id="status-panel" class="status-panel" hidden/);
  assert.doesNotMatch(html, /id="transfer-download"|id="transfer-upload"/);
});
