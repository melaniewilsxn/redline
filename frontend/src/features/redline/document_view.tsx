import { useEffect, useRef, useState, type ReactNode } from "react";

import type { DocumentResponse, TextSpanResponse } from "../../api/types.ts";
import { StatusBanner } from "../../components/status_banner.tsx";
import { useDocumentSearch } from "../search/use_search.ts";
import {
  ChangeState,
  SegmentKind,
  SuggestionStatus,
  buildDocumentParagraphs,
  type DocumentSegment,
  type ReviewSuggestion,
} from "./document_segments.ts";
import styles from "./document_view.module.css";

const PULSE_DURATION_MS = 600;
const MATCH_STEP = 1;

/**
 * The open contract, with suggestions and search matches drawn in the text.
 * @param document - The contract, or null while it is closed.
 * @param suggestions - The open review, or none.
 * @param activeSuggestionId - The suggestion the keyboard is on.
 * @param hoveredSuggestionId - The suggestion whose card is hovered.
 * @param jumpStart - A match to scroll to, or null.
 * @param jumpEnd - The end of that match.
 * @param loading - Whether the contract is still opening.
 * @param failed - Whether the contract could not be loaded.
 * @param onSelectSuggestion - Makes a suggestion active.
 * @param onHoverSuggestion - Highlights a suggestion from the text.
 * @returns The document column.
 * @throws Does not throw.
 */
export function DocumentView({
  document,
  suggestions,
  activeSuggestionId,
  hoveredSuggestionId,
  jumpStart,
  jumpEnd,
  loading,
  failed,
  onSelectSuggestion,
  onHoverSuggestion,
}: {
  document: DocumentResponse | null;
  suggestions: ReviewSuggestion[];
  activeSuggestionId: string | null;
  hoveredSuggestionId: string | null;
  jumpStart: number | null;
  jumpEnd: number | null;
  loading: boolean;
  failed: boolean;
  onSelectSuggestion: (suggestionId: string) => void;
  onHoverSuggestion: (suggestionId: string | null) => void;
}): ReactNode {
  const [query, setQuery] = useState("");
  const [matchIndex, setMatchIndex] = useState(0);
  const [trackedQuery, setTrackedQuery] = useState("");
  const [trackedDocumentId, setTrackedDocumentId] = useState("");
  const columnRef = useRef<HTMLDivElement>(null);
  const search = useDocumentSearch(document?.id ?? "", query);
  const hit = search.search.data?.body.hits[0];
  const snippets = hit?.snippets ?? [];
  const matchCount = hit?.match_count ?? 0;
  const currentSnippet = snippets[matchIndex] ?? snippets[0];
  const documentHighlights = search.searching
    ? snippets.flatMap((snippet) => snippet.highlights)
    : jumpHighlight(jumpStart, jumpEnd);
  const paragraphs =
    document === null
      ? []
      : buildDocumentParagraphs(document.text, suggestions, documentHighlights);
  const scrollStart = search.searching
    ? (currentSnippet?.highlights[0]?.start ?? currentSnippet?.start ?? null)
    : jumpStart;

  const documentId = document?.id ?? "";
  if (trackedDocumentId !== documentId) {
    setTrackedDocumentId(documentId);
    setTrackedQuery("");
    setQuery("");
    setMatchIndex(0);
  } else if (trackedQuery !== search.settledQuery) {
    setTrackedQuery(search.settledQuery);
    setMatchIndex(0);
  }

  useEffect(() => {
    const column = columnRef.current;
    const target = findSegment(column, scrollStart);
    target?.scrollIntoView({ block: "center", behavior: scrollBehavior() });
    if (target === null) {
      return;
    }
    target.classList.add(styles.pulse);
    const timer = window.setTimeout(() => target.classList.remove(styles.pulse), PULSE_DURATION_MS);
    return () => {
      window.clearTimeout(timer);
      target.classList.remove(styles.pulse);
    };
  }, [scrollStart, document?.text]);

  useEffect(() => {
    if (activeSuggestionId === null || columnRef.current === null) {
      return;
    }
    const suggestion = columnRef.current.querySelector(
      `[data-suggestion-id="${activeSuggestionId}"]`,
    );
    suggestion?.scrollIntoView({ block: "center", behavior: scrollBehavior() });
  }, [activeSuggestionId]);

  if (document === null) {
    return (
      <div className={styles.column}>
        {failed ? (
          <StatusBanner
            message="Can't reach the Redline server. Check that it's running."
            actionLabel=""
            onAction={() => undefined}
          />
        ) : (
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>
              {loading ? "Opening the contract." : "Choose a contract to review"}
            </p>
            <p className={styles.emptyDetail}>
              Ask Claude for redlines, then accept or reject each one.
            </p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={styles.column} ref={columnRef}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <h1 className={styles.title}>{document.title}</h1>
          <p className={styles.version}>Version {document.version}</p>
        </div>
        <div className={styles.search}>
          <label>
            <span className="visuallyHidden">Search in this contract</span>
            <input
              className={styles.field}
              value={query}
              placeholder="Search in this contract"
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== "Enter" || snippets.length === 0) {
                  return;
                }
                event.preventDefault();
                setMatchIndex((current) =>
                  stepMatch(current, snippets.length, event.shiftKey ? -MATCH_STEP : MATCH_STEP),
                );
              }}
            />
          </label>
          {search.searching ? (
            <span className={styles.matchCount}>{matchCount} matches</span>
          ) : null}
          <button
            type="button"
            className={styles.step}
            onClick={() =>
              setMatchIndex((current) => stepMatch(current, snippets.length, -MATCH_STEP))
            }
          >
            Previous
          </button>
          <button
            type="button"
            className={styles.step}
            onClick={() =>
              setMatchIndex((current) => stepMatch(current, snippets.length, MATCH_STEP))
            }
          >
            Next
          </button>
        </div>
      </header>
      <article className={styles.article}>
        {paragraphs.map((paragraph) => (
          <p
            key={paragraph.start}
            data-start={paragraph.start}
            className={paragraphClass(paragraph.isHeading, paragraph.changeState)}
          >
            {paragraph.segments.map((segment) => (
              <SegmentView
                key={`${segment.kind}-${segment.start}`}
                segment={segment}
                active={
                  segment.kind === SegmentKind.Suggestion &&
                  segment.suggestion.suggestionId === activeSuggestionId
                }
                hovered={
                  segment.kind === SegmentKind.Suggestion &&
                  segment.suggestion.suggestionId === hoveredSuggestionId
                }
                onSelectSuggestion={onSelectSuggestion}
                onHoverSuggestion={onHoverSuggestion}
              />
            ))}
          </p>
        ))}
      </article>
    </div>
  );
}

