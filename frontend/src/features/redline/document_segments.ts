export const SuggestionStatus = {
  Pending: "pending",
  Accepted: "accepted",
  Rejected: "rejected",
} as const;
export type SuggestionStatus = (typeof SuggestionStatus)[keyof typeof SuggestionStatus];

export const SegmentKind = {
  Text: "text",
  Suggestion: "suggestion",
} as const;
export type SegmentKind = (typeof SegmentKind)[keyof typeof SegmentKind];

export const ChangeState = {
  None: "none",
  Pending: "pending",
  Accepted: "accepted",
} as const;
export type ChangeState = (typeof ChangeState)[keyof typeof ChangeState];

const HEADING_PATTERN = /^\d+(\.\d+)*\.\s+\S/;
const HEADING_CHARACTER_LIMIT = 80;
const PARAGRAPH_BREAK = /\n[ \t]*\n\s*/g;

export interface ReviewSuggestion {
  suggestionId: string;
  start: number;
  end: number;
  originalText: string;
  replacement: string;
  rationale: string;
  status: SuggestionStatus;
}

export interface TextSpan {
  start: number;
  end: number;
}

export type DocumentSegment =
  | {
      kind: typeof SegmentKind.Text;
      start: number;
      end: number;
      text: string;
      highlighted: boolean;
    }
  | {
      kind: typeof SegmentKind.Suggestion;
      start: number;
      end: number;
      suggestion: ReviewSuggestion;
      highlighted: boolean;
    };

export interface DocumentParagraph {
  start: number;
  end: number;
  isHeading: boolean;
  segments: DocumentSegment[];
  changeState: ChangeState;
}

interface ParagraphSpan {
  start: number;
  end: number;
}

/**
 * Split a document into paragraphs with suggestions and highlights cut into segments.
 * @param text - The full document.
 * @param suggestions - Suggestions whose spans use document offsets.
 * @param highlights - Search matches whose spans use document offsets.
 * @returns Paragraphs that tile the document.
 * @throws Does not throw.
 */
export function buildDocumentParagraphs(
  text: string,
  suggestions: ReviewSuggestion[],
  highlights: TextSpan[],
): DocumentParagraph[] {
  const spans = adjustForCrossingSuggestions(splitParagraphSpans(text), suggestions);
  return spans.map((span) => buildParagraph(text, span, suggestions, highlights));
}

/**
 * Split the text on blank lines, keeping each break with the paragraph before it.
 * @param text - The full document.
 * @returns Spans that tile the text.
 * @throws Does not throw.
 */
function splitParagraphSpans(text: string): ParagraphSpan[] {
  if (text.length === 0) {
    return [];
  }
  const spans: ParagraphSpan[] = [];
  const pattern = new RegExp(PARAGRAPH_BREAK.source, "g");
  let cursor = 0;
  let match = pattern.exec(text);
  while (match !== null) {
    spans.push({ start: cursor, end: match.index + match[0].length });
    cursor = match.index + match[0].length;
    match = pattern.exec(text);
  }
  if (cursor < text.length) {
    spans.push({ start: cursor, end: text.length });
  }
  return spans;
}

/**
 * Keep a suggestion that crosses a paragraph break inside the paragraph where it starts.
 * @param spans - The paragraph spans.
 * @param suggestions - The suggestions that may cross a break.
 * @returns Spans that still tile the text, with a crossing suggestion owned by its first paragraph.
 * @throws Does not throw.
 */
function adjustForCrossingSuggestions(
  spans: ParagraphSpan[],
  suggestions: ReviewSuggestion[],
): ParagraphSpan[] {
  const adjusted: ParagraphSpan[] = [];
  let cursor = 0;
  for (const span of spans) {
    if (span.end <= cursor) {
      continue;
    }
    const start = Math.max(span.start, cursor);
    let end = span.end;
    for (const suggestion of suggestions) {
      const startsHere = suggestion.start >= start && suggestion.start < end;
      if (startsHere && suggestion.end > end) {
        end = suggestion.end;
      }
    }
    if (start < end) {
      adjusted.push({ start, end });
    }
    cursor = end;
  }
  return adjusted;
}

