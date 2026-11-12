/** Read-only offline PDF.js preview for MCP File Manager. */
import "pdfjs-dist/build/pdf.worker.min.mjs";
import { getDocument, type PDFDocumentProxy, type PDFPageProxy } from "pdfjs-dist";
import type { JsonRecord } from "./state";

const MAX_PDF_BYTES = 8 * 1024 * 1024;
const CHUNK_BYTES = 24 * 1024;
const PARALLEL = 4;
export const MAX_RENDER_PIXELS = 4_000_000;

export interface PdfManifest {
  path: string;
  revision: string;
  mimeType: "application/pdf";
  sizeBytes: number;
  chunkBytes: number;
}

export function isPdfPath(path: string): boolean {
  return /\.pdf$/i.test(path);
}

/** Validate metadata before allocating client memory. */
export function parsePdfManifest(raw: JsonRecord): PdfManifest {
  const { path, revision, mime_type: mimeType, size_bytes: size, chunk_bytes: chunk } = raw;
  if (typeof path !== "string" || !path.startsWith("/") ||
      typeof revision !== "string" || !/^pdfstat:[0-9a-f]{64}$/.test(revision) ||
      mimeType !== "application/pdf" || !Number.isSafeInteger(size) || typeof size !== "number" ||
      size < 16 || size > MAX_PDF_BYTES ||
      typeof chunk !== "number" || !Number.isSafeInteger(chunk) ||
      chunk < 3 || chunk > CHUNK_BYTES || chunk % 3 !== 0) {
    throw new Error("Unsupported or oversized PDF manifest");
  }
  return { path, revision, mimeType: "application/pdf", sizeBytes: size, chunkBytes: chunk };
}

function base64Bytes(value: unknown): Uint8Array {
  if (typeof value !== "string" || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value)) {
    throw new Error("Invalid Base64 PDF chunk");
  }
  const decoded = atob(value);
  const bytes = new Uint8Array(decoded.length);
  for (let i = 0; i < decoded.length; ++i) bytes[i] = decoded.charCodeAt(i);
  return bytes;
}

/** Assemble capped binary PDF chunks with strict revision and offset checks. */
export async function assemblePdfBytes(
  manifest: PdfManifest,
  read: (offset: number) => Promise<JsonRecord>,
  progress?: (completed: number, total: number) => void,
): Promise<Uint8Array> {
  const data = new Uint8Array(manifest.sizeBytes);
  const totalChunks = Math.ceil(manifest.sizeBytes / manifest.chunkBytes);
  for (let first = 0; first < totalChunks; first += PARALLEL) {
    const fetched = await Promise.all(Array.from(
      { length: Math.min(PARALLEL, totalChunks - first) },
      async (_, i) => {
        const offset = (first + i) * manifest.chunkBytes;
        const expected = Math.min(manifest.chunkBytes, manifest.sizeBytes - offset);
        const chunk = await read(offset);
        if (chunk.revision !== manifest.revision || chunk.offset !== offset ||
            chunk.next_offset !== offset + expected ||
            chunk.size_bytes !== manifest.sizeBytes ||
            chunk.has_more !== (offset + expected < manifest.sizeBytes)) {
          throw new Error("PDF changed or returned an inconsistent chunk");
        }
        const bytes = base64Bytes(chunk.content_base64);
        if (bytes.length !== expected) throw new Error("Unexpected PDF chunk size");
        return { offset, bytes };
      },
    ));
    for (const { offset, bytes } of fetched) data.set(bytes, offset);
    progress?.(Math.min((first + fetched.length) * manifest.chunkBytes, manifest.sizeBytes),
      manifest.sizeBytes);
  }
  if (String.fromCharCode(...data.slice(0, 5)) !== "%PDF-") {
    throw new Error("The received file is not a PDF");
  }
  return data;
}

export type PdfDocument = PDFDocumentProxy;

/**
 * Run the bundled PDF.js parser in fake-worker mode without a network worker.
 * The packaged worker module is imported above and registers a local handler.
 * No annotation scripting, remote fonts, URLs, or PDF attachments are activated.
 */
export async function loadPdfDocument(data: Uint8Array): Promise<PdfDocument> {
  if (data.byteLength > MAX_PDF_BYTES || data.byteLength < 16) throw new Error("PDF size is unsupported");
  const task = getDocument({
    data: data.slice(),
    isEvalSupported: false,
    disableAutoFetch: true,
    disableStream: true,
    useSystemFonts: true,
    enableXfa: false,
    stopAtErrors: true,
  });
  const doc = await task.promise;
  if (doc.numPages < 1 || doc.numPages > 2000) {
    await task.destroy();
    throw new Error("Unsupported PDF page count");
  }
  return doc;
}

/** Render a single PDF page with a strict browser canvas pixel budget. */
export async function renderPdfPage(
  page: PDFPageProxy,
  target: HTMLElement,
  desiredScale: number,
): Promise<void> {
  if (!Number.isFinite(desiredScale) || desiredScale <= 0) throw new Error("Invalid PDF zoom");
  const base = page.getViewport({ scale: 1 });
  const maxScale = Math.min(4096 / base.width, 4096 / base.height,
    Math.sqrt(MAX_RENDER_PIXELS / (base.width * base.height)));
  const scale = Math.max(0.05, Math.min(desiredScale, maxScale));
  const viewport = page.getViewport({ scale });
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.floor(viewport.width));
  canvas.height = Math.max(1, Math.floor(viewport.height));
  canvas.className = "pdf-page-canvas";
  await page.render({ canvas, viewport, intent: "display" }).promise;
  target.replaceChildren(canvas);
}

/** Extract only the currently selected page's text for optional copying. */
export async function extractPdfText(page: PDFPageProxy): Promise<string> {
  const content = await page.getTextContent();
  const lines: string[] = [];
  for (const item of content.items) {
    if (!("str" in item) || typeof item.str !== "string") continue;
    lines.push(item.str);
    if (lines.join(" ").length > 300_000) break;
  }
  return lines.join(" ").slice(0, 300_000);
}
