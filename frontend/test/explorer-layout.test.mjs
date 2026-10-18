import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const source = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");

test("viewer takes full width and explorer starts hidden", () => {
  assert.match(html, /\.workspace \{display:grid;grid-template-columns:minmax\(0,1fr\)/);
  assert.match(html, /class="sidebar" id="explorer-panel"[^>]*hidden/);
  assert.match(html, /id="explorer-toggle"[^>]*aria-expanded="false"/);
  assert.match(html, /\.workspace\.explorer-open \{grid-template-columns:/);
});

test("toolbar toggles explorer without replacing the viewer", () => {
  assert.match(source, /addEventListener\("click", toggleExplorer\)/);
  assert.match(source, /sidebar\.hidden = !open/);
  assert.match(source, /aria-expanded", String\(open\)/);
  assert.match(source, /setExplorerOpen\(false\)/);
});

test("explorer directories are loaded on demand", () => {
  assert.match(source, /if \(open && active\)/);
  assert.match(source, /if \(!el\("explorer-panel"\)\.hidden && parent !== currentDirectory\)/);
});
