/** Reassemble a complete, revision-pinned Unicode snapshot from bounded MCP pages. */
export interface RevisionPage {
  content?: unknown;
  revision?: unknown;
  offset?: unknown;
  next_offset?: unknown;
  total_chars?: unknown;
  has_more?: unknown;
}

export interface CompleteRevision {
  text: string;
  revision: string;
}

export async function readCompleteRevision(
  fetchPage: (offset: number, revision: string | null) => Promise<RevisionPage>,
  expectedRevision: string | null = null,
  maxBytes = 64 * 1024,
  maxPages = 96,
): Promise<CompleteRevision> {
  let revision = expectedRevision;
  let offset = 0;
  let totalChars: number | null = null;
  const chunks: string[] = [];
  let totalBytes = 0;
  const encoder = new TextEncoder();

  for (let i = 0; i < maxPages; i++) {
    const page = await fetchPage(offset, revision);
    if (typeof page.content !== "string" ||
        typeof page.revision !== "string" ||
        typeof page.next_offset !== "number" ||
        typeof page.total_chars !== "number" ||
        typeof page.offset !== "number" ||
        typeof page.has_more !== "boolean" ||
        !/^sha256:[0-9a-f]{64}$/.test(page.revision) ||
        (revision !== null && revision !== page.revision) ||
        page.offset !== offset ||
        (totalChars !== null && totalChars !== page.total_chars) ||
        !Number.isSafeInteger(page.next_offset) ||
        !Number.isSafeInteger(page.total_chars) ||
        page.total_chars < 0 ||
        page.next_offset < offset ||
        page.next_offset > page.total_chars ||
        page.next_offset - offset !== [...page.content].length ||
        (page.has_more && page.next_offset === offset) ||
        page.has_more !== (page.next_offset < page.total_chars)) {
      throw new Error("Invalid or inconsistent revision-pinned file chunk.");
    }
    revision = page.revision;
    totalChars = page.total_chars;
    totalBytes += encoder.encode(page.content).length;
    if (totalBytes > maxBytes) {
      throw new Error("File exceeds the 64 KiB editor and preview limit.");
    }
    chunks.push(page.content);
    offset = page.next_offset;
    if (!page.has_more) {
      return { text: chunks.join(""), revision };
    }
  }
  throw new Error("Too many chunks; file preview was not completed.");
}
