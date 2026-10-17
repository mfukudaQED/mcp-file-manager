import { test } from "node:test";
import assert from "node:assert/strict";
import { findMatches, MAX_MATCHES, MAX_TABS } from "../src/search.ts";

test("literal search is case-insensitive and line-numbered", () => {
  assert.deepEqual(findMatches("Abc\naBC abc", "abc"), [
    { start:0,end:3,line:1,column:1 },
    { start:4,end:7,line:2,column:1 },
    { start:8,end:11,line:2,column:5 },
  ]);
});
test("literal search does not treat regular expressions as regex", () => {
  assert.equal(findMatches("a.c abc a.c", "a.c").length, 2);
});
test("search input and result counts have bounded limits", () => {
  assert.deepEqual(findMatches("x".repeat(250), "x".repeat(121)), []);
  assert.equal(findMatches("x ".repeat(1000), "x").length, MAX_MATCHES);
  assert.equal(findMatches("abc", "").length, 0);
  assert.equal(MAX_TABS, 5);
});
