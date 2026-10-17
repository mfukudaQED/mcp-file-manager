import { test } from "node:test";
import assert from "node:assert/strict";
import { readCompleteRevision } from "../src/revision-reader.ts";

const rev = "sha256:" + "a".repeat(64);
test("collects revision-pinned Unicode codepoint offsets", async () => {
  const text = "A😀漢字";
  const chunks = ["A😀", "漢字"];
  const result = await readCompleteRevision(async (offset, revision) => {
    assert.equal(revision, rev);
    const i = offset === 0 ? 0 : 1;
    return {content:chunks[i], revision:rev, offset,
      next_offset:offset + [...chunks[i]].length, total_chars:4, has_more:i===0};
  }, rev);
  assert.equal(result.text, text);
});
test("rejects overlapping offsets and changed revisions", async () => {
  await assert.rejects(readCompleteRevision(async () => ({
    content:"abc",revision:rev,offset:1,next_offset:4,total_chars:4,has_more:false,
  }),rev), /Invalid/);
  await assert.rejects(readCompleteRevision(async () => ({
    content:"abc",revision:"sha256:"+"b".repeat(64),offset:0,
    next_offset:3,total_chars:3,has_more:false,
  }),rev), /Invalid/);
});
test("rejects oversized file and nonadvancing pages", async () => {
  await assert.rejects(readCompleteRevision(async () => ({
    content:"abcd",revision:rev,offset:0,next_offset:4,total_chars:4,has_more:false,
  }),rev,3), /64 KiB/);
  await assert.rejects(readCompleteRevision(async () => ({
    content:"",revision:rev,offset:0,next_offset:0,total_chars:1,has_more:true,
  }),rev), /Invalid/);
});
