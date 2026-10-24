import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { INITIAL_VIEW_LINES, VIEW_PAGE_LINES, needsInitialFill } from "../src/view-paging.ts";

test("initial view keeps loading until at least 1,000 lines", () => {
  assert.equal(INITIAL_VIEW_LINES, 1000);
  assert.equal(VIEW_PAGE_LINES, 1000);
  assert.equal(needsInitialFill(1), true);
  assert.equal(needsInitialFill(999), true);
  assert.equal(needsInitialFill(1000), true);
  assert.equal(needsInitialFill(1001), false);
  assert.equal(needsInitialFill(0), false);
});
test("continuation remains button-only; scrolling never triggers page loading", () => {
  const source = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
  const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
  assert.match(source, /el\("more"\)\.addEventListener\("click", \(\) => void readMore\(\)\)/);
  assert.doesNotMatch(source, /addEventListener\("scroll"/);
  assert.doesNotMatch(source, /maybeAutoLoadOnScroll|nearScrollBottom/);
  assert.match(html, /id="more" disabled hidden aria-label="Load more"/);
});
