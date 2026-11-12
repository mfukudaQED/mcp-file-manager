import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import ts from "typescript";

/** Execute the small, pure launcher-label module as a JavaScript regression. */
async function loadLabels() {
  const source = readFileSync(fileURLToPath(new URL("../src/compact-launch.ts", import.meta.url)), "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  return import("data:text/javascript;base64," + Buffer.from(output).toString("base64"));
}
const { launchDetails, launchHost } = await loadLabels();
assert.deepEqual(launchDetails("/work/a/b/論文 H₄.pdf"),
  { filename: "論文 H₄.pdf", fileType: "PDF" });
assert.deepEqual(launchDetails("/work/CWF.wan.PNG"),
  { filename: "CWF.wan.PNG", fileType: "画像" });
assert.equal(launchDetails("/work/model.md").fileType, "Markdown");
assert.equal(launchDetails("/work/SCF.out").fileType, "テキスト");
assert.equal(launchDetails(null).filename, "HPC File Browser");
assert.equal(launchDetails(" ").fileType, "ファイルブラウザー");
assert.equal(launchHost("sham"), "sham");
assert.equal(launchHost("ohtaka"), "ohtaka");
assert.equal(launchHost("<img src=x>"), "HPC");

const html = readFileSync(fileURLToPath(new URL("../index.html", import.meta.url)), "utf8");
assert.ok(html.includes('id="launch-card"') && html.includes('id="launch-filename"'));
assert.ok(html.includes('id="launch-open"') && html.includes('id="viewer-shell" class="viewer-shell" hidden'));
assert.ok(html.includes("aria-expanded=") && html.includes("aria-live="));
assert.ok(html.includes("__MCPFM_V29_HOST__"));
assert.ok(html.indexOf('id="launch-card"') < html.indexOf('id="viewer-shell"'));
const frontend = readFileSync(fileURLToPath(new URL("../src/main.ts", import.meta.url)), "utf8");
assert.ok(frontend.includes('app.requestDisplayMode({ mode: "fullscreen" })'));
assert.ok(frontend.includes('app.onhostcontextchanged ='));
assert.ok(frontend.includes('app.getHostContext()'));
assert.ok(frontend.includes('currentDisplayMode === "fullscreen"'));
assert.ok(frontend.includes("queuedHostPath = null;"));
assert.ok(frontend.includes('el("launch-open").addEventListener("click"'));
console.log("Compact launcher labels, accessible card and fullscreen event wiring passed");
