/** Bounded literal search over the text already loaded into the browser. */
export interface Match {
  start: number;
  end: number;
  line: number;
  column: number;
}

export const MAX_QUERY_CHARS = 120;
export const MAX_MATCHES = 200;

/**
 * Match positions use UTF-16 indices, as required by DOM text operations.
 * No regex compilation from user input. Search never accesses the HPC filesystem.
 */
export function findMatches(text: string, query: string, maxMatches = MAX_MATCHES): Match[] {
  if (!query || query.length > MAX_QUERY_CHARS || !Number.isSafeInteger(maxMatches)
      || maxMatches < 1 || maxMatches > MAX_MATCHES) return [];
  const matches: Match[] = [];
  const lowerQuery = query.toLowerCase();
  const lowerText = text.toLowerCase();
  let cursor = 0, line = 1, lineStart = 0, from = 0;

  while (matches.length < maxMatches && from < lowerText.length) {
    const at = lowerText.indexOf(lowerQuery, from);
    if (at < 0) break;
    // Verify the source span; Unicode casefolding can change code-unit length.
    const fragment = text.slice(at, at + query.length);
    if (fragment.toLowerCase() !== lowerQuery) { from = at + 1; continue; }
    const newlines = text.slice(cursor, at).split("\n");
    if (newlines.length > 1) {
      line += newlines.length - 1;
      lineStart = at - newlines[newlines.length - 1].length;
    }
    matches.push({ start: at, end: at + query.length, line, column: at - lineStart + 1 });
    cursor = at;
    from = at + Math.max(1, query.length);
  }
  return matches;
}

/** Keeps a small, in-memory set of open file snapshots. */
export const MAX_TABS = 5;
