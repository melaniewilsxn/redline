import { describe, expect, it } from "vitest";

import {
  ChangeState,
  SegmentKind,
  SuggestionStatus,
  buildDocumentParagraphs,
  type ReviewSuggestion,
} from "./document_segments.ts";

const RATIONALE = "Make the indemnity mutual.";

/**
 * Build one suggestion.
 * @param suggestionId - The stable id.
 * @param start - The span start.
 * @param end - The span end.
 * @param status - Whether the reviewer has decided.
 * @returns The suggestion.
 * @throws Does not throw.
 */
function buildSuggestion(
  suggestionId: string,
  start: number,
  end: number,
  status: ReviewSuggestion["status"],
): ReviewSuggestion {
  return {
    suggestionId,
    start,
    end,
    originalText: "text",
    replacement: "replacement",
    rationale: RATIONALE,
    title: "Make the indemnity mutual",
    status,
  };
}

describe("document paragraphs", () => {
  it("splits paragraphs on blank lines with absolute offsets", () => {
    const text = "Alpha.\n\nBeta.";

    const paragraphs = buildDocumentParagraphs(text, [], []);

    expect(paragraphs.map((paragraph) => [paragraph.start, paragraph.end])).toEqual([
      [0, 8],
      [8, 13],
    ]);
    expect(paragraphs[0]?.segments[0]).toMatchObject({
      kind: SegmentKind.Text,
      text: "Alpha.\n\n",
    });
    expect(paragraphs[1]?.segments[0]).toMatchObject({ kind: SegmentKind.Text, text: "Beta." });
  });

  it("marks a numbered short paragraph as a heading", () => {
    const paragraphs = buildDocumentParagraphs("11. Indemnification\n\nBody.", [], []);

    expect(paragraphs[0]?.isHeading).toBe(true);
    expect(paragraphs[1]?.isHeading).toBe(false);
  });

  it("does not mark a long numbered paragraph as a heading", () => {
    const heading = `11. ${"word ".repeat(30)}`;
    const paragraphs = buildDocumentParagraphs(heading, [], []);

    expect(heading.replace(/\s+$/, "").length).toBeGreaterThanOrEqual(80);
    expect(paragraphs[0]?.isHeading).toBe(false);
  });

  it("places a suggestion as one segment between text segments", () => {
    const text = "Hello world.";
    const suggestion = buildSuggestion("s1", 6, 11, SuggestionStatus.Pending);

    const paragraphs = buildDocumentParagraphs(text, [suggestion], []);

    expect(paragraphs[0]?.segments).toEqual([
      { kind: SegmentKind.Text, start: 0, end: 6, text: "Hello ", highlighted: false },
      {
        kind: SegmentKind.Suggestion,
        start: 6,
        end: 11,
        suggestion,
        highlighted: false,
      },
      { kind: SegmentKind.Text, start: 11, end: 12, text: ".", highlighted: false },
    ]);
  });

  it("splits text at highlight boundaries", () => {
    const paragraphs = buildDocumentParagraphs("Hello world.", [], [{ start: 0, end: 5 }]);

    expect(paragraphs[0]?.segments).toEqual([
      { kind: SegmentKind.Text, start: 0, end: 5, text: "Hello", highlighted: true },
      { kind: SegmentKind.Text, start: 5, end: 12, text: " world.", highlighted: false },
    ]);
  });

  it("highlights the original text inside a suggestion", () => {
    const suggestion = buildSuggestion("s1", 6, 11, SuggestionStatus.Pending);

    const paragraphs = buildDocumentParagraphs(
      "Hello world.",
      [suggestion],
      [{ start: 6, end: 11 }],
    );

    expect(paragraphs[0]?.segments[1]).toMatchObject({
      kind: SegmentKind.Suggestion,
      highlighted: true,
      suggestion,
    });
  });

  it("sets change state pending when any suggestion is pending", () => {
    const text = "Hello world.";
    const suggestions = [
      buildSuggestion("s1", 0, 5, SuggestionStatus.Accepted),
      buildSuggestion("s2", 6, 11, SuggestionStatus.Pending),
    ];

    const paragraphs = buildDocumentParagraphs(text, suggestions, []);

    expect(paragraphs[0]?.changeState).toBe(ChangeState.Pending);
  });

  it("sets change state accepted when all suggestions are decided and one is accepted", () => {
    const text = "Hello world.";
    const suggestions = [
      buildSuggestion("s1", 0, 5, SuggestionStatus.Accepted),
      buildSuggestion("s2", 6, 11, SuggestionStatus.Rejected),
    ];

    const paragraphs = buildDocumentParagraphs(text, suggestions, []);

    expect(paragraphs[0]?.changeState).toBe(ChangeState.Accepted);
  });

  it("sets change state none when every suggestion is rejected", () => {
    const paragraphs = buildDocumentParagraphs(
      "Hello world.",
      [buildSuggestion("s1", 6, 11, SuggestionStatus.Rejected)],
      [],
    );

    expect(paragraphs[0]?.changeState).toBe(ChangeState.None);
  });

  it("keeps a suggestion that crosses a paragraph break whole in its first paragraph", () => {
    const text = "One.\n\nTwo is here.";
    const suggestion = buildSuggestion("s1", 2, 9, SuggestionStatus.Pending);

    const paragraphs = buildDocumentParagraphs(text, [suggestion], []);

    expect(paragraphs).toHaveLength(2);
    expect(paragraphs[0]?.end).toBe(9);
    expect(paragraphs[0]?.segments.some((segment) => segment.kind === SegmentKind.Suggestion)).toBe(
      true,
    );
    const suggestionSegment = paragraphs[0]?.segments.find(
      (segment) => segment.kind === SegmentKind.Suggestion,
    );
    expect(suggestionSegment).toMatchObject({ start: 2, end: 9 });
    expect(paragraphs[1]?.start).toBe(9);
    expect(paragraphs[1]?.segments.every((segment) => segment.kind === SegmentKind.Text)).toBe(
      true,
    );
  });
});