/**
 * Draw one text run or one suggestion.
 * @param segment - The run.
 * @param active - Whether the keyboard is on this suggestion.
 * @param hovered - Whether the matching card is hovered.
 * @param onSelectSuggestion - Makes the suggestion active.
 * @param onHoverSuggestion - Shares the hover with the card.
 * @returns The run.
 * @throws Does not throw.
 */
function SegmentView({
  segment,
  active,
  hovered,
  onSelectSuggestion,
  onHoverSuggestion,
}: {
  segment: DocumentSegment;
  active: boolean;
  hovered: boolean;
  onSelectSuggestion: (suggestionId: string) => void;
  onHoverSuggestion: (suggestionId: string | null) => void;
}): ReactNode {
  if (segment.kind === SegmentKind.Text) {
    return (
      <span data-start={segment.start} className={segment.highlighted ? styles.marked : undefined}>
        {segment.text}
      </span>
    );
  }
  return (
    <SuggestionRun
      segmentStart={segment.start}
      suggestion={segment.suggestion}
      highlighted={segment.highlighted}
      active={active}
      hovered={hovered}
      onSelectSuggestion={onSelectSuggestion}
      onHoverSuggestion={onHoverSuggestion}
    />
  );
}

/**
 * Draw a suggestion as a tracked change.
 * @param segmentStart - Where this run starts in the document.
 * @param suggestion - The suggestion.
 * @param highlighted - Whether a search match covers this run.
 * @param active - Whether the keyboard is on it.
 * @param hovered - Whether its card is hovered.
 * @param onSelectSuggestion - Makes it active.
 * @param onHoverSuggestion - Shares the hover with the card.
 * @returns The tracked change, once for the whole suggestion.
 * @throws Does not throw.
 */
function SuggestionRun({
  segmentStart,
  suggestion,
  highlighted,
  active,
  hovered,
  onSelectSuggestion,
  onHoverSuggestion,
}: {
  segmentStart: number;
  suggestion: ReviewSuggestion;
  highlighted: boolean;
  active: boolean;
  hovered: boolean;
  onSelectSuggestion: (suggestionId: string) => void;
  onHoverSuggestion: (suggestionId: string | null) => void;
}): ReactNode {
  if (segmentStart !== suggestion.start) {
    return null;
  }
  const className = [
    active ? styles.active : "",
    hovered ? styles.hovered : "",
    highlighted ? styles.marked : "",
  ]
    .filter((name) => name !== "")
    .join(" ");
  return (
    <span
      data-start={suggestion.start}
      data-suggestion-id={suggestion.suggestionId}
      className={className === "" ? undefined : className}
      onClick={() => onSelectSuggestion(suggestion.suggestionId)}
      onMouseEnter={() => onHoverSuggestion(suggestion.suggestionId)}
      onMouseLeave={() => onHoverSuggestion(null)}
    >
      <del className={deletionClasses(suggestion.status)}>{suggestion.originalText}</del>
      <ins className={insertionClasses(suggestion.status)}>{suggestion.replacement}</ins>
    </span>
  );
}

