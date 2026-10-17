export type JsonRecord = Record<string, unknown>;

export type Cursor =
  | { kind: "lines"; line: number }
  | { kind: "section"; id: string; offset: number };

function record(value: unknown): value is JsonRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function decodeToolResult(response: unknown): JsonRecord {
  if (!record(response)) throw new Error("Invalid MCP response");
  if (response.isError === true) throw new Error("MCP tool failed");
  const parts = response.content;
  const textPart = Array.isArray(parts)
    ? parts.find((entry) => record(entry) && entry.type === "text" && typeof entry.text === "string")
    : undefined;
  let value: unknown = textPart && record(textPart) ? textPart.text : response.structuredContent;
  try {
    if (typeof value === "string") value = JSON.parse(value);
    if (record(value) && typeof value.result === "string") value = JSON.parse(value.result);
  } catch {
    throw new Error("Invalid MCP response JSON");
  }
  if (!record(value)) throw new Error("Malformed MCP result");
  if (record(value.error)) {
    const error = value.error;
    throw new Error(
      typeof error.message === "string" ? error.message : String(error.code ?? "File operation failed"),
    );
  }
  return value;
}

function positiveInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && typeof value === "number" && value >= 0;
}

export function nextCursor(
  previous: Cursor,
  result: JsonRecord,
): Cursor | null {
  if (result.has_more !== true) return null;
  if (previous.kind === "lines") {
    if (!positiveInteger(result.next_line) || result.next_line <= previous.line) {
      throw new Error("Line paging did not advance");
    }
    return { kind: "lines", line: result.next_line };
  }
  if (!positiveInteger(result.next_offset) || result.next_offset <= previous.offset) {
    throw new Error("Section paging did not advance");
  }
  return { kind: "section", id: previous.id, offset: result.next_offset };
}

export function parentDirectory(path: string): string {
  const normalized = path.trim().replace(/\/+$/, "");
  if (!normalized.startsWith("/")) {
    throw new Error("An absolute path is required");
  }
  const i = normalized.lastIndexOf("/");
  return i <= 0 ? "/" : normalized.slice(0, i);
}

export function childPath(directory: string, filename: string): string {
  if (!filename || filename === "." || filename === ".." || filename.includes("/")) {
    throw new Error("Invalid filename");
  }
  return (directory === "/" ? "" : directory.replace(/\/+$/, "")) + "/" + filename;
}