/**
 * Build one paragraph from the cuts inside its span.
 * @param text - The full document.
 * @param span - This paragraph's offsets.
 * @param suggestions - Every suggestion.
 * @param highlights - Every search highlight.
 * @returns The paragraph.
 * @throws Does not throw.
 */
function buildParagraph(
  text: string,
  span: ParagraphSpan,
  suggestions: ReviewSuggestion[],
  highlights: TextSpan[],
): DocumentParagraph {
  const segments = mergeSegments(cutSegments(text, span, suggestions, highlights));
  const paragraphText = text.slice(span.start, span.end);
  return {
    start: span.start,
    end: span.end,
    isHeading: isHeading(paragraphText),
    segments,
    changeState: getChangeState(segments),
  };
}

/**
 * Return whether the paragraph is a short numbered heading.
 * @param paragraphText - The paragraph, including the blank lines after it.
 * @returns Whether it renders as a heading.
 * @throws Does not throw.
 */
function isHeading(paragraphText: string): boolean {
  const content = paragraphText.replace(/\s+$/, "");
  return content.length < HEADING_CHARACTER_LIMIT && HEADING_PATTERN.test(content);
}

/**
 * Cut one paragraph at every suggestion and highlight boundary.
 * @param text - The full document.
 * @param span - This paragraph's offsets.
 * @param suggestions - Every suggestion.
 * @param highlights - Every search highlight.
 * @returns Segments in document order, before neighbors are merged.
 * @throws Does not throw.
 */
function cutSegments(
  text: string,
  span: ParagraphSpan,
  suggestions: ReviewSuggestion[],
  highlights: TextSpan[],
): DocumentSegment[] {
  const boundaries = new Set<number>([span.start, span.end]);
  for (const suggestion of suggestions) {
    addBoundary(boundaries, span, suggestion.start);
    addBoundary(boundaries, span, suggestion.end);
  }
  for (const highlight of highlights) {
    addBoundary(boundaries, span, highlight.start);
    addBoundary(boundaries, span, highlight.end);
  }
  const points = [...boundaries].sort((left, right) => left - right);
  const segments: DocumentSegment[] = [];
  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index];
    const end = points[index + 1];
    if (start === end) {
      continue;
    }
    segments.push(buildSegment(text, span, start, end, suggestions, highlights));
  }
  return segments;
}

/**
 * Record a cut when it falls strictly inside the paragraph.
 * @param boundaries - The cut offsets collected so far.
 * @param span - This paragraph's offsets.
 * @param offset - A suggestion or highlight edge.
 * @throws Does not throw.
 */
function addBoundary(boundaries: Set<number>, span: ParagraphSpan, offset: number): void {
  if (offset > span.start && offset < span.end) {
    boundaries.add(offset);
  }
}

/**
 * Build the segment that covers one slice of a paragraph.
 * @param text - The full document.
 * @param span - This paragraph's offsets.
 * @param start - The slice start.
 * @param end - The slice end.
 * @param suggestions - Every suggestion.
 * @param highlights - Every search highlight.
 * @returns The text or suggestion segment.
 * @throws Does not throw.
 */
function buildSegment(
  text: string,
  span: ParagraphSpan,
  start: number,
  end: number,
  suggestions: ReviewSuggestion[],
  highlights: TextSpan[],
): DocumentSegment {
  const suggestion = findOwningSuggestion(span, start, end, suggestions);
  const highlighted = highlights.some(
    (highlight) => highlight.start <= start && end <= highlight.end,
  );
  if (suggestion === null) {
    return {
      kind: SegmentKind.Text,
      start,
      end,
      text: text.slice(start, end),
      highlighted,
    };
  }
  return {
    kind: SegmentKind.Suggestion,
    start,
    end,
    suggestion,
    highlighted,
  };
}