/**
 * Choose the deletion classes for one suggestion status.
 * @param status - The reviewer's decision.
 * @returns The class list.
 * @throws Does not throw.
 */
function deletionClasses(status: SuggestionStatus): string {
  switch (status) {
    case SuggestionStatus.Rejected:
      return rejectedDeletionClasses();
    case SuggestionStatus.Accepted:
      return acceptedDeletionClasses();
    case SuggestionStatus.Pending:
      return pendingDeletionClasses();
  }
}

/**
 * Draw a pending deletion: struck through, in the delete color.
 * @returns The class list.
 * @throws Does not throw.
 */
function pendingDeletionClasses(): string {
  return styles.deletion;
}

/**
 * Collapse a deletion once the suggestion is accepted.
 * @returns The class list.
 * @throws Does not throw.
 */
function acceptedDeletionClasses(): string {
  return `${styles.deletion} ${styles.collapsed}`;
}

/**
 * Show the original words as ordinary text once the suggestion is rejected.
 * @returns The class list.
 * @throws Does not throw.
 */
function rejectedDeletionClasses(): string {
  return `${styles.deletion} ${styles.plain}`;
}

/**
 * Choose the insertion classes for one suggestion status.
 * @param status - The reviewer's decision.
 * @returns The class list.
 * @throws Does not throw.
 */
function insertionClasses(status: SuggestionStatus): string {
  switch (status) {
    case SuggestionStatus.Rejected:
      return rejectedInsertionClasses();
    case SuggestionStatus.Accepted:
      return acceptedInsertionClasses();
    case SuggestionStatus.Pending:
      return pendingInsertionClasses();
  }
}

/**
 * Draw a pending insertion: underlined, in the insert color.
 * @returns The class list.
 * @throws Does not throw.
 */
function pendingInsertionClasses(): string {
  return styles.insertion;
}

/**
 * Show an accepted insertion in the accept color.
 * @returns The class list.
 * @throws Does not throw.
 */
function acceptedInsertionClasses(): string {
  return `${styles.insertion} ${styles.acceptedText}`;
}

/**
 * Collapse an insertion once the suggestion is rejected.
 * @returns The class list.
 * @throws Does not throw.
 */
function rejectedInsertionClasses(): string {
  return `${styles.insertion} ${styles.collapsed}`;
}

/**
 * Choose the paragraph classes.
 * @param isHeading - Whether the paragraph is a numbered heading.
 * @param changeState - Which change bar to show.
 * @returns The class list.
 * @throws Does not throw.
 */
function paragraphClass(isHeading: boolean, changeState: ChangeState): string {
  const names = [styles.paragraph];
  if (isHeading) {
    names.push(styles.sectionHeading);
  }
  if (changeState === ChangeState.Pending) {
    names.push(styles.pending);
  }
  if (changeState === ChangeState.Accepted) {
    names.push(styles.accepted);
  }
  return names.join(" ");
}

/**
 * Turn a jump into the highlight list the paragraphs expect.
 * @param start - The match start, or null.
 * @param end - The match end, or null.
 * @returns One highlight, or none.
 * @throws Does not throw.
 */
function jumpHighlight(start: number | null, end: number | null): TextSpanResponse[] {
  if (start === null || end === null) {
    return [];
  }
  return [{ start, end }];
}

/**
 * Move through the snippets, wrapping at either end.
 * @param current - The snippet on screen.
 * @param count - How many snippets there are.
 * @param delta - Which way to move.
 * @returns The next index.
 * @throws Does not throw.
 */
function stepMatch(current: number, count: number, delta: number): number {
  if (count === 0) {
    return 0;
  }
  return (current + delta + count) % count;
}

/**
 * Find the closest segment at or before an offset.
 * @param column - The scrolling column.
 * @param offset - The document offset, or null when there is nothing to show.
 * @returns The segment, or null.
 * @throws Does not throw.
 */
function findSegment(column: HTMLElement | null, offset: number | null): HTMLElement | null {
  if (column === null || offset === null) {
    return null;
  }
  const segments = Array.from(column.querySelectorAll<HTMLElement>("[data-start]"));
  let target: HTMLElement | null = null;
  for (const segment of segments) {
    const start = Number(segment.dataset.start);
    if (start <= offset) {
      target = segment;
    }
  }
  return target;
}

/**
 * Choose a scroll animation the reader has asked for.
 * @returns Smooth scrolling, or an instant jump when motion is reduced.
 * @throws Does not throw.
 */
function scrollBehavior(): ScrollBehavior {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return "auto";
  }
  return "smooth";
}
