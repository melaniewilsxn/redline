import type { TextSpan } from "./document_segments.ts";

export const MAXIMUM_FIND_MATCHES = 1000;

export interface TextMatchPage {
  matches: TextSpan[];
  capped: boolean;
}

/**
 * Find every literal, non-overlapping occurrence of a query.
 * @param text - The document text.
 * @param query - The text to find. Quotes are ordinary characters.
 * @param limit - How many matches to return at most.
 * @returns The matches, and whether more exist past the limit.
 * @throws Does not throw.
 */
export function findTextMatches(text: string, query: string, limit: number): TextMatchPage {
  const queryText = query.trim().toLowerCase();
  if (queryText === "") {
    return { matches: [], capped: false };
  }
  const documentText = text.toLowerCase();
  const matches: TextSpan[] = [];
  let searchFrom = 0;
  while (matches.length < limit) {
    const start = documentText.indexOf(queryText, searchFrom);
    if (start === -1) {
      return { matches, capped: false };
    }
    matches.push({ start, end: start + queryText.length });
    searchFrom = start + queryText.length;
  }
  return { matches, capped: documentText.indexOf(queryText, searchFrom) !== -1 };
}