/**
 * Return the suggestion that owns this slice, when it starts in this paragraph.
 * @param span - This paragraph's offsets.
 * @param start - The slice start.
 * @param end - The slice end.
 * @param suggestions - Every suggestion.
 * @returns The owning suggestion, or null when the slice is plain text.
 * @throws Does not throw.
 */
function findOwningSuggestion(
  span: ParagraphSpan,
  start: number,
  end: number,
  suggestions: ReviewSuggestion[],
): ReviewSuggestion | null {
  for (const suggestion of suggestions) {
    const startsHere = suggestion.start >= span.start && suggestion.start < span.end;
    const coversSlice = suggestion.start <= start && end <= suggestion.end;
    if (startsHere && coversSlice) {
      return suggestion;
    }
  }
  return null;
}

/**
 * Join neighboring text with the same highlight, and neighboring pieces of one suggestion.
 * @param segments - The slices in document order.
 * @returns Segments a reader sees as one run.
 * @throws Does not throw.
 */
function mergeSegments(segments: DocumentSegment[]): DocumentSegment[] {
  const merged: DocumentSegment[] = [];
  for (const segment of segments) {
    const previous = merged[merged.length - 1];
    if (previous === undefined) {
      merged.push(segment);
      continue;
    }
    const mergedText = mergeTextSegments(previous, segment);
    if (mergedText !== null) {
      merged[merged.length - 1] = mergedText;
      continue;
    }
    const mergedSuggestion = mergeSuggestionSegments(previous, segment);
    if (mergedSuggestion !== null) {
      merged[merged.length - 1] = mergedSuggestion;
      continue;
    }
    merged.push(segment);
  }
  return merged;
}

/**
 * Join two text slices when they touch and share a highlight.
 * @param previous - The segment already kept.
 * @param segment - The next slice.
 * @returns The joined segment, or null when they stay separate.
 * @throws Does not throw.
 */
function mergeTextSegments(
  previous: DocumentSegment,
  segment: DocumentSegment,
): DocumentSegment | null {
  if (previous.kind !== SegmentKind.Text || segment.kind !== SegmentKind.Text) {
    return null;
  }
  if (previous.end !== segment.start || previous.highlighted !== segment.highlighted) {
    return null;
  }
  return {
    kind: SegmentKind.Text,
    start: previous.start,
    end: segment.end,
    text: previous.text + segment.text,
    highlighted: previous.highlighted,
  };
}

/**
 * Join two slices of the same suggestion so the replacement is drawn once.
 * @param previous - The segment already kept.
 * @param segment - The next slice.
 * @returns The joined segment, or null when they stay separate.
 * @throws Does not throw.
 */
function mergeSuggestionSegments(
  previous: DocumentSegment,
  segment: DocumentSegment,
): DocumentSegment | null {
  if (previous.kind !== SegmentKind.Suggestion || segment.kind !== SegmentKind.Suggestion) {
    return null;
  }
  if (previous.suggestion.suggestionId !== segment.suggestion.suggestionId) {
    return null;
  }
  if (previous.end !== segment.start) {
    return null;
  }
  return {
    kind: SegmentKind.Suggestion,
    start: previous.start,
    end: segment.end,
    suggestion: previous.suggestion,
    highlighted: previous.highlighted || segment.highlighted,
  };
}

/**
 * Choose the paragraph's change bar from the suggestions inside it.
 * @param segments - The paragraph's segments.
 * @returns Pending when any suggestion is still open, otherwise accepted when one was accepted.
 * @throws Does not throw.
 */
function getChangeState(segments: DocumentSegment[]): ChangeState {
  const suggestions = segments.flatMap((segment) =>
    segment.kind === SegmentKind.Suggestion ? [segment.suggestion] : [],
  );
  if (suggestions.some((suggestion) => suggestion.status === SuggestionStatus.Pending)) {
    return ChangeState.Pending;
  }
  if (suggestions.some((suggestion) => suggestion.status === SuggestionStatus.Accepted)) {
    return ChangeState.Accepted;
  }
  return ChangeState.None;
}
