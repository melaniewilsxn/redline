import type { ReactNode } from "react";

import type { SearchHitResponse, SnippetResponse } from "../../api/types.ts";
import styles from "./search_results.module.css";

/**
 * Search hits grouped by contract.
 * @param query - The query that was searched.
 * @param hits - One hit per contract.
 * @param onOpenMatch - Opens the contract at a match and keeps that hit's highlights.
 * @returns The results, or the empty message.
 * @throws Does not throw.
 */
export function SearchResults({
  query,
  hits,
  onOpenMatch,
}: {
  query: string;
  hits: SearchHitResponse[];
  onOpenMatch: (
    documentId: string,
    highlights: SnippetResponse["highlights"],
    focusStart: number,
    focusEnd: number,
  ) => void;
}): ReactNode {
  if (hits.length === 0) {
    return (
      <p className={styles.empty}>
        No matches for “{query}”. Every word must appear; put exact phrases in quotes.
      </p>
    );
  }
  return (
    <div className={styles.results}>
      {hits.map((hit) => (
        <section key={hit.document_id} className={styles.group}>
          <h2 className={styles.title}>
            {hit.title} <span className={styles.count}>{hit.match_count} matches</span>
          </h2>
          {hit.snippets.map((snippet) => (
            <button
              key={`${snippet.start}-${snippet.end}`}
              type="button"
              className={styles.snippet}
              onClick={() =>
                onOpenMatch(
                  hit.document_id,
                  hit.snippets.flatMap((listedSnippet) => listedSnippet.highlights),
                  matchStart(snippet),
                  matchEnd(snippet),
                )
              }
            >
              <SnippetText snippet={snippet} />
            </button>
          ))}
        </section>
      ))}
    </div>
  );
}

/**
 * Draw a snippet with its matches marked.
 * @param snippet - The excerpt and its highlight offsets.
 * @returns The excerpt.
 * @throws Does not throw.
 */
function SnippetText({ snippet }: { snippet: SnippetResponse }): ReactNode {
  const pieces: ReactNode[] = [];
  let cursor = 0;
  const highlights = [...snippet.highlights].sort((left, right) => left.start - right.start);
  for (const highlight of highlights) {
    const start = highlight.start - snippet.start;
    const end = highlight.end - snippet.start;
    if (start > cursor) {
      pieces.push(snippet.text.slice(cursor, start));
    }
    pieces.push(
      <mark key={`${highlight.start}-${highlight.end}`}>{snippet.text.slice(start, end)}</mark>,
    );
    cursor = end;
  }
  if (cursor < snippet.text.length) {
    pieces.push(snippet.text.slice(cursor));
  }
  return <span>{pieces}</span>;
}

/**
 * Return the start of the first highlight, or the snippet start.
 * @param snippet - The excerpt.
 * @returns A document offset.
 * @throws Does not throw.
 */
function matchStart(snippet: SnippetResponse): number {
  const first = snippet.highlights[0];
  return first === undefined ? snippet.start : first.start;
}

/**
 * Return the end of the first highlight, or the snippet end.
 * @param snippet - The excerpt.
 * @returns A document offset.
 * @throws Does not throw.
 */
function matchEnd(snippet: SnippetResponse): number {
  const first = snippet.highlights[0];
  return first === undefined ? snippet.end : first.end;
}
