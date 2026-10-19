import { test } from "node:test";
import assert from "node:assert/strict";
import {
  tabbyProfileUrl, copyableRemotePath, winScpDirectoryPath, winScpDirectoryUrl,
} from "../src/copy-targets.ts";

test("Tabby URL is encoded and excludes control characters", () => {
  assert.equal(tabbyProfileUrl("sham"), "tabby://profile?profileName=sham");
  assert.equal(tabbyProfileUrl("Lab SSH"), "tabby://profile?profileName=Lab%20SSH");
  assert.throws(() => tabbyProfileUrl(" \n "));
  assert.throws(() => tabbyProfileUrl(""));
});

test("WinSCP URL uses a saved site and always opens a directory", () => {
  assert.equal(winScpDirectoryUrl("sham", "/home/user/work/"),
    "winscp-sftp://sham/home/user/work/");
  assert.equal(winScpDirectoryUrl("sham", "/data/a b/#sample"),
    "winscp-sftp://sham/data/a%20b/%23sample/");
  assert.equal(winScpDirectoryUrl("sham", "/"),
    "winscp-sftp://sham/");
  assert.throws(() => winScpDirectoryUrl("me:password@host", "/home/"));
  assert.throws(() => winScpDirectoryUrl("bad/path", "/home/"));
  assert.throws(() => winScpDirectoryUrl("sham", "relative/path"));
});

test("WinSCP opens parent of selected file to prevent unintended download", () => {
  assert.equal(winScpDirectoryPath("/home/user/work/README.md", true),
    "/home/user/work/");
  assert.equal(winScpDirectoryPath("/README.md", true), "/");
  assert.equal(winScpDirectoryPath("/home/user/work", false),
    "/home/user/work/");
  assert.equal(copyableRemotePath("/home/user/a b.txt"),
    "/home/user/a b.txt");
});
