import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {tooltipPosition} from "../src/icon-tooltip.ts";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const source = readFileSync(new URL("../src/icon-tooltip.ts", import.meta.url), "utf8");
const main = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");

test("tooltip flips below controls near top of viewport", () => {
  const anchor = {left: 60, right: 94, top: 4, bottom: 38, width: 34, height: 34};
  assert.deepEqual(tooltipPosition(anchor, 90, 20, 300, 200), {left: 32, top: 46});
});

test("tooltip prefers above and clamps horizontal position at edges", () => {
  const anchor = {left: 290, right: 324, top: 150, bottom: 184, width: 34, height: 34};
  assert.deepEqual(tooltipPosition(anchor, 120, 28, 320, 210), {left: 192, top: 114});
});

test("tooltip stays within left viewport edge", () => {
  const anchor = {left: 0, right: 34, top: 80, bottom: 114, width: 34, height: 34};
  assert.deepEqual(tooltipPosition(anchor, 140, 20, 320, 200), {left: 8, top: 52});
});

test("tooltip is enabled for mouse and keyboard icon controls", () => {
  assert.match(html, /id="icon-tooltip" role="tooltip" hidden/);
  assert.match(html, /#icon-tooltip \{position:fixed;/);
  assert.match(source, /document\.addEventListener\("pointerover"/);
  assert.match(source, /document\.addEventListener\("focusin"/);
  assert.match(source, /document\.addEventListener\("pointerout"/);
  assert.match(source, /document\.addEventListener\("focusout"/);
  assert.match(source, /"\.icon-btn, \.twisty, \.close-tab"/);
  assert.match(source, /button\.getAttribute\("aria-label"\)/);
  assert.match(source, /button\.closest\("\[hidden\]"\)/);
  assert.match(source, /document\.elementFromPoint\(event\.clientX, event\.clientY\)/);
  assert.match(main, /installIconTooltips\(\)/);
});
