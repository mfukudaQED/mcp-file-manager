import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import ts from "typescript";

/** Load the local pure TypeScript image-preview module without browser APIs. */
async function loadModule() {
  const filename = fileURLToPath(new URL("../src/image-preview.ts", import.meta.url));
  const source = readFileSync(filename, "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  });
  return import("data:text/javascript;base64," + Buffer.from(outputText).toString("base64"));
}

const { isRasterImage, parseImageManifest, assembleImagePreview } = await loadModule();
assert.equal(isRasterImage("/work/plot.PNG"), true);
assert.equal(isRasterImage("/work/figure.jpeg"), true);
assert.equal(isRasterImage("/work/animated.gif"), true);
assert.equal(isRasterImage("/work/figure.webp"), true);
assert.equal(isRasterImage("/work/danger.svg"), false);

const bytes = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9YwLcy0AAAAASUVORK5CYII=", "base64");
const revision = "imgstat:" + "a".repeat(64);
const manifest = parseImageManifest({
  path: "/work/plot.png", revision, mime_type: "image/png",
  size_bytes: bytes.length, chunk_bytes: 24576,
});
const getChunk = async (offset) => {
  const slice = bytes.subarray(offset, Math.min(offset + manifest.chunkBytes, bytes.length));
  const end = offset + slice.length;
  return { revision, offset, next_offset: end, size_bytes: bytes.length,
    content_base64: slice.toString("base64"), has_more: end < bytes.length };
};
assert.equal(await assembleImagePreview(manifest, getChunk),
  "data:image/png;base64," + bytes.toString("base64"));

const longBytes = Buffer.concat([bytes, Buffer.alloc(50000, 0x45)]);
const bigManifest = parseImageManifest({
  path: "/work/large.webp", revision, mime_type: "image/webp",
  size_bytes: longBytes.length, chunk_bytes: 24576,
});
const dataUrl = await assembleImagePreview(bigManifest, async (offset) => {
  const piece = longBytes.subarray(offset, offset + bigManifest.chunkBytes);
  return { revision, offset, next_offset: offset + piece.length,
    size_bytes: longBytes.length, content_base64: piece.toString("base64"),
    has_more: offset + piece.length < longBytes.length };
});
assert.deepEqual(Buffer.from(dataUrl.split(",")[1], "base64"), longBytes);
await assert.rejects(() => assembleImagePreview(manifest, async () => ({
  revision: "imgstat:" + "b".repeat(64), offset: 0, next_offset: bytes.length,
  size_bytes: bytes.length, content_base64: bytes.toString("base64"),
  has_more: false,
})), /inconsistent/);
assert.throws(() => parseImageManifest({
  path: "/work/bad.png", revision, mime_type: "image/svg+xml",
  size_bytes: bytes.length, chunk_bytes: 24576,
}), /Unsupported/);
assert.throws(() => parseImageManifest({
  path: "/work/large.png", revision, mime_type: "image/png",
  size_bytes: 10000000, chunk_bytes: 24576,
}), /Unsupported/);
console.log("Raster image preview transport tests passed");
