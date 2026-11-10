import { useEffect, useRef, useState, type ReactNode } from "react";

import type { DocumentResponse } from "../../api/types.ts";
import { StatusBanner } from "../../components/status_banner.tsx";
import { useDocumentSearch } from "../search/use_search.ts";
import {
  ChangeState,
  SegmentKind,
  SuggestionStatus,
  buildDocumentParagraphs,
  type DocumentParagraph,
  type DocumentSegment,
  type ReviewSuggestion,
  type TextSpan,
} from "./document_segments.ts";
import {
  SuggestionPartKind,
  buildSuggestionParts,
  getRenderedSeparator,
  type SuggestionPart,
} from "./suggestion_diff.ts";
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
 * @param persistedHighlights - Matches kept from the last search jump.
 * @param focusStart - The jumped-to match, or null.
 * @param focusEnd - The end of the jumped-to match.
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
  persistedHighlights,
  focusStart,
  focusEnd,
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
  persistedHighlights: TextSpan[];
  focusStart: number | null;
  focusEnd: number | null;
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
  const inDocumentHighlights = snippets.flatMap((snippet) => snippet.highlights);
  const documentHighlights = search.searching ? inDocumentHighlights : persistedHighlights;
  const activeFocusStart = search.searching
    ? (currentSnippet?.highlights[0]?.start ?? null)
    : focusStart;
  const activeFocusEnd = search.searching ? (currentSnippet?.highlights[0]?.end ?? null) : focusEnd;
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
          {query === "" ? null : (
            <>
              <span className={styles.matchCount}>{matchCount} matches</span>
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
            </>
          )}
        </div>
      </header>
      <article className={styles.article}>
        {paragraphs.map((paragraph) => (
          <p
            key={paragraph.start}
            data-start={paragraph.start}
            className={paragraphClassName(paragraph, activeSuggestionId)}
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
                highlights={documentHighlights}
                focusStart={activeFocusStart}
                focusEnd={activeFocusEnd}
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
 * @param highlights - Search matches in document offsets.
 * @param focusStart - The jumped-to match, or null.
 * @param focusEnd - The end of the jumped-to match.
 * @param active - Whether the keyboard is on this suggestion.
 * @param hovered - Whether the matching card is hovered.
 * @param onSelectSuggestion - Makes the suggestion active.
 * @param onHoverSuggestion - Shares the hover with the card.
 * @returns The run.
 * @throws Does not throw.
 */
function SegmentView({
  segment,
  highlights,
  focusStart,
  focusEnd,
  active,
  hovered,
  onSelectSuggestion,
  onHoverSuggestion,
}: {
  segment: DocumentSegment;
  highlights: TextSpan[];
  focusStart: number | null;
  focusEnd: number | null;
  active: boolean;
  hovered: boolean;
  onSelectSuggestion: (suggestionId: string) => void;
  onHoverSuggestion: (suggestionId: string | null) => void;
}): ReactNode {
  if (segment.kind === SegmentKind.Text) {
    if (!segment.highlighted) {
      return <span data-start={segment.start}>{segment.text}</span>;
    }
    return (
      <mark
        data-start={segment.start}
        className={markClass(segment.start, segment.end, focusStart, focusEnd)}
      >
        {segment.text}
      </mark>
    );
  }
  return (
    <SuggestionRun
      segmentStart={segment.start}
      suggestion={segment.suggestion}
      highlights={highlights}
      focusStart={focusStart}
      focusEnd={focusEnd}
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
 * @param highlights - Search matches in document offsets.
 * @param focusStart - The jumped-to match, or null.
 * @param focusEnd - The end of the jumped-to match.
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
  highlights,
  focusStart,
  focusEnd,
  active,
  hovered,
  onSelectSuggestion,
  onHoverSuggestion,
}: {
  segmentStart: number;
  suggestion: ReviewSuggestion;
  highlights: TextSpan[];
  focusStart: number | null;
  focusEnd: number | null;
  active: boolean;
  hovered: boolean;
  onSelectSuggestion: (suggestionId: string) => void;
  onHoverSuggestion: (suggestionId: string | null) => void;
}): ReactNode {
  if (segmentStart !== suggestion.start) {
    return null;
  }
  const className = [active ? styles.active : "", hovered ? styles.hovered : ""]
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
      {renderSuggestionParts(suggestion, highlights, focusStart, focusEnd)}
    </span>
  );
}

/**
 * Draw each word-level part of a suggestion.
 * @param suggestion - The suggestion.
 * @param highlights - Search matches in document offsets.
 * @param focusStart - The jumped-to match, or null.
 * @param focusEnd - The end of the jumped-to match.
 * @returns The parts in order.
 * @throws Does not throw.
 */
function renderSuggestionParts(
  suggestion: ReviewSuggestion,
  highlights: TextSpan[],
  focusStart: number | null,
  focusEnd: number | null,
): ReactNode[] {
  const parts = buildSuggestionParts(suggestion.originalText, suggestion.replacement);
  const views: ReactNode[] = [];
  let originalOffset = suggestion.start;
  for (let index = 0; index < parts.length; index += 1) {
    const part = parts[index];
    if (part.kind === SuggestionPartKind.Added) {
      views.push(renderAddedPart(suggestion.status, part.text, index));
      continue;
    }
    views.push(
      renderOriginalPart(
        suggestion.status,
        part,
        buildMarkedRuns(part.text, originalOffset, highlights, focusStart, focusEnd),
        index,
      ),
    );
    originalOffset += part.text.length;
    const next = index + 1 < parts.length ? parts[index + 1] : undefined;
    if (part.kind === SuggestionPartKind.Removed && next?.kind === SuggestionPartKind.Added) {
      const separator = getRenderedSeparator(part.text, next.text);
      if (separator !== "") {
        views.push(separator);
      }
    }
  }
  return views;
}

interface MarkedRun {
  text: string;
  highlighted: boolean;
  focused: boolean;
}

/**
 * Draw the added words for one suggestion status.
 * @param status - The reviewer's decision.
 * @param text - The added words.
 * @param index - The part's place in the diff.
 * @returns The added words.
 * @throws Does not throw.
 */
function renderAddedPart(status: SuggestionStatus, text: string, index: number): ReactNode {
  switch (status) {
    case SuggestionStatus.Pending:
      return renderPendingAddedPart(text, index);
    case SuggestionStatus.Accepted:
      return renderAcceptedAddedPart(text, index);
    case SuggestionStatus.Rejected:
      return renderRejectedAddedPart(text, index);
  }
}

/**
 * Draw the original words for one suggestion status.
 * @param status - The reviewer's decision.
 * @param part - The unchanged or removed part.
 * @param runs - Those words, split where a search match falls.
 * @param index - The part's place in the diff.
 * @returns The original words.
 * @throws Does not throw.
 */
function renderOriginalPart(
  status: SuggestionStatus,
  part: SuggestionPart,
  runs: MarkedRun[],
  index: number,
): ReactNode {
  switch (status) {
    case SuggestionStatus.Pending:
      return part.kind === SuggestionPartKind.Removed
        ? renderPendingRemovedPart(runs, index)
        : renderPendingUnchangedPart(runs, index);
    case SuggestionStatus.Accepted:
      return part.kind === SuggestionPartKind.Removed
        ? renderAcceptedRemovedPart(runs, index)
        : renderAcceptedUnchangedPart(runs, index);
    case SuggestionStatus.Rejected:
      return renderRejectedOriginalPart(runs, index);
  }
}

/**
 * Draw pending words that stay.
 * @param runs - The words, split where a search match falls.
 * @param index - The part's place in the diff.
 * @returns The words.
 * @throws Does not throw.
 */
function renderPendingUnchangedPart(runs: MarkedRun[], index: number): ReactNode {
  return <span key={index}>{renderMarkedRuns(runs)}</span>;
}

/**
 * Draw pending words that the suggestion removes.
 * @param runs - The words, split where a search match falls.
 * @param index - The part's place in the diff.
 * @returns The struck words.
 * @throws Does not throw.
 */
function renderPendingRemovedPart(runs: MarkedRun[], index: number): ReactNode {
  return (
    <del key={index} className={styles.deletion}>
      {renderMarkedRuns(runs)}
    </del>
  );
}

/**
 * Draw pending words that the suggestion adds.
 * @param text - The added words.
 * @param index - The part's place in the diff.
 * @returns The inserted words.
 * @throws Does not throw.
 */
function renderPendingAddedPart(text: string, index: number): ReactNode {
  return (
    <ins key={index} className={styles.insertion}>
      {text}
    </ins>
  );
}

/**
 * Draw words that stay after the suggestion is accepted.
 * @param runs - The words, split where a search match falls.
 * @param index - The part's place in the diff.
 * @returns The words.
 * @throws Does not throw.
 */
function renderAcceptedUnchangedPart(runs: MarkedRun[], index: number): ReactNode {
  return <span key={index}>{renderMarkedRuns(runs)}</span>;
}

/**
 * Collapse words the reviewer accepted removing.
 * @param runs - The words, split where a search match falls.
 * @param index - The part's place in the diff.
 * @returns The collapsed words.
 * @throws Does not throw.
 */
function renderAcceptedRemovedPart(runs: MarkedRun[], index: number): ReactNode {
  return (
    <del key={index} className={`${styles.deletion} ${styles.collapsed}`}>
      {renderMarkedRuns(runs)}
    </del>
  );
}

/**
 * Draw accepted words in the accept color.
 * @param text - The added words.
 * @param index - The part's place in the diff.
 * @returns The accepted words.
 * @throws Does not throw.
 */
function renderAcceptedAddedPart(text: string, index: number): ReactNode {
  return (
    <ins key={index} className={`${styles.insertion} ${styles.acceptedText}`}>
      {text}
    </ins>
  );
}

/**
 * Draw the original words after the suggestion is rejected.
 * @param runs - The words, split where a search match falls.
 * @param index - The part's place in the diff.
 * @returns The words as ordinary text.
 * @throws Does not throw.
 */
function renderRejectedOriginalPart(runs: MarkedRun[], index: number): ReactNode {
  return <span key={index}>{renderMarkedRuns(runs)}</span>;
}

/**
 * Collapse words the reviewer rejected adding.
 * @param text - The added words.
 * @param index - The part's place in the diff.
 * @returns The collapsed words.
 * @throws Does not throw.
 */
function renderRejectedAddedPart(text: string, index: number): ReactNode {
  return (
    <ins key={index} className={`${styles.insertion} ${styles.collapsed}`}>
      {text}
    </ins>
  );
}

/**
 * Draw search marks inside one run of words.
 * @param runs - The pieces of the run.
 * @returns The words, with matches marked.
 * @throws Does not throw.
 */
function renderMarkedRuns(runs: MarkedRun[]): ReactNode {
  return runs.map((run, index) =>
    run.highlighted ? (
      <mark key={index} className={run.focused ? styles.focusedMark : undefined}>
        {run.text}
      </mark>
    ) : (
      <span key={index}>{run.text}</span>
    ),
  );
}

/**
 * Split words where a search match starts or ends.
 * @param text - The words.
 * @param documentStart - Where these words start in the document.
 * @param highlights - Search matches in document offsets.
 * @param focusStart - The jumped-to match, or null.
 * @param focusEnd - The end of the jumped-to match.
 * @returns The pieces, each marked when a search match covers it.
 * @throws Does not throw.
 */
function buildMarkedRuns(
  text: string,
  documentStart: number,
  highlights: TextSpan[],
  focusStart: number | null,
  focusEnd: number | null,
): MarkedRun[] {
  const documentEnd = documentStart + text.length;
  const edges = new Set<number>([documentStart, documentEnd]);
  for (const highlight of highlights) {
    if (highlight.start > documentStart && highlight.start < documentEnd) {
      edges.add(highlight.start);
    }
    if (highlight.end > documentStart && highlight.end < documentEnd) {
      edges.add(highlight.end);
    }
  }
  const ordered = [...edges].sort((left, right) => left - right);
  const runs: MarkedRun[] = [];
  for (let index = 0; index < ordered.length - 1; index += 1) {
    const start = ordered[index];
    const end = ordered[index + 1];
    const highlighted = highlights.some(
      (highlight) => highlight.start <= start && end <= highlight.end,
    );
    runs.push({
      text: text.slice(start - documentStart, end - documentStart),
      highlighted,
      focused: highlighted && rangesOverlap(start, end, focusStart, focusEnd),
    });
  }
  return runs;
}

/**
 * Choose the mark classes for a plain-text match.
 * @param start - The match start.
 * @param end - The match end.
 * @param focusStart - The jumped-to match, or null.
 * @param focusEnd - The end of the jumped-to match.
 * @returns The class list.
 * @throws Does not throw.
 */
function markClass(
  start: number,
  end: number,
  focusStart: number | null,
  focusEnd: number | null,
): string {
  if (rangesOverlap(start, end, focusStart, focusEnd)) {
    return `${styles.marked} ${styles.focusedMark}`;
  }
  return styles.marked;
}

/**
 * Report whether two ranges share a character.
 * @param start - The first range start.
 * @param end - The first range end.
 * @param focusStart - The second range start, or null.
 * @param focusEnd - The second range end, or null.
 * @returns True when the ranges overlap.
 * @throws Does not throw.
 */
function rangesOverlap(
  start: number,
  end: number,
  focusStart: number | null,
  focusEnd: number | null,
): boolean {
  if (focusStart === null || focusEnd === null) {
    return false;
  }
  return start < focusEnd && focusStart < end;
}

/**
 * Choose the paragraph classes, including a stronger bar when it holds the active suggestion.
 * @param paragraph - The paragraph.
 * @param activeSuggestionId - The suggestion the keyboard is on, or null.
 * @returns The class list.
 * @throws Does not throw.
 */
function paragraphClassName(
  paragraph: DocumentParagraph,
  activeSuggestionId: string | null,
): string {
  const names = [paragraphClass(paragraph.isHeading, paragraph.changeState)];
  if (paragraphHoldsActiveSuggestion(paragraph, activeSuggestionId)) {
    names.push(styles.activeChange);
  }
  return names.join(" ");
}

/**
 * Report whether the active suggestion is in this paragraph.
 * @param paragraph - The paragraph.
 * @param activeSuggestionId - The suggestion the keyboard is on, or null.
 * @returns True when the paragraph holds that suggestion.
 * @throws Does not throw.
 */
function paragraphHoldsActiveSuggestion(
  paragraph: DocumentParagraph,
  activeSuggestionId: string | null,
): boolean {
  if (activeSuggestionId === null) {
    return false;
  }
  return paragraph.segments.some(
    (segment) =>
      segment.kind === SegmentKind.Suggestion &&
      segment.suggestion.suggestionId === activeSuggestionId,
  );
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
