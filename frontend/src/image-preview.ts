import type { JsonRecord } from "./state";

/** Supported raster previews; deliberately exclude SVG and embedded HTML. */
export function isRasterImage(path: string): boolean {
  return /\.(png|jpe?g|gif|webp)$/i.test(path);
}

const ALLOWED_TYPES = new Set(["image/png", "image/jpeg", "image/gif", "image/webp"]);
const MAX_IMAGE_BYTES = 4 * 1024 * 1024;
const MAX_CHUNK_BYTES = 24 * 1024;
const PARALLEL_READS = 4;

export interface ImageManifest {
  path: string;
  revision: string;
  mimeType: string;
  sizeBytes: number;
  chunkBytes: number;
}

/** Reject malformed server manifests before allocating large preview strings. */
export function parseImageManifest(data: JsonRecord): ImageManifest {
  const { path, revision, mime_type: mimeType, size_bytes: sizeBytes, chunk_bytes: chunkBytes } = data;
  if (typeof path !== "string" || !path.startsWith("/") ||
      typeof revision !== "string" || !/^imgstat:[a-f0-9]{64}$/.test(revision) ||
      typeof mimeType !== "string" || !ALLOWED_TYPES.has(mimeType) ||
      typeof sizeBytes !== "number" || !Number.isSafeInteger(sizeBytes) ||
      sizeBytes < 12 || sizeBytes > MAX_IMAGE_BYTES ||
      typeof chunkBytes !== "number" || !Number.isSafeInteger(chunkBytes) ||
      chunkBytes <= 0 || chunkBytes > MAX_CHUNK_BYTES || chunkBytes % 3 !== 0) {
    throw new Error("Unsupported or oversized image manifest");
  }
  return { path, revision, mimeType, sizeBytes, chunkBytes };
}

function encodedByteLength(text: string): number {
  if (!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(text)) {
    throw new Error("Invalid Base64 image chunk");
  }
  return text.length / 4 * 3 - (text.endsWith("==") ? 2 : text.endsWith("=") ? 1 : 0);
}

/**
 * Retrieve only the requested image through bounded, revision-pinned MCP chunks.
 * No fetch(), remote URL, local disk writes, or upload capability is required.
 */
export async function assembleImagePreview(
  manifest: ImageManifest,
  read: (offset: number) => Promise<JsonRecord>,
  progress?: (loadedBytes: number, totalBytes: number) => void,
): Promise<string> {
  const total = Math.ceil(manifest.sizeBytes / manifest.chunkBytes);
  const chunks: string[] = new Array(total);
  for (let first = 0; first < total; first += PARALLEL_READS) {
    const tasks = Array.from({ length: Math.min(PARALLEL_READS, total - first) }, (_, j) => {
      const i = first + j;
      const offset = i * manifest.chunkBytes;
      const expectedLength = Math.min(manifest.chunkBytes, manifest.sizeBytes - offset);
      return read(offset).then((data) => {
        if (data.revision !== manifest.revision || data.offset !== offset ||
            data.next_offset !== offset + expectedLength ||
            data.size_bytes !== manifest.sizeBytes ||
            data.has_more !== (offset + expectedLength < manifest.sizeBytes) ||
            typeof data.content_base64 !== "string" ||
            encodedByteLength(data.content_base64) !== expectedLength) {
          throw new Error("Image chunk is inconsistent with the requested revision");
        }
        return [i, data.content_base64] as const;
      });
    });
    const completed = await Promise.all(tasks);
    for (const [i, value] of completed) chunks[i] = value;
    progress?.(Math.min((first + completed.length) * manifest.chunkBytes, manifest.sizeBytes),
      manifest.sizeBytes);
  }
  return "data:" + manifest.mimeType + ";base64," + chunks.join("");
}
