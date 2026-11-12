import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import ts from "typescript";

/** Generate a minimal, valid two-page PDF without external downloads. */
function samplePdf() {
  const stream1 = "BT /F1 16 Tf 72 720 Td (PDF Preview First Page) Tj ET\n";
  const stream2 = "BT /F1 16 Tf 72 720 Td (PDF Preview Second Page) Tj ET\n";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${stream1.length} >>\nstream\n${stream1}endstream`,
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 7 0 R >>",
    `<< /Length ${stream2.length} >>\nstream\n${stream2}endstream`,
  ];
  let document = "%PDF-1.4\n";
  const offsets = [0];
  for (const [index, content] of objects.entries()) {
    offsets.push(Buffer.byteLength(document, "ascii"));
    document += `${index + 1} 0 obj\n${content}\nendobj\n`;
  }
  const crossrefOffset = Buffer.byteLength(document, "ascii");
  document += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets.slice(1)) {
    document += String(offset).padStart(10, "0") + " 00000 n \n";
  }
  document += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${crossrefOffset}\n%%EOF\n`;
  return Buffer.from(document, "ascii");
}

/** Import the pure TS module from the local installed PDF.js package. */
async function loadModule() {
  const filename = fileURLToPath(new URL("../src/pdf-preview.ts", import.meta.url));
  let { outputText } = ts.transpileModule(readFileSync(filename, "utf8"), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  });
  const base = new URL("../node_modules/pdfjs-dist/legacy/build/", import.meta.url);
  const apiUrl = new URL("pdf.mjs", base).href;
  const workerUrl = new URL("pdf.worker.min.mjs", base).href;
  outputText = outputText.replaceAll('"pdfjs-dist/build/pdf.worker.min.mjs"', JSON.stringify(workerUrl));
  outputText = outputText.replaceAll('"pdfjs-dist"', JSON.stringify(apiUrl));
  return import("data:text/javascript;base64," + Buffer.from(outputText).toString("base64"));
}

const mod = await loadModule();
assert.equal(mod.isPdfPath("/work/paper.PDF"), true);
assert.equal(mod.isPdfPath("/work/figure.png"), false);
const source = samplePdf();
const revision = "pdfstat:" + "a".repeat(64);
const manifest = mod.parsePdfManifest({
  path: "/work/paper.pdf", revision,
  mime_type: "application/pdf", size_bytes: source.length, chunk_bytes: 24576,
});
const part = async (offset) => {
  const data = source.subarray(offset, offset + 24576);
  return { offset, next_offset: offset + data.length, revision,
    size_bytes: source.length, content_base64: data.toString("base64"),
    has_more: offset + data.length < source.length };
};
const assembled = await mod.assemblePdfBytes(manifest, part);
assert.deepEqual(Buffer.from(assembled), source);
await assert.rejects(mod.assemblePdfBytes(manifest, async () => ({
  ...await part(0), revision: "pdfstat:" + "b".repeat(64),
})), /changed or returned/);
assert.throws(() => mod.parsePdfManifest({
  path: "/work/paper.pdf", revision, mime_type: "text/html",
  size_bytes: source.length, chunk_bytes: 24576,
}), /Unsupported/);

const document = await mod.loadPdfDocument(assembled);
assert.equal(document.numPages, 2);
const page1 = await document.getPage(1);
const page2 = await document.getPage(2);
assert.match(await mod.extractPdfText(page1), /First Page/);
assert.match(await mod.extractPdfText(page2), /Second Page/);
assert.equal(page1.getViewport({ scale: 1 }).width, 612);
const { createCanvas } = await import("@napi-rs/canvas");
const viewport = page1.getViewport({ scale: 1 });
const canvas = createCanvas(Math.floor(viewport.width), Math.floor(viewport.height));
await page1.render({ canvas, viewport }).promise;
const pixels = canvas.getContext("2d").getImageData(60, 60, 350, 55).data;
let darkPixels = 0;
for (let i = 0; i < pixels.length; i += 4) {
  if (pixels[i] < 200 && pixels[i + 1] < 200 && pixels[i + 2] < 200) darkPixels++;
}
assert.ok(darkPixels > 20, "Rendered PDF page must contain visible text pixels");
await document.destroy();
console.log("Offline PDF transport and two-page PDF.js parsing passed");
