import type { ReactNode } from "react";

import type {
  DocumentSummaryResponse,
  SearchHitResponse,
  SnippetResponse,
} from "../../api/types.ts";
import styles from "./search_results.module.css";

const MINIMUM_TEXT_SEARCH_CHARACTERS = 2;

/**
 * Contract names and text hits for one query.
 * @param query - The text in the search field.
 * @param documents - The loaded contracts, used for name matching.
 * @param hits - Text hits for the settled query.
 * @param textSettled - Whether the text search for this query has finished.
 * @param onOpenDocument - Opens a contract from its name.
 * @param onOpenMatch - Opens a contract at a text match.
 * @returns The two groups, or the empty message.
 * @throws Does not throw.
 */
export function SearchResults({
  query,
  documents,
  hits,
  textSettled,
  onOpenDocument,
  onOpenMatch,
}: {
  query: string;
  documents: DocumentSummaryResponse[];
  hits: SearchHitResponse[];
  textSettled: boolean;
  onOpenDocument: (documentId: string) => void;
  onOpenMatch: (
    documentId: string,
    highlights: SnippetResponse["highlights"],
    focusStart: number,
    focusEnd: number,
  ) => void;
}): ReactNode {
  const trimmedQuery = query.trim();
  const contracts = documents.filter((document) =>
    document.title.toLowerCase().includes(trimmedQuery.toLowerCase()),
  );
  const showText = trimmedQuery.length >= MINIMUM_TEXT_SEARCH_CHARACTERS;
  const textHits = showText ? hits : [];
  if (contracts.length === 0 && textHits.length === 0 && (textSettled || !showText)) {
    const message = showText
      ? `No contracts or text match “${trimmedQuery}”.`
      : `No contract names match “${trimmedQuery}”.`;
    return <p className={styles.empty}>{message}</p>;
  }
  return (
    <div className={styles.results}>
      {contracts.length === 0 ? null : (
        <section className={styles.group}>
          <h2 className={styles.sectionHeading}>Contracts</h2>
          {contracts.map((document) => (
            <button
              key={document.id}
              type="button"
              className={styles.contract}
              onClick={() => onOpenDocument(document.id)}
            >
              <span className={styles.contractTitle}>{document.title}</span>
              <span className={styles.meta}>Version {document.version}</span>
            </button>
          ))}
        </section>
      )}
      {textHits.length === 0 ? null : (
        <section className={styles.group}>
          <h2 className={styles.sectionHeading}>In contract text</h2>
          {textHits.map((hit) => (
            <div key={hit.document_id} className={styles.hit}>
              <h3 className={styles.title}>
                {hit.title} <span className={styles.count}>{hit.match_count} matches</span>
              </h3>
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
            </div>
          ))}
        </section>
      )}
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
